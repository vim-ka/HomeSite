"""Phone API: /api/v1/sms/ping|next|done with the SMS key, and its own Swagger page (works without debug)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.config import ConfigKV
from app.models.sms import SmsItem
from app.models.user import User
from app.services.sms_queue import issue_key

PHONE = "+79990000001"


async def add_pending(db, text: str = "Низкое давление", is_test: bool = False) -> SmsItem:
    u = (await db.execute(select(User).where(User.username == "a"))).scalar_one_or_none()
    if u is None:
        u = User(username="a", password_hash="x", email="a@x", role="viewer", phone=PHONE,
                 sms_categories="critical,test")
        db.add(u)
        await db.commit()
    now = datetime.now(UTC)
    it = SmsItem(problem="test" if is_test else "pressure", code="pressure", level="ERROR", raised=True,
                 kind="test" if is_test else "first", user_id=u.id, phone=PHONE, text=text, is_test=is_test,
                 state="pending", created_at=now - timedelta(minutes=2), ready_at=now - timedelta(minutes=1))
    db.add(it)
    await db.commit()
    return it


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest.mark.asyncio
async def test_sms_docs_available_without_debug():
    # production: debug off → the app-wide /docs and /openapi.json are disabled; the phone's Swagger still works
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.sms import router

    prod = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    prod.include_router(router, prefix="/api/v1/sms")
    async with AsyncClient(transport=ASGITransport(app=prod), base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == 404
        await _check_phone_docs(client)


@pytest.mark.asyncio
async def test_sms_docs_in_main_app(client):
    await _check_phone_docs(client)


async def _check_phone_docs(client) -> None:
    r = await client.get("/api/v1/sms/docs")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "/api/v1/sms/openapi.json" in r.text
    assert "swagger-ui-dist@5.17.14" in r.text
    r = await client.get("/api/v1/sms/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert set(spec["paths"]) == {"/api/v1/sms/ping", "/api/v1/sms/next", "/api/v1/sms/done"}
    schemes = spec["components"]["securitySchemes"]
    assert any(s.get("type") == "http" and s.get("scheme") == "bearer" for s in schemes.values())
    assert any(s.get("type") == "apiKey" and s.get("in") == "header" and s.get("name") == "X-SMS-Key"
               for s in schemes.values())


@pytest.mark.asyncio
async def test_no_key_401(client, db_session):
    await issue_key(db_session, "live")
    for method, path in (("get", "ping"), ("get", "next"), ("post", "done")):
        kwargs = {"json": {"id": 1, "ok": True}} if method == "post" else {}
        r = await getattr(client, method)(f"/api/v1/sms/{path}", **kwargs)
        assert r.status_code == 401, path
    r = await client.get("/api/v1/sms/ping", headers=bearer("wrong"))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_key_in_query_401(client, db_session):
    key = await issue_key(db_session, "live")
    for param in ("key", "api_key", "token", "X-SMS-Key"):
        r = await client.get("/api/v1/sms/ping", params={param: key})
        assert r.status_code == 401, param


@pytest.mark.asyncio
async def test_bearer_and_x_sms_key_both_work(client, db_session):
    live = await issue_key(db_session, "live")
    test = await issue_key(db_session, "test")
    r = await client.get("/api/v1/sms/ping", headers=bearer(live))
    assert r.status_code == 200
    body = r.json()
    assert {k: v for k, v in body.items() if k != "quiet"} == {"mode": "live", "queue": 0, "poll_after": 60}
    assert isinstance(body["quiet"], bool)   # default quiet hours: depends on the clock
    r = await client.get("/api/v1/sms/ping", headers={"X-SMS-Key": test})
    assert r.status_code == 200 and r.json()["mode"] == "test"


@pytest.mark.asyncio
async def test_ping_queue_quiet_and_poll_after(client, db_session):
    key = await issue_key(db_session, "live")
    db_session.add_all([ConfigKV(key="sms_poll_seconds", value="90"),
                        ConfigKV(key="sms_quiet_start", value="00:00"),
                        ConfigKV(key="sms_quiet_end", value="23:59")])
    await db_session.commit()
    await add_pending(db_session)
    await add_pending(db_session, "Тест", is_test=True)
    r = await client.get("/api/v1/sms/ping", headers=bearer(key))
    body = r.json()
    assert body["queue"] == 1 and body["poll_after"] == 90
    now = datetime.now(UTC)
    assert body["quiet"] is (now.hour * 60 + now.minute < 23 * 60 + 59)


@pytest.mark.asyncio
async def test_next_and_done_flow(client, db_session):
    key = await issue_key(db_session, "live")
    await add_pending(db_session)
    r = await client.get("/api/v1/sms/next", headers=bearer(key))
    assert r.status_code == 200
    body = r.json()
    assert body["to"] == PHONE and body["text"] == "Низкое давление" and body["poll_after"] == 60
    assert isinstance(body["id"], int)
    r = await client.post("/api/v1/sms/done", headers=bearer(key), json={"id": body["id"], "ok": True})
    assert r.status_code == 200 and r.json() == {"ok": True, "poll_after": 60}


@pytest.mark.asyncio
async def test_next_204_has_x_poll_after(client, db_session):
    key = await issue_key(db_session, "live")
    r = await client.get("/api/v1/sms/next", headers=bearer(key))
    assert r.status_code == 204
    assert r.headers["X-Poll-After"] == "60"
    assert r.content == b""


@pytest.mark.asyncio
async def test_done_unknown_404(client, db_session):
    live = await issue_key(db_session, "live")
    test = await issue_key(db_session, "test")
    r = await client.post("/api/v1/sms/done", headers=bearer(live), json={"id": 999, "ok": True})
    assert r.status_code == 404
    await add_pending(db_session)
    msg_id = (await client.get("/api/v1/sms/next", headers=bearer(live))).json()["id"]
    r = await client.post("/api/v1/sms/done", headers=bearer(test), json={"id": msg_id, "ok": True})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_done_repeat_200(client, db_session):
    key = await issue_key(db_session, "live")
    await add_pending(db_session)
    msg_id = (await client.get("/api/v1/sms/next", headers=bearer(key))).json()["id"]
    for _ in range(2):
        r = await client.post("/api/v1/sms/done", headers={"X-SMS-Key": key},
                              json={"id": msg_id, "ok": False, "error": "нет сети"})
        assert r.status_code == 200
    r = await client.post("/api/v1/sms/done", headers={"X-SMS-Key": key}, json={"id": msg_id, "ok": True})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_live_request_updates_last_poll(client, db_session):
    live = await issue_key(db_session, "live")
    test = await issue_key(db_session, "test")

    async def last_poll() -> str | None:
        db_session.expire_all()
        row = (await db_session.execute(select(ConfigKV).where(ConfigKV.key == "sms_last_poll_at"))).scalar_one_or_none()
        return row.value if row else None

    await client.get("/api/v1/sms/ping", headers=bearer(test))
    assert await last_poll() is None
    before = datetime.now(UTC)
    await client.get("/api/v1/sms/next", headers=bearer(live))
    value = await last_poll()
    assert value is not None
    assert datetime.fromisoformat(value) >= before.replace(microsecond=0) - timedelta(seconds=1)
