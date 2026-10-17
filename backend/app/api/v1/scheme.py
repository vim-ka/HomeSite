from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.settings_repository import SettingsRepository
from app.services.scheme_service import CachedFetch, SchemeService, fetch_gateway_health

router = APIRouter()

# One shared, briefly cached gateway /health per (url, timeout) — see CachedFetch
_gateway_cache: dict[tuple[str, float], CachedFetch] = {}


@router.get("/state")
async def scheme_state(
    request: Request,
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

    key = (url, timeout)
    if key not in _gateway_cache:
        async def fetch():
            return await fetch_gateway_health(url, timeout)

        _gateway_cache[key] = CachedFetch(fetch)
    state = await SchemeService(db, _gateway_cache[key]).build_state()
    # alarms: what the HealthMonitor raised (delays, hysteresis) — the same list the event log follows
    monitor = getattr(request.app.state, "health_monitor", None)
    state["alarms"] = list(monitor.state.active_alarms) if monitor else []
    # efficiency advice (not alarms): averaged over steady operation, also by the HealthMonitor
    state["advice"] = list(getattr(monitor.state, "active_advice", [])) if monitor else []
    return state
