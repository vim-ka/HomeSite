"""Phone API: the Android phone (MacroDroid) polls ping/next/done with the SMS key and sends what it gets.

The key goes in `Authorization: Bearer <key>` or `X-SMS-Key` — never in the URL. The live key sees live
messages, the test key only test ones. These three endpoints have their own Swagger page (`/sms/docs`), which
works on production too, where the app-wide `/docs` is off."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.event import EventLog
from app.models.sms import SmsItem, SmsMessage
from app.models.user import User, UserRole
from app.services import sms_queue

router = APIRouter()
admin = require_role([UserRole.ADMIN])

_bearer = HTTPBearer(auto_error=False, description="Ключ СМС-API (боевой или тестовый)")
_x_key = APIKeyHeader(name="X-SMS-Key", auto_error=False, description="Ключ СМС-API (боевой или тестовый)")

PHONE_PATHS = ("/ping", "/next", "/done")
SWAGGER_UI = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14"


class PingOut(BaseModel):
    mode: str
    queue: int
    quiet: bool
    poll_after: int


class NextOut(BaseModel):
    id: int
    to: str
    text: str
    poll_after: int


class DoneIn(BaseModel):
    id: int
    ok: bool
    error: str | None = None


class DoneOut(BaseModel):
    ok: bool
    poll_after: int


async def phone_mode(
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_key: str | None = Depends(_x_key),
    db: AsyncSession = Depends(get_db),
) -> str:
    """The key's mode ("live" / "test"); 401 otherwise. A live request counts as the phone's poll."""
    key = (bearer.credentials if bearer else None) or x_key or ""
    mode = await sms_queue.key_mode(db, key)
    if mode is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный ключ СМС",
                            headers={"WWW-Authenticate": "Bearer"})
    if mode == "live":
        await sms_queue.touch_poll(db, datetime.now(UTC))
    return mode


@router.get("/ping", response_model=PingOut, summary="Проверка ключа и очереди")
@limiter.limit("60/minute")
async def ping(request: Request, mode: str = Depends(phone_mode), db: AsyncSession = Depends(get_db)):
    now = datetime.now(UTC)
    return PingOut(mode=mode, queue=await sms_queue.queue_size(db, mode == "test"),
                   quiet=await sms_queue.quiet_now(db, now), poll_after=await sms_queue.poll_seconds(db))


@router.get("/next", response_model=NextOut, summary="Следующая СМС (204 — нечего слать)",
            responses={204: {"description": "Очередь пуста; через сколько секунд спросить — в `X-Poll-After`"}})
@limiter.limit("60/minute")
async def next_sms(request: Request, mode: str = Depends(phone_mode), db: AsyncSession = Depends(get_db)):
    poll = await sms_queue.poll_seconds(db)
    msg = await sms_queue.next_message(db, mode == "test", datetime.now(UTC))
    if msg is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"X-Poll-After": str(poll)})
    return NextOut(id=msg.id, to=msg.phone, text=msg.text, poll_after=poll)


@router.post("/done", response_model=DoneOut, summary="Отчёт телефона: ушла / не ушла",
             responses={404: {"description": "Нет такой СМС для этого ключа"}})
@limiter.limit("60/minute")
async def done(request: Request, payload: DoneIn, mode: str = Depends(phone_mode),
               db: AsyncSession = Depends(get_db)):
    found = await sms_queue.mark_done(db, payload.id, mode == "test", payload.ok, payload.error, datetime.now(UTC))
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Нет такой СМС для этого ключа")
    return DoneOut(ok=True, poll_after=await sms_queue.poll_seconds(db))


@router.get("/openapi.json", include_in_schema=False)
async def phone_openapi(request: Request) -> JSONResponse:
    prefix = request.scope["route"].path.removesuffix("/openapi.json")   # e.g. /api/v1/sms
    wanted = {prefix + p for p in PHONE_PATHS}
    routes = [r for r in request.app.routes if getattr(r, "path", None) in wanted]
    return JSONResponse(get_openapi(
        title="HomeSite — API телефона СМС", version="1",
        description="Телефон-отправитель опрашивает `next`, шлёт СМС и отчитывается `done`. "
                    "Ключ — кнопка «Authorize» (`Bearer` или `X-SMS-Key`); для проверок — тестовый ключ.",
        routes=routes))


@router.get("/docs", include_in_schema=False)
async def phone_docs(request: Request) -> HTMLResponse:
    return get_swagger_ui_html(openapi_url=request.url.path.removesuffix("/docs") + "/openapi.json",
                               title="HomeSite — API телефона СМС",
                               swagger_js_url=f"{SWAGGER_UI}/swagger-ui-bundle.js",
                               swagger_css_url=f"{SWAGGER_UI}/swagger-ui.css")


# ── admin: journal, status, retry, keys, test SMS ──────────────────────────

PAGE_SIZE = 50
ITEM_STATUS = {"pending": "ждёт", "superseded": "заменена", "not_needed": "не нужна"}
MESSAGE_STATUS = {"leased": "выдана", "sent": "ушла", "failed": "не ушла", "ready": "ждёт повтора"}
TEST_TEXT = "Тестовая СМС HomeSite"
KEY_MODES = {"live": "боевой", "test": "тестовый"}


def _iso(ts: datetime | None) -> str | None:
    ts = sms_queue._utc(ts)
    return ts.isoformat() if ts else None


@router.get("/log", summary="Журнал СМС (admin)")
async def sms_log(state: str | None = None, code: str | None = None, user_id: int | None = None,
                  test: bool = False, page: int = 1, _: User = Depends(admin),
                  db: AsyncSession = Depends(get_db)) -> dict:
    page = max(1, page)
    query = (select(SmsItem, User.username, SmsMessage)
             .outerjoin(User, User.id == SmsItem.user_id)
             .outerjoin(SmsMessage, SmsMessage.id == SmsItem.message_id)
             .where(SmsItem.is_test.is_(test)))
    if state in ITEM_STATUS or state == "formed":
        query = query.where(SmsItem.state == state)
    elif state in MESSAGE_STATUS:
        query = query.where(SmsItem.state == "formed", SmsMessage.state == state)
    elif state:
        query = query.where(False)
    if code:
        query = query.where(SmsItem.code == code)
    if user_id is not None:
        query = query.where(SmsItem.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(SmsItem.created_at.desc(), SmsItem.id.desc())
                             .limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE))).all()
    items = []
    for item, username, msg in rows:
        status_text = ITEM_STATUS.get(item.state) or (MESSAGE_STATUS.get(msg.state, msg.state) if msg else item.state)
        items.append({
            "id": item.id, "created_at": _iso(item.created_at), "code": item.code, "level": item.level,
            "kind": item.kind, "text": item.text,
            "user": {"id": item.user_id, "username": username} if username is not None else None,
            "phone": item.phone, "status": status_text,
            "message": {"id": msg.id, "items": msg.items, "attempts": msg.attempts, "error": msg.error,
                        "sent_at": _iso(msg.sent_at)} if msg else None,
        })
    return {"items": items, "total": total, "page": page}


@router.get("/status", summary="Состояние телефона и ключей (admin)")
async def sms_status(_: User = Depends(admin), db: AsyncSession = Depends(get_db)) -> dict:
    out = await sms_queue.phone_status(db, datetime.now(UTC), await sms_queue.poll_seconds(db))
    for mode in KEY_MODES:
        out[f"has_{mode}_key"] = bool(await sms_queue._get(db, f"sms_key_{mode}_hash"))
    return out


@router.post("/messages/{msg_id}/retry", summary="Повторить неушедшую СМС (admin)")
async def retry_message(msg_id: int, user: User = Depends(admin), db: AsyncSession = Depends(get_db)) -> dict:
    async with sms_queue.SMS_LOCK:
        msg = await db.get(SmsMessage, msg_id)
        if msg is None:
            raise HTTPException(status_code=404, detail="Нет такой СМС")
        if msg.state != "failed":
            raise HTTPException(status_code=409, detail="Повторить можно только неушедшую СМС")
        now = datetime.now(UTC)
        await db.execute(update(SmsMessage).where(SmsMessage.id == msg_id, SmsMessage.state == "failed")
                         .values(state="ready", attempts=0, ready_at=now, leased_until=None)
                         .execution_options(synchronize_session=False))
        db.add(EventLog(level="INFO", source="sms", message=f"Повтор СМС #{msg_id}", user_id=user.id))
        await db.commit()
    return {"status": "ok"}


@router.post("/keys/{mode}", summary="Выпустить ключ (admin); показывается один раз")
async def issue_key(mode: str, user: User = Depends(admin), db: AsyncSession = Depends(get_db)) -> dict:
    if mode not in KEY_MODES:
        raise HTTPException(status_code=404, detail="Неизвестный тип ключа")
    async with sms_queue.SMS_LOCK:
        key = await sms_queue.issue_key(db, mode)
        db.add(EventLog(level="INFO", source="sms", message=f"Выпущен {KEY_MODES[mode]} ключ СМС", user_id=user.id))
        await db.commit()
    return {"key": key}


async def _enqueue_test(user: User, db: AsyncSession, is_test: bool) -> dict:
    if not user.phone:
        raise HTTPException(status_code=400, detail="У вас не указан телефон")
    now = datetime.now(UTC)
    async with sms_queue.SMS_LOCK:
        db.add(SmsItem(problem="test", code="test", level="INFO", raised=True, kind="test", user_id=user.id,
                       phone=user.phone, text=TEST_TEXT, is_test=is_test, state="pending",
                       created_at=now, ready_at=now))
        db.add(EventLog(level="INFO", source="sms", message="Тестовая СМС поставлена в очередь", user_id=user.id))
        await db.commit()
    return {"status": "ok"}


@router.post("/test-me", summary="Тестовая СМС себе, боевой очередью (admin)")
async def test_me(user: User = Depends(admin), db: AsyncSession = Depends(get_db)) -> dict:
    return await _enqueue_test(user, db, False)


@router.post("/test-queue", summary="Тестовая СМС в тестовую очередь (admin)")
async def test_queue(user: User = Depends(admin), db: AsyncSession = Depends(get_db)) -> dict:
    return await _enqueue_test(user, db, True)
