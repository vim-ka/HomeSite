"""HealthMonitor: device safety alarms, resilience."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.event import EventLog
from app.models.heating import HeatingCircuit
from app.services.health_monitor import HealthMonitor


def _monitor(engine):
    return HealthMonitor(async_sessionmaker(engine, expire_on_commit=False), gateway_url="http://127.0.0.1:9")


@pytest.mark.asyncio
async def test_duplicate_boiler_prefix_does_not_break_monitoring(engine, db_session):
    """Two circuits with config_prefix=heating_boiler used to raise on every poll."""
    db_session.add_all([
        HeatingCircuit(circuit_name="A", config_prefix="heating_boiler"),
        HeatingCircuit(circuit_name="B", config_prefix="heating_boiler"),
    ])
    await db_session.commit()
    m = _monitor(engine)
    await m._check()
    m._initialized = True
    await m._check()  # must not raise
    assert m.state.database is True
    assert m.state.gateway is False


@pytest.mark.asyncio
async def test_failure_marks_database_down(engine, monkeypatch):
    m = _monitor(engine)
    await m._check()
    assert m.state.database is True

    async def boom():
        raise RuntimeError("db gone")

    monkeypatch.setattr(m, "_check", boom)
    monkeypatch.setattr("app.services.health_monitor.asyncio.sleep", _stop_after_one)
    with pytest.raises(_Stop):
        await m.run()
    assert m.state.database is False


class _Stop(Exception):
    pass


async def _stop_after_one(_seconds):
    raise _Stop


# ---------------------------------------------------------------- alarms through the tracker
from datetime import timedelta  # noqa: E402

from tests.test_scheme_service import NOW, gateway, seed  # noqa: E402


def _with_gateway(m, monkeypatch, fetch):
    async def services(_session, _timeout=3.0):
        payload = await fetch()
        return {"database": True, "gateway": True, "mqtt": True}, payload
    monkeypatch.setattr(m, "_check_services", services)


async def _events(db_session) -> list[EventLog]:
    db_session.expire_all()
    return list((await db_session.execute(select(EventLog).order_by(EventLog.id))).scalars())


async def test_controller_flag_is_logged_and_cleared(engine, db_session, monkeypatch):
    await seed(db_session)
    m = _monitor(engine)
    m._now = lambda: NOW
    data = {"relays": 0b11, "prs_heat": 1.43, "frost_protect": True}
    _with_gateway(m, monkeypatch, gateway(data=data))
    await m._check()
    assert "flag:frost_protect" in [a["code"] for a in m.state.active_alarms]
    raised = [e for e in await _events(db_session) if "замерзания" in (e.message or "")]
    assert [e.level for e in raised] == ["ERROR"]

    _with_gateway(m, monkeypatch, gateway(data={**data, "frost_protect": False}))
    await m._check()
    assert "flag:frost_protect" not in [a["code"] for a in m.state.active_alarms]
    assert any(e.level == "INFO" and (e.message or "").startswith("Снято:") for e in await _events(db_session))


async def test_controller_silent_since_startup_is_logged_after_the_delay(engine, db_session, monkeypatch):
    """B7: a controller that never sent a heartbeat since start used to go unnoticed."""
    await seed(db_session)
    m = _monitor(engine)
    _with_gateway(m, monkeypatch, gateway(hb_age_s=None))
    m._now = lambda: NOW
    await m._check()
    assert not any("Нет связи с контроллером" in (e.message or "") for e in await _events(db_session))
    m._now = lambda: NOW + timedelta(seconds=61)
    await m._check()
    assert any(e.level == "ERROR" and "Нет связи с контроллером" in (e.message or "") for e in await _events(db_session))


async def test_silent_sensor_is_reported_in_russian_with_its_place(engine, db_session, monkeypatch):
    await seed(db_session)
    m = _monitor(engine)
    _with_gateway(m, monkeypatch, gateway())
    m._now = lambda: NOW
    await m._check()
    m._now = lambda: NOW + timedelta(minutes=10)
    await m._check()
    texts = [e.message or "" for e in await _events(db_session)]
    assert any(t.startswith("Датчик «Камин» (clm_gost_th) не присылает данные") for t in texts)
    assert not any("stopped responding" in t for t in texts)


async def test_water_pressure_is_not_judged_by_heating_limits(engine, db_session, monkeypatch):
    """B3: a normal 3 bar in the water main used to raise 'Давление вне нормы' every time."""
    await seed(db_session)
    m = _monitor(engine)
    _with_gateway(m, monkeypatch, gateway())   # prs_water 3.05 in the heartbeat
    for minutes in (0, 5, 11, 20):
        m._now = lambda minutes=minutes: NOW + timedelta(minutes=minutes, seconds=-60)
        await m._check()
    assert not any("Давлен" in (e.message or "") for e in await _events(db_session))
