"""Internal endpoints — called by DeviceGateway, not exposed to frontend.

Protected by X-Internal-Secret header.
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.api.v1.ws import manager
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter()


class SensorUpdatePayload(BaseModel):
    device_name: str
    sensor_id: int
    data: dict[str, Any]


class RfDebugPayload(BaseModel):
    device_name: str
    payload: str


def _verify_internal_secret(x_internal_secret: str = Header()) -> None:
    if x_internal_secret != settings.internal_api_secret:
        raise HTTPException(status_code=403, detail="Invalid internal secret")


@router.post("/sensor-update")
async def sensor_update(
    payload: SensorUpdatePayload,
    _: None = Depends(_verify_internal_secret),
):
    """Receive sensor update from DeviceGateway and broadcast to WebSocket clients."""
    await manager.broadcast({
        "type": "sensor_update",
        "device_name": payload.device_name,
        "sensor_id": payload.sensor_id,
        "data": payload.data,
    })

    logger.info(
        "sensor_update_broadcast",
        device=payload.device_name,
        sensor_id=payload.sensor_id,
        ws_clients=manager.active_count,
    )
    return {"broadcast": True, "clients": manager.active_count}


@router.post("/rf-debug")
async def rf_debug(
    payload: RfDebugPayload,
    _: None = Depends(_verify_internal_secret),
):
    """Receive raw RF frame from gateway and broadcast to WebSocket clients."""
    await manager.broadcast({
        "type": "rf_debug",
        "device_name": payload.device_name,
        "payload": payload.payload,
    })
    return {"broadcast": True, "clients": manager.active_count}
