from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.settings_repository import SettingsRepository
from app.schemas.settings import (
    MqttSettingsRequest,
    MqttSettingsResponse,
    SettingResponse,
    SettingUpdateRequest,
    ToggleRequest,
    ToggleResponse,
)
from app.services.gateway_client import GatewayClient
from app.services.settings_service import SettingsService

router = APIRouter()


def get_settings_service(db: AsyncSession = Depends(get_db)) -> SettingsService:
    return SettingsService(SettingsRepository(db), GatewayClient())


@router.get("", response_model=list[SettingResponse])
async def get_all_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all Config_KV entries."""
    repo = SettingsRepository(db)
    settings = await repo.get_all()
    return [SettingResponse(key=k, value=v) for k, v in settings.items()]


@router.put("")
async def update_settings(
    payload: SettingUpdateRequest,
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.OPERATOR])),
    service: SettingsService = Depends(get_settings_service),
):
    """Update settings and dispatch to DeviceGateway. RBAC: admin/operator."""
    await service.update_settings(payload.settings)
    return {"success": True}


@router.get("/mqtt", response_model=MqttSettingsResponse)
async def get_mqtt_settings(
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: SettingsService = Depends(get_settings_service),
):
    """Get MQTT broker settings. Admin only."""
    return await service.get_mqtt_settings()


@router.put("/mqtt")
async def update_mqtt_settings(
    payload: MqttSettingsRequest,
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: SettingsService = Depends(get_settings_service),
):
    """Update MQTT broker settings. Admin only."""
    await service.update_mqtt_settings(payload.host, payload.port, payload.user, payload.password)
    return {"success": True}


@router.post("/toggle", response_model=ToggleResponse)
async def toggle_device(
    payload: ToggleRequest,
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.OPERATOR])),
    service: SettingsService = Depends(get_settings_service),
):
    """Toggle a device ON/OFF — actually dispatches via GatewayClient (fixes v1 stub)."""
    new_status = "1" if payload.toggle else "0"
    await service.update_settings({payload.id: new_status})
    return ToggleResponse(id=payload.id, status="ON" if payload.toggle else "OFF")
