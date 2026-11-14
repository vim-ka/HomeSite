"""Admin API of the SMS section: journal, status, retry, keys, test SMS."""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.config import ConfigKV
from app.models.event import EventLog
from app.models.sms import SmsItem, SmsMessage
from app.models.user import User, UserRole

PHONE = "+79990000001"


@pytest_asyncio.fixture(autouse=True)
async def _sms_on(db_session):
    """These tests exercise the SMS API, which answers 404 while SMS is switched off."""
    db_session.add(ConfigKV(key="sms_enabled", value="1"))
    await db_session.commit()


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
    await _item(db_session, uid, 61, is_test=True, kind="test", code="test")   # legacy test-queue row: hidden
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
    for state, word in (("ready", "ждёт повтора"), ("leased", "передана телефону"), ("sent", "ушла")):
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
    assert st["has_key"] is False and st["key_issued_at"] is None and st["pending"] == 0
    old = (await client.post("/api/v1/sms/key", headers=headers)).json()["key"]
    key = (await client.post("/api/v1/sms/key", headers=headers)).json()["key"]
    assert (await client.get("/api/v1/sms/ping", headers={"X-SMS-Key": old})).status_code == 401   # replaced
    ping = await client.get("/api/v1/sms/ping", headers={"Authorization": f"Bearer {key}"})
    assert ping.status_code == 200 and ping.json()["mode"] == "live"
    stored = (await db_session.execute(select(ConfigKV.value).where(ConfigKV.key.like("sms_key_live%")))).scalars().all()
    assert key not in stored and len(stored) == 2
    st = (await client.get("/api/v1/sms/status", headers=headers)).json()
    assert st["has_key"] is True and st["key_issued_at"]
    assert (await client.post("/api/v1/sms/keys/test", headers=headers)).status_code in (404, 405)
    messages = [e.message for e in (await db_session.execute(select(EventLog))).scalars()]
    assert messages.count("Выдан новый ключ телефона СМС") == 2


@pytest.mark.asyncio
async def test_test_sms_to_typed_number(client, db_session):
    headers = await _token(client, db_session, UserRole.ADMIN)
    for bad in ({}, {"phone": ""}, {"phone": "12345"}, {"phone": "abc"}):
        assert (await client.post("/api/v1/sms/test", json=bad, headers=headers)).status_code == 422, bad
    resp = await client.post("/api/v1/sms/test", json={"phone": "8 (916) 123-45-67"}, headers=headers)
    assert resp.status_code == 200 and resp.json() == {"status": "ok", "phone": "+79161234567"}
    assert (await client.post("/api/v1/sms/test-me", headers=headers)).status_code in (404, 405)
    user = (await db_session.execute(select(User))).scalar_one()
    items = (await db_session.execute(select(SmsItem).order_by(SmsItem.id))).scalars().all()
    assert [(i.is_test, i.kind, i.state, i.phone, i.text, i.user_id) for i in items] == [
        (False, "test", "pending", "+79161234567", "Тестовая СМС HomeSite", user.id)]
    assert all((i.problem, i.code, i.level, i.raised) == ("test", "test", "INFO", True) for i in items)
    messages = {e.message for e in (await db_session.execute(select(EventLog))).scalars()}
    assert "Тестовая СМС на +79161234567 поставлена в очередь" in messages


@pytest.mark.asyncio
async def test_viewer_and_operator_forbidden(client, db_session):
    calls = [("GET", "/sms/log"), ("GET", "/sms/status"), ("POST", "/sms/messages/1/retry"),
             ("POST", "/sms/key"), ("POST", "/sms/test")]
    for role in (UserRole.VIEWER, UserRole.OPERATOR):
        headers = await _token(client, db_session, role, PHONE)
        for method, path in calls:
            assert (await client.request(method, "/api/v1" + path, headers=headers)).status_code == 403, (role, path)


@pytest.mark.asyncio
async def test_phone_swagger_stays_phone_only(client):
    paths = (await client.get("/api/v1/sms/openapi.json")).json()["paths"]
    assert sorted(paths) == ["/api/v1/sms/done", "/api/v1/sms/next", "/api/v1/sms/ping"]


@pytest.mark.asyncio
async def test_sms_switched_off_hides_the_whole_api(client, db_session):
    headers = await _token(client, db_session, UserRole.ADMIN, PHONE)
    row = (await db_session.execute(select(ConfigKV).where(ConfigKV.key == "sms_enabled"))).scalar_one()
    row.value = "0"
    await db_session.commit()
    for method, path in (("GET", "/sms/status"), ("GET", "/sms/log"), ("POST", "/sms/key"), ("GET", "/sms/ping"),
                         ("GET", "/sms/next"), ("GET", "/sms/docs"), ("GET", "/sms/openapi.json")):
        resp = await client.request(method, "/api/v1" + path, headers=headers)
        assert resp.status_code == 404, path
        assert resp.json()["detail"] == "Отправка СМС выключена"
    await db_session.delete(row)               # absent key = off (the default)
    await db_session.commit()
    assert (await client.get("/api/v1/sms/status", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_switch_through_put_settings(client, db_session):
    """The switch saved by the settings page (PUT /settings normalises a bool to "1"/"0") opens and closes the API."""
    headers = await _token(client, db_session, UserRole.ADMIN, PHONE)
    for value, code in (("false", 404), ("true", 200), ("0", 404), ("1", 200)):
        assert (await client.put("/api/v1/settings", json={"settings": {"sms_enabled": value}},
                                 headers=headers)).status_code == 200
        assert (await client.get("/api/v1/sms/status", headers=headers)).status_code == code, value
