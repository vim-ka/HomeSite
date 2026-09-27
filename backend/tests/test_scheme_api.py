import pytest

from app.core.security import get_password_hash
from app.models.config import ConfigKV
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_scheme_state_requires_login(client):
    assert (await client.get("/api/v1/scheme/state")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_scheme_state_for_viewer(client, db_session):
    db_session.add_all([
        User(username="viewer", password_hash=get_password_hash("viewer123"), email="v@test.com",
             role=UserRole.VIEWER.value),
        ConfigKV(key="mqtt_pass", value="secret"),
        ConfigKV(key="device_gateway_url", value="http://127.0.0.1:9"),
    ])
    await db_session.commit()
    token = (await client.post("/api/v1/auth/login", json={"username": "viewer", "password": "viewer123"})).json()["access_token"]
    resp = await client.get("/api/v1/scheme/state", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["controller"]["online"] is False          # no gateway in tests
    assert "mqtt_pass" not in body["settings"]
    assert set(body) >= {"values", "controller", "settings", "sync", "alarms", "events", "stale_minutes"}


@pytest.mark.asyncio
async def test_scheme_alarms_are_the_monitors_active_alarms(client, db_session):
    """One source of truth: the panel shows what the HealthMonitor raised (with its delays)."""
    from types import SimpleNamespace

    from app.main import app

    active = [{"code": "room:Детская", "level": "ERROR", "text": "Холодно в помещении «Детская»: 9.0 °C"}]
    db_session.add(User(username="v2", password_hash=get_password_hash("viewer123"), email="v2@test.com",
                        role=UserRole.VIEWER.value))
    await db_session.commit()
    app.state.health_monitor = SimpleNamespace(state=SimpleNamespace(active_alarms=active))
    try:
        token = (await client.post("/api/v1/auth/login", json={"username": "v2", "password": "viewer123"})).json()["access_token"]
        body = (await client.get("/api/v1/scheme/state", headers={"Authorization": f"Bearer {token}"})).json()
        assert body["alarms"] == active
    finally:
        del app.state.health_monitor
