import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.config import get_settings as get_app_settings
from app.db.session import get_db
from app.models.event import EventLog
from app.models.user import User, UserRole
from app.repositories.settings_repository import SettingsRepository
from app.schemas.settings import (
    BackupResponse,
    BackupScheduleRequest,
    BackupScheduleResponse,
    DatabaseInfoResponse,
    DatabaseUpdateRequest,
    MqttSettingsRequest,
    MqttSettingsResponse,
    SettingResponse,
    SettingUpdateRequest,
    ToggleRequest,
    ToggleResponse,
)
from app.services.backup_service import BackupService
from app.services.gateway_client import GatewayClient
from app.api.v1.ws import manager as ws_manager
from app.services.settings_service import SettingsService

router = APIRouter()


def get_settings_service(db: AsyncSession = Depends(get_db)) -> SettingsService:
    return SettingsService(SettingsRepository(db), GatewayClient())


def get_backup_service(db: AsyncSession = Depends(get_db)) -> BackupService:
    return BackupService(SettingsRepository(db))


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
    db: AsyncSession = Depends(get_db),
):
    """Update settings and dispatch to DeviceGateway. RBAC: admin/operator."""
    await service.update_settings(payload.settings)

    summary = ", ".join(f"{k}={v}" for k, v in payload.settings.items())
    db.add(EventLog(
        level="INFO",
        source="settings",
        method="PUT",
        path="/api/v1/settings",
        message=f"Settings updated: {summary}",
        user_id=user.id,
    ))

    # Notify all WebSocket clients about the settings change
    await ws_manager.broadcast({
        "type": "settings_update",
        "settings": {k: str(v) for k, v in payload.settings.items()},
    })

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
    db: AsyncSession = Depends(get_db),
):
    """Update MQTT broker settings and signal gateway to reconnect. Admin only."""
    result = await service.update_mqtt_settings(payload.host, payload.port, payload.user, payload.password)
    db.add(EventLog(
        level="INFO", source="settings", method="PUT", path="/api/v1/settings/mqtt",
        message=f"Обновлены настройки MQTT: host={payload.host}, port={payload.port}",
        user_id=user.id,
    ))
    return result


@router.post("/retry-unsynced")
async def retry_unsynced(
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.OPERATOR])),
):
    """Re-send all unsynced commands to devices."""
    client = GatewayClient()
    retried = await client.retry_unsynced()
    return {"retried": retried}


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


# --- Database info ---


def _mask_url(url: str) -> str:
    """Mask password in database URL for display."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)


@router.get("/database", response_model=DatabaseInfoResponse)
async def get_database_info(
    user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get database type and masked connection URL. Admin only."""
    settings = get_app_settings()
    db_type = "sqlite" if settings.is_sqlite else "postgresql"
    return DatabaseInfoResponse(type=db_type, url=_mask_url(settings.database_url))


@router.put("/database")
async def update_database(
    payload: DatabaseUpdateRequest,
    user: User = Depends(require_role([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Save new database URL after validating connection. Requires app restart. Admin only."""
    if payload.type == "sqlite":
        new_url = f"sqlite+aiosqlite:///{payload.path}"
    else:
        new_url = (
            f"postgresql+asyncpg://{payload.user}:{payload.password}"
            f"@{payload.host}:{payload.port}/{payload.dbname}"
        )

    # Validate connection before saving, and check whether the target DB
    # already has tables. If empty, the UI must warn the admin that switching
    # will land on a bare DB until `alembic upgrade head` + data migration.
    target_is_empty = False
    from sqlalchemy.ext.asyncio import create_async_engine as _create_engine
    from sqlalchemy import text as _text
    test_engine = _create_engine(new_url, pool_pre_ping=True)
    try:
        async with test_engine.connect() as conn:
            await conn.execute(_text("SELECT 1"))
            if payload.type == "postgresql":
                count_q = _text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            else:
                count_q = _text(
                    "SELECT COUNT(*) FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            result = await conn.execute(count_q)
            target_is_empty = (result.scalar() or 0) == 0
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot connect to {payload.type}: {str(e)}",
        )
    finally:
        await test_engine.dispose()

    env_path = ".env"
    lines: list[str] = []
    found = False
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    lines.append(f"DATABASE_URL={new_url}\n")
                    found = True
                else:
                    lines.append(line)
    except FileNotFoundError:
        lines = []

    if not found:
        lines.append(f"DATABASE_URL={new_url}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    db.add(EventLog(
        level="INFO", source="settings", method="PUT", path="/api/v1/settings/database",
        message=f"Обновлена конфигурация БД: type={payload.type}",
        user_id=user.id,
    ))
    return {
        "success": True,
        "restart_required": True,
        "target_is_empty": target_is_empty,
    }


# --- Backup ---


@router.post("/backup", response_model=BackupResponse)
async def create_backup(
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: BackupService = Depends(get_backup_service),
    db: AsyncSession = Depends(get_db),
):
    """Create a database backup now. Admin only."""
    result = await service.create_backup()
    db.add(EventLog(
        level="INFO", source="settings", method="POST", path="/api/v1/settings/backup",
        message=f"Создан бэкап: {result.filename}",
        user_id=user.id,
    ))
    return result


@router.get("/backups", response_model=list[BackupResponse])
async def list_backups(
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: BackupService = Depends(get_backup_service),
):
    """List all backup files. Admin only."""
    return await service.list_backups()


@router.get("/backups/{filename}")
async def download_backup(
    filename: str,
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: BackupService = Depends(get_backup_service),
):
    """Download a specific backup file. Admin only."""
    path = await service.get_backup_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


# --- Backup schedule ---


@router.get("/backup-schedule", response_model=BackupScheduleResponse)
async def get_backup_schedule(
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: BackupService = Depends(get_backup_service),
):
    """Get backup schedule settings. Admin only."""
    return await service.get_schedule()


@router.put("/backup-schedule", response_model=BackupScheduleResponse)
async def update_backup_schedule(
    payload: BackupScheduleRequest,
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: BackupService = Depends(get_backup_service),
    db: AsyncSession = Depends(get_db),
):
    """Update backup schedule. Admin only."""
    result = await service.update_schedule(payload.enabled, payload.interval, payload.time)
    db.add(EventLog(
        level="INFO", source="settings", method="PUT", path="/api/v1/settings/backup-schedule",
        message=f"Расписание бэкапов: enabled={payload.enabled}, {payload.interval} {payload.time}",
        user_id=user.id,
    ))
    return result
