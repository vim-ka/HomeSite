from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from app.api.router import api_v1_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import engine, AsyncSessionLocal

settings = get_settings()
logger = get_logger(__name__)


async def ensure_config_kv_populated() -> None:
    """Seed MQTT + tuning keys into config_kv from .env if missing (for existing deployments)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT key FROM config_kv WHERE key = 'mqtt_host'")
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
            "rate_limit_default": settings.rate_limit_default,
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
            await session.execute(
                text("INSERT OR IGNORE INTO config_kv (key, value) VALUES (:key, :value)"),
                {"key": key, "value": value},
            )
        await session.commit()
        logger.info("config_kv_bootstrapped_from_env")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    import asyncio
    from app.services.health_monitor import HealthMonitor

    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
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
