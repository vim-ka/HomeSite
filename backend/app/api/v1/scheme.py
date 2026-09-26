from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.settings_repository import SettingsRepository
from app.services.scheme_service import SchemeService, fetch_gateway_health

router = APIRouter()


@router.get("/state")
async def scheme_state(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Everything the scheme page draws, in one response (any logged-in role)."""
    kv = await SettingsRepository(db).get_all()
    url = kv.get("device_gateway_url") or get_settings().device_gateway_url
    try:
        timeout = float(kv.get("gateway_timeout_seconds", "3"))
    except ValueError:
        timeout = 3.0

    async def fetch():
        return await fetch_gateway_health(url, timeout)

    return await SchemeService(db, fetch).build_state()
