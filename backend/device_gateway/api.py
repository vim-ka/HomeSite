"""Internal FastAPI for DeviceGateway — accepts commands from backend, exposes health."""

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from device_gateway.config import GatewaySettings, get_gateway_settings
from device_gateway.dispatcher import AsyncCommandDispatcher

import structlog

logger = structlog.get_logger(__name__)


class CommandRequest(BaseModel):
    device_id: str
    params: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    mqtt_connected: bool


def create_gateway_api(
    dispatcher: AsyncCommandDispatcher,
    mqtt_connected_fn: Any,
    settings: GatewaySettings | None = None,
) -> FastAPI:
    """Factory: creates internal API with injected dispatcher and health check."""
    _settings = settings or get_gateway_settings()

    app = FastAPI(title="DeviceGateway Internal API", docs_url=None, redoc_url=None)

    def verify_secret(x_internal_secret: str = Header()) -> None:
        if x_internal_secret != _settings.internal_api_secret:
            raise HTTPException(status_code=403, detail="Invalid internal secret")

    @app.post("/commands")
    async def receive_command(
        payload: CommandRequest,
        _: None = Depends(verify_secret),
    ) -> dict:
        """Accept a command from the backend and queue it for MQTT dispatch."""
        for key, value in payload.params.items():
            await dispatcher.add_param(payload.device_id, key, value)

        logger.info(
            "command_received",
            device_id=payload.device_id,
            params=list(payload.params.keys()),
        )
        return {"queued": True, "device_id": payload.device_id}

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Health check — reports MQTT connection status."""
        connected = mqtt_connected_fn()
        return HealthResponse(
            status="ok" if connected else "degraded",
            mqtt_connected=connected,
        )

    return app
