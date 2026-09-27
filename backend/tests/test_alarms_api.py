"""/api/v1/alarms — the active alarms, acknowledgement, silencing the controller's buzzer."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.main import app
from app.models.event import EventLog
from app.models.user import User, UserRole
from app.services.alarm_rules import Alarm, AlarmTracker
from app.services.health_monitor import HealthState

NOW = datetime(2026, 1, 20, 3, 0, tzinfo=UTC)


@pytest.fixture
def monitor():
    tracker = AlarmTracker()
    tracker.update([Alarm("room:Детская", "ERROR", "Холодно в помещении «Детская»: 9.0 °C")], NOW)
    m = SimpleNamespace(alarms=tracker, state=HealthState(active_alarms=tracker.active_list()))
    app.state.health_monitor = m
    yield m
    del app.state.health_monitor


async def _token(client, db_session, role: UserRole) -> dict:
    name = f"u_{role.value}"
    db_session.add(User(username=name, password_hash=get_password_hash("pass12345"), email=f"{name}@t.com",
                        role=role.value))
    await db_session.commit()
    token = (await client.post("/api/v1/auth/login", json={"username": name, "password": "pass12345"})).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_anyone_logged_in_sees_the_active_alarms(client, db_session, monitor):
    assert (await client.get("/api/v1/alarms")).status_code in (401, 403)
    headers = await _token(client, db_session, UserRole.VIEWER)
    body = (await client.get("/api/v1/alarms", headers=headers)).json()
    assert [(a["code"], a["acked"]) for a in body["alarms"]] == [("room:Детская", False)]


@pytest.mark.asyncio
async def test_operator_acknowledges_an_alarm(client, db_session, monitor):
    headers = await _token(client, db_session, UserRole.OPERATOR)
    resp = await client.post("/api/v1/alarms/ack", json={"code": "room:Детская"}, headers=headers)
    assert resp.status_code == 200
    assert monitor.state.active_alarms[0]["acked"] is True          # visible right away, not at the next poll
    events = (await db_session.execute(select(EventLog))).scalars().all()
    assert any(e.message == "Авария подтверждена: Холодно в помещении «Детская»: 9.0 °C" for e in events)
    assert (await client.post("/api/v1/alarms/ack", json={"code": "nope"}, headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_viewer_cannot_acknowledge(client, db_session, monitor):
    headers = await _token(client, db_session, UserRole.VIEWER)
    assert (await client.post("/api/v1/alarms/ack", json={"code": "room:Детская"}, headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_operator_silences_the_buzzer(client, db_session, monitor, monkeypatch):
    sent = []

    async def dispatch(self, device, params):
        sent.append((device, params))
        return True

    monkeypatch.setattr("app.services.gateway_client.GatewayClient.dispatch_command", dispatch)
    headers = await _token(client, db_session, UserRole.OPERATOR)
    assert (await client.post("/api/v1/alarms/buzzer-mute", headers=headers)).status_code == 200
    assert sent == [("boiler_unit", {"buzzer_mute": "1"})]

    async def fail(self, device, params):
        return False

    monkeypatch.setattr("app.services.gateway_client.GatewayClient.dispatch_command", fail)
    assert (await client.post("/api/v1/alarms/buzzer-mute", headers=headers)).status_code == 502
