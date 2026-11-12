"""Phone number and SMS categories per user."""

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.event import EventLog
from app.models.user import User, UserRole
from app.services.sms_text import normalize_phone


def test_normalize_phone():
    assert normalize_phone("8 (900) 123-45-67") == "+79001234567"
    assert normalize_phone("+7 900 1234567") == "+79001234567"
    assert normalize_phone("79001234567") == "+79001234567"
    with pytest.raises(ValueError):
        normalize_phone("12345")


async def _user(db_session, role: UserRole) -> User:
    name = f"u_{role.value}"
    u = User(username=name, password_hash=get_password_hash("pass12345"), email=f"{name}@t.com", role=role.value)
    db_session.add(u)
    await db_session.commit()
    return u


async def _headers(client, name: str) -> dict:
    r = await client.post("/api/v1/auth/login", json={"username": name, "password": "pass12345"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_admin_sets_phone_and_categories(client, db_session):
    admin = await _user(db_session, UserRole.ADMIN)
    h = await _headers(client, admin.username)
    r = await client.put(f"/api/v1/auth/users/{admin.id}/sms", headers=h,
                         json={"phone": "89001234567", "categories": ["critical", "internet"]})
    assert r.status_code == 200
    users = (await client.get("/api/v1/auth/users", headers=h)).json()
    me = next(u for u in users if u["id"] == admin.id)
    assert me["phone"] == "+79001234567"
    assert me["sms_categories"] == ["critical", "internet"]
    log = (await db_session.execute(
        select(EventLog).where(EventLog.message.like("Изменены СМС-настройки пользователя:%"))
    )).scalars().all()
    assert len(log) == 1 and log[0].user_id == admin.id


@pytest.mark.asyncio
async def test_operator_cannot_set_sms(client, db_session):
    op = await _user(db_session, UserRole.OPERATOR)
    h = await _headers(client, op.username)
    r = await client.put(f"/api/v1/auth/users/{op.id}/sms", headers=h,
                         json={"phone": "89001234567", "categories": []})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_unknown_category_rejected(client, db_session):
    admin = await _user(db_session, UserRole.ADMIN)
    h = await _headers(client, admin.username)
    r = await client.put(f"/api/v1/auth/users/{admin.id}/sms", headers=h,
                         json={"phone": None, "categories": ["power"]})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_bad_phone_rejected(client, db_session):
    admin = await _user(db_session, UserRole.ADMIN)
    h = await _headers(client, admin.username)
    r = await client.put(f"/api/v1/auth/users/{admin.id}/sms", headers=h,
                         json={"phone": "12345", "categories": []})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_empty_phone_clears(client, db_session):
    admin = await _user(db_session, UserRole.ADMIN)
    h = await _headers(client, admin.username)
    await client.put(f"/api/v1/auth/users/{admin.id}/sms", headers=h,
                     json={"phone": "89001234567", "categories": ["test"]})
    r = await client.put(f"/api/v1/auth/users/{admin.id}/sms", headers=h, json={"phone": "", "categories": []})
    assert r.status_code == 200
    me = next(u for u in (await client.get("/api/v1/auth/users", headers=h)).json() if u["id"] == admin.id)
    assert me["phone"] is None
    assert me["sms_categories"] == []
