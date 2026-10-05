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
    assert "flag:frost_protect" in [a["code"] for a in m.state.active_alarms]   # gone only just
    m._now = lambda: NOW + timedelta(seconds=121)
    _with_gateway(m, monkeypatch, gateway(hb_age_s=-116, data={**data, "frost_protect": False}))
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
    """B3: a normal 3 bar in the water main used to raise 'Давление вне нормы' every time.

    The controller stays online (its heartbeat moves with the clock) for 20 minutes — longer than every
    pressure delay — with the heating at 1.43 bar and the water main at 3.05 bar.
    """
    await seed(db_session)
    m = _monitor(engine)
    clock = {"now": NOW}
    m._now = lambda: clock["now"]

    async def fetch():
        return {"heartbeats": {"boiler_unit": {
            "timestamp": (clock["now"] - timedelta(seconds=5)).isoformat(),
            "data": {"relays": 0b11, "prs_heat": 1.43, "prs_water": 3.05, "rad_target": 54.0},
        }}, "sync": {}}

    _with_gateway(m, monkeypatch, fetch)
    for minutes in range(0, 21):
        clock["now"] = NOW + timedelta(minutes=minutes)
        await m._check()
        assert m.state.database and m.state.gateway
    assert not any("Давлен" in (e.message or "") for e in await _events(db_session))
    assert not any(a["code"].startswith("pressure") for a in m.state.active_alarms)
    assert "no_link" not in [a["code"] for a in m.state.active_alarms]


async def test_a_broken_alarm_check_is_itself_an_alarm(engine, db_session, monkeypatch):
    """If the rules crash, alarms must not silently switch off."""
    await seed(db_session)
    m = _monitor(engine)
    m._now = lambda: NOW
    _with_gateway(m, monkeypatch, gateway())

    def boom(*_a, **_k):
        raise RuntimeError("rule bug")

    monkeypatch.setattr("app.services.health_monitor.evaluate", boom)
    await m._check()
    await m._check()
    assert [a["code"] for a in m.state.active_alarms] == ["alarm_check_failed"]
    failed = [e for e in await _events(db_session) if "Проверка аварий не работает" in (e.message or "")]
    assert [e.level for e in failed] == ["ERROR"]


# ---------------------------------------------------------------- room correction: the house average to the controller
async def _forwarded(engine, db_session, monkeypatch, factor: str | None, *, fresh: bool = True) -> list[dict]:
    from app.models.config import ConfigKV

    await seed(db_session, fresh=fresh)
    if factor is not None:
        db_session.add(ConfigKV(key="heating_room_factor", value=factor))
        await db_session.commit()
    m = _monitor(engine)
    m._now = lambda: NOW
    _with_gateway(m, monkeypatch, gateway())
    sent: list[dict] = []

    async def capture(params):
        sent.append(params)

    monkeypatch.setattr(m, "_send_telemetry", capture)
    await m._check()
    return sent


async def test_the_house_average_goes_to_the_controller_while_room_correction_is_on(engine, db_session, monkeypatch):
    assert await _forwarded(engine, db_session, monkeypatch, "2") == [{"indoor_temp": "22.7"}]


async def test_no_forward_with_room_correction_off(engine, db_session, monkeypatch):
    assert await _forwarded(engine, db_session, monkeypatch, "0") == []


async def test_a_stale_house_average_is_not_forwarded(engine, db_session, monkeypatch):
    assert await _forwarded(engine, db_session, monkeypatch, "2", fresh=False) == []
