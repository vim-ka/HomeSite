"""Admin API of the SMS section: journal, status, retry, keys, test SMS."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.config import ConfigKV
from app.models.event import EventLog
from app.models.sms import SmsItem, SmsMessage
from app.models.user import User, UserRole

PHONE = "+79990000001"


async def _token(client, db_session, role: UserRole, phone: str | None = None) -> dict:
    name = f"u_{role.value}"
    db_session.add(User(username=name, password_hash=get_password_hash("pass12345"), email=f"{name}@t.com",
                        role=role.value, phone=phone))
    await db_session.commit()
    token = (await client.post("/api/v1/auth/login", json={"username": name, "password": "pass12345"})).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _item(db, user_id, n, **kw) -> SmsItem:
    now = datetime.now(UTC)
    values = dict(problem="pressure", code="pressure", level="ERROR", raised=True, kind="first", user_id=user_id,
                  phone=PHONE, text=f"СМС {n}", is_test=False, state="pending",
                  created_at=now - timedelta(minutes=100 - n), ready_at=now)
    values.update(kw)
    it = SmsItem(**values)
    db.add(it)
    await db.commit()
    return it


async def _msg(db, state="failed", items=1, **kw) -> SmsMessage:
    now = datetime.now(UTC)
    values = dict(phone=PHONE, text="m", is_test=False, state=state, items=items, attempts=3, error="boom",
                  created_at=now, ready_at=now)
    values.update(kw)
    m = SmsMessage(**values)
    db.add(m)
    await db.commit()
    return m


@pytest.mark.asyncio
async def test_log_paginates_and_filters(client, db_session):
    headers = await _token(client, db_session, UserRole.ADMIN, PHONE)
    uid = (await db_session.execute(select(User.id))).scalar_one()
    for n in range(55):
        await _item(db_session, uid, n)
    await _item(db_session, uid, 60, code="well", state="superseded")
    await _item(db_session, uid, 61, is_test=True, kind="test", code="test")
    await _item(db_session, None, 62, state="not_needed")

    body = (await client.get("/api/v1/sms/log", headers=headers)).json()
    assert body["total"] == 57 and body["page"] == 1 and len(body["items"]) == 50
    assert body["items"][0]["text"] == "СМС 62"                      # newest first
    assert body["items"][0]["user"] is None                           # deleted user
    assert body["items"][0]["status"] == "не нужна"
    assert body["items"][1]["status"] == "заменена"
    first = body["items"][2]
    assert first["status"] == "ждёт" and first["user"] == {"id": uid, "username": "u_admin"}
    assert first["message"] is None and first["phone"] == PHONE
    assert len((await client.get("/api/v1/sms/log?page=2", headers=headers)).json()["items"]) == 7

    by_code = (await client.get("/api/v1/sms/log?code=well", headers=headers)).json()
    assert [i["code"] for i in by_code["items"]] == ["well"] and by_code["total"] == 1
    by_state = (await client.get("/api/v1/sms/log?state=superseded", headers=headers)).json()
    assert by_state["total"] == 1
    by_user = (await client.get(f"/api/v1/sms/log?user_id={uid}", headers=headers)).json()
    assert by_user["total"] == 56
    tests = (await client.get("/api/v1/sms/log?test=true", headers=headers)).json()
    assert [i["kind"] for i in tests["items"]] == ["test"]


@pytest.mark.asyncio
async def test_log_shows_merged_count(client, db_session):
    headers = await _token(client, db_session, UserRole.ADMIN, PHONE)
    uid = (await db_session.execute(select(User.id))).scalar_one()
    msg = await _msg(db_session, "failed", items=2)
    await _item(db_session, uid, 1, state="formed", message_id=msg.id)
    await _item(db_session, uid, 2, state="formed", message_id=msg.id)
    body = (await client.get("/api/v1/sms/log", headers=headers)).json()
    assert [i["status"] for i in body["items"]] == ["не ушла", "не ушла"]
    m = body["items"][0]["message"]
    assert (m["id"], m["items"], m["attempts"], m["error"]) == (msg.id, 2, 3, "boom") and m["sent_at"] is None
    for state, word in (("ready", "ждёт повтора"), ("leased", "выдана"), ("sent", "ушла")):
        msg.state = state
        await db_session.commit()
        items = (await client.get("/api/v1/sms/log", headers=headers)).json()["items"]
        assert items[0]["status"] == word


@pytest.mark.asyncio
async def test_retry_only_failed(client, db_session):
    headers = await _token(client, db_session, UserRole.ADMIN, PHONE)
    failed, sent = await _msg(db_session, "failed"), await _msg(db_session, "sent")
    assert (await client.post(f"/api/v1/sms/messages/{sent.id}/retry", headers=headers)).status_code == 409
    assert (await client.post("/api/v1/sms/messages/9999/retry", headers=headers)).status_code == 404
    assert (await client.post(f"/api/v1/sms/messages/{failed.id}/retry", headers=headers)).status_code == 200
    await db_session.refresh(failed)
    assert (failed.state, failed.attempts) == ("ready", 0)
    events = (await db_session.execute(select(EventLog))).scalars().all()
    assert any(e.message == f"Повтор СМС #{failed.id}" and e.user_id for e in events)


@pytest.mark.asyncio
async def test_issue_key_shown_once_and_works(client, db_session):
    headers = await _token(client, db_session, UserRole.ADMIN, PHONE)
    st = (await client.get("/api/v1/sms/status", headers=headers)).json()
    assert st["has_live_key"] is False and st["has_test_key"] is False and st["pending"] == 0
    assert (await client.post("/api/v1/sms/keys/bogus", headers=headers)).status_code == 404
    key = (await client.post("/api/v1/sms/keys/live", headers=headers)).json()["key"]
    ping = await client.get("/api/v1/sms/ping", headers={"Authorization": f"Bearer {key}"})
    assert ping.status_code == 200 and ping.json()["mode"] == "live"
    stored = (await db_session.execute(select(ConfigKV.value).where(ConfigKV.key.like("sms_key_live%")))).scalars().all()
    assert key not in stored and len(stored) == 2
    st = (await client.get("/api/v1/sms/status", headers=headers)).json()
    assert st["has_live_key"] is True and st["has_test_key"] is False
    tkey = (await client.post("/api/v1/sms/keys/test", headers=headers)).json()["key"]
    assert (await client.get("/api/v1/sms/ping", headers={"X-SMS-Key": tkey})).json()["mode"] == "test"
    messages = {e.message for e in (await db_session.execute(select(EventLog))).scalars()}
    assert {"Выпущен боевой ключ СМС", "Выпущен тестовый ключ СМС"} <= messages


@pytest.mark.asyncio
async def test_test_me_requires_phone(client, db_session):
    headers = await _token(client, db_session, UserRole.ADMIN)
    resp = await client.post("/api/v1/sms/test-me", headers=headers)
    assert resp.status_code == 400 and resp.json()["detail"] == "У вас не указан телефон"
    assert (await client.post("/api/v1/sms/test-queue", headers=headers)).status_code == 400
    user = (await db_session.execute(select(User))).scalar_one()
    user.phone = PHONE
    await db_session.commit()
    assert (await client.post("/api/v1/sms/test-me", headers=headers)).status_code == 200
    assert (await client.post("/api/v1/sms/test-queue", headers=headers)).status_code == 200
    items = (await db_session.execute(select(SmsItem).order_by(SmsItem.id))).scalars().all()
    assert [(i.is_test, i.kind, i.state, i.phone, i.text, i.user_id) for i in items] == [
        (False, "test", "pending", PHONE, "Тестовая СМС HomeSite", user.id),
        (True, "test", "pending", PHONE, "Тестовая СМС HomeSite", user.id)]
    assert all((i.problem, i.code, i.level, i.raised) == ("test", "test", "INFO", True) for i in items)
    messages = {e.message for e in (await db_session.execute(select(EventLog))).scalars()}
    assert "Тестовая СМС поставлена в очередь" in messages


@pytest.mark.asyncio
async def test_viewer_and_operator_forbidden(client, db_session):
    calls = [("GET", "/sms/log"), ("GET", "/sms/status"), ("POST", "/sms/messages/1/retry"),
             ("POST", "/sms/keys/live"), ("POST", "/sms/test-me"), ("POST", "/sms/test-queue")]
    for role in (UserRole.VIEWER, UserRole.OPERATOR):
        headers = await _token(client, db_session, role, PHONE)
        for method, path in calls:
            assert (await client.request(method, "/api/v1" + path, headers=headers)).status_code == 403, (role, path)


@pytest.mark.asyncio
async def test_phone_swagger_stays_phone_only(client):
    paths = (await client.get("/api/v1/sms/openapi.json")).json()["paths"]
    assert sorted(paths) == ["/api/v1/sms/done", "/api/v1/sms/next", "/api/v1/sms/ping"]
