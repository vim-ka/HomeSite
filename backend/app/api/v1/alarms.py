"""Active alarms (raised by the HealthMonitor), acknowledgement and silencing the controller's buzzer."""

from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.event import EventLog
from app.models.user import User, UserRole

router = APIRouter()

CONTROLLER_DEVICE = "boiler_unit"
operator = require_role([UserRole.ADMIN, UserRole.OPERATOR])


class AckRequest(BaseModel):
    code: str


def _monitor(request: Request):
    monitor = getattr(request.app.state, "health_monitor", None)
    if monitor is None:
        raise HTTPException(status_code=503, detail="Мониторинг не запущен")
    return monitor


@router.get("")
async def active_alarms(request: Request, user: User = Depends(get_current_user)) -> dict:
    """Alarms active right now, most severe first, with `since` and `acked`."""
    return {"alarms": list(_monitor(request).state.active_alarms)}


@router.post("/ack")
async def acknowledge(
    body: AckRequest, request: Request,
    user: User = Depends(operator), db: AsyncSession = Depends(get_db),
) -> dict:
    """A person has seen the alarm: it stops nagging until it gets worse or comes back."""
    monitor = _monitor(request)
    alarm = monitor.alarms.active.get(body.code)
    if alarm is None or not monitor.alarms.ack(body.code):
        raise HTTPException(status_code=404, detail="Авария уже снята")
    monitor.state = replace(monitor.state, active_alarms=monitor.alarms.active_list())
    db.add(EventLog(level="INFO", source="alarms", message=f"Авария подтверждена: {alarm.text}", user_id=user.id))
    await db.commit()
    return {"status": "ok"}


@router.post("/buzzer-mute")
async def buzzer_mute(user: User = Depends(operator), db: AsyncSession = Depends(get_db)) -> dict:
    """Silence the controller's alarm lamp + buzzer until a NEW critical cause appears."""
    from app.services.gateway_client import GatewayClient

    if not await GatewayClient().dispatch_command(CONTROLLER_DEVICE, {"buzzer_mute": "1"}):
        raise HTTPException(status_code=502, detail="Шлюз недоступен")
    db.add(EventLog(level="INFO", source="alarms", message="Зуммер аварии отключён", user_id=user.id))
    await db.commit()
    return {"status": "ok"}
