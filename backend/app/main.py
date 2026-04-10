from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import func, select, text

from app.api.router import api_v1_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.session import engine, AsyncSessionLocal

settings = get_settings()
logger = get_logger(__name__)


async def ensure_config_kv_populated() -> None:
    """Seed MQTT + tuning keys into config_kv from .env if missing (for existing deployments)."""
    from app.models.config import ConfigKV

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ConfigKV.key).where(ConfigKV.key == "mqtt_host")
        )
        if result.scalar_one_or_none() is not None:
            return  # Already populated

        defaults = {
            "mqtt_host": settings.mqtt_broker_host,
            "mqtt_port": str(settings.mqtt_broker_port),
            "mqtt_user": settings.mqtt_username,
            "mqtt_pass": settings.mqtt_password,
            "access_token_expire_minutes": str(settings.access_token_expire_minutes),
            "refresh_token_expire_days": str(settings.refresh_token_expire_days),
            "log_level": settings.log_level,
            "device_gateway_url": settings.device_gateway_url,
            "sensor_stale_minutes": "5",
            "health_poll_seconds": "30",
            "gateway_timeout_seconds": "5",
            "chart_history_days": "100",
            "frontend_poll_seconds": "30",
            "mqtt_topic_prefix": "home/devices/",
        }
        for key, value in defaults.items():
            existing = await session.execute(
                select(ConfigKV.key).where(ConfigKV.key == key)
            )
            if existing.scalar_one_or_none() is None:
                session.add(ConfigKV(key=key, value=value))
        await session.commit()
        logger.info("config_kv_bootstrapped_from_env")


async def ensure_tables_exist() -> None:
    """Create all tables if they don't exist (safe for both SQLite and PostgreSQL).

    On first connection to a new database (e.g. after switching to PostgreSQL),
    this creates the schema. On existing databases, it's a no-op.
    """
    from app.models.base import Base
    # Import all models so Base.metadata knows about them
    import app.models.sensor  # noqa: F401
    import app.models.config  # noqa: F401
    import app.models.event  # noqa: F401
    import app.models.heating  # noqa: F401
    import app.models.pending_sensor  # noqa: F401
    import app.models.user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_seed_data() -> None:
    """Run seed if database is empty (no users = fresh database)."""
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count()).select_from(User))
        count = result.scalar() or 0
        if count == 0:
            logger.info("empty_database_detected, running seed")
            from app.db.seed import seed
            await seed(session)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    import asyncio
    from app.services.health_monitor import HealthMonitor

    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        log_file=settings.log_file,
        log_max_bytes=settings.log_max_bytes,
        log_backup_count=settings.log_backup_count,
    )
    await ensure_tables_exist()
    await ensure_seed_data()
    await ensure_config_kv_populated()
    logger.info("application_startup", env=settings.app_env)

    # Start background health monitor — single source of truth for health state
    monitor = HealthMonitor(
        session_factory=AsyncSessionLocal,
        gateway_url=settings.device_gateway_url,
    )
    app.state.health_monitor = monitor
    monitor_task = asyncio.create_task(monitor.run())

    yield

    monitor_task.cancel()
    await engine.dispose()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="HomeSite v2",
        description=(
            "Home automation API for monitoring and controlling heating, "
            "water supply, and climate sensors via MQTT."
        ),
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_tags=[
            {"name": "auth", "description": "Authentication & user management"},
            {"name": "sensors", "description": "Sensor data & dashboard"},
            {"name": "charts", "description": "Chart data (PZA curves & sensor history)"},
            {"name": "settings", "description": "System configuration & device control"},
            {"name": "websocket", "description": "Real-time sensor updates"},
            {"name": "internal", "description": "Internal API (DeviceGateway → Backend)"},
        ],
    )

    # Rate limiting — disabled in test env to avoid test interference
    app.state.limiter = limiter
    if settings.app_env != "test":
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

    # CORS — allow frontend origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_v1_router)

    # Liveness probe — always returns ok if the process is running
    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "version": "2.0.0"}

    # Readiness probe — checks DB connectivity
    @app.get("/health/ready", tags=["health"])
    async def health_ready():
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            return {"status": "ready", "database": "ok"}
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "database": str(e)},
            )

    # Aggregated status — reads from HealthMonitor cache (no extra DB/HTTP calls)
    @app.get("/health/status", tags=["health"])
    async def health_status(request: Request):
        monitor = request.app.state.health_monitor
        s = monitor.state
        return {
            "backend": s.backend,
            "database": s.database,
            "gateway": s.gateway,
            "mqtt": s.mqtt,
            "poll_seconds": s.poll_seconds,
        }

    # Sensor health — reads from HealthMonitor cache
    @app.get("/health/sensors", tags=["health"])
    async def health_sensors(request: Request):
        s = request.app.state.health_monitor.state
        return {
            "total": s.sensor_total,
            "active": s.sensor_active,
            "pending": s.sensor_pending,
        }

    # Device health — live query (pending/unsynced change rapidly, can't use cache)
    @app.get("/health/devices", tags=["health"])
    async def health_devices(request: Request):
        from datetime import UTC, datetime

        from app.models.config import Actuator

        monitor = request.app.state.health_monitor
        s = monitor.state
        hb_timeout = 60  # default

        # Load actuators from DB
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Actuator))
            actuators = result.scalars().all()

            # Get heartbeat timeout from config
            from app.models.config import ConfigKV

            kv_result = await session.execute(
                select(ConfigKV.value).where(ConfigKV.key == "heartbeat_timeout_seconds")
            )
            kv_val = kv_result.scalar_one_or_none()
            if kv_val:
                hb_timeout = int(kv_val)

        # Fetch gateway health (heartbeats + command queues)
        pending_commands = 0
        unsynced_commands = 0
        heartbeats: dict = {}
        try:
            async with httpx.AsyncClient(base_url=settings.device_gateway_url, timeout=2.0) as client:
                resp = await client.get("/health")
                if resp.status_code == 200:
                    gw = resp.json()
                    pending_commands = gw.get("pending_commands", 0)
                    unsynced_commands = gw.get("unsynced_commands", 0)
                    heartbeats = gw.get("heartbeats", {})
        except Exception:
            pass

        now = datetime.now(UTC)
        devices = []
        online_count = 0

        for act in actuators:
            hb_info = heartbeats.get(act.mqtt_device_name)
            online = False
            last_heartbeat = None
            heartbeat_data = {}

            if hb_info and isinstance(hb_info, dict):
                ts_str = hb_info.get("timestamp")
                heartbeat_data = hb_info.get("data", {})
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        last_heartbeat = ts_str
                        if (now - ts).total_seconds() < hb_timeout:
                            online = True
                            online_count += 1
                    except (ValueError, TypeError):
                        pass

            devices.append({
                "id": act.id,
                "name": act.name,
                "mqtt_device_name": act.mqtt_device_name,
                "description": act.description,
                "online": online,
                "last_heartbeat": last_heartbeat,
                "heartbeat_data": heartbeat_data,
            })

        return {
            "devices": devices,
            "total": len(actuators),
            "online": online_count,
            "pending_commands": pending_commands,
            "unsynced_commands": unsynced_commands,
        }

    # Alert count for frontend bell indicator
    @app.get("/health/alerts", tags=["health"])
    async def health_alerts(since: str | None = None):
        from datetime import UTC, datetime, timedelta
        from app.models.event import EventLog

        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                since_dt = datetime.now(UTC) - timedelta(hours=1)
        else:
            since_dt = datetime.now(UTC) - timedelta(hours=1)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count()).select_from(EventLog).where(
                    EventLog.level.in_(["WARNING", "ERROR"]),
                    EventLog.timestamp >= since_dt,
                )
            )
            count = result.scalar() or 0

        return {"count": count}

    # Global exception handler
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
