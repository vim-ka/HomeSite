from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.router import api_v1_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import engine, AsyncSessionLocal

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("application_startup", env=settings.app_env)
    yield
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
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
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

    # Global exception handler
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
