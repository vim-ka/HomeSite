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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.db.session import get_db
from app.services import sms_queue

router = APIRouter()

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
