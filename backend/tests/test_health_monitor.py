"""HealthMonitor: device safety alarms, resilience."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.event import EventLog
from app.models.heating import HeatingCircuit
from app.services.health_monitor import HealthMonitor


def _monitor(engine):
    return HealthMonitor(async_sessionmaker(engine, expire_on_commit=False), gateway_url="http://127.0.0.1:9")


def test_device_alarm_events_on_change(engine):
    m = _monitor(engine)
    events: list[EventLog] = []
    m._check_device_alarms({"boiler_unit": {"data": {"autofill_fault": False}}}, events)
    m._initialized = True

    m._check_device_alarms({"boiler_unit": {"data": {"autofill_fault": True}}}, events)
    assert [e.level for e in events] == ["ERROR"]
    assert "Автоподпитка" in events[0].message

    m._check_device_alarms({"boiler_unit": {"data": {"autofill_fault": True}}}, events)
    assert len(events) == 1  # no repeat while the flag stays set

    m._check_device_alarms({"boiler_unit": {"data": {"autofill_fault": False}}}, events)
    assert events[-1].level == "INFO"


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


def test_new_controller_flags_are_logged_with_their_level(engine):
    m = _monitor(engine)
    events: list[EventLog] = []
    m._check_device_alarms({"boiler_unit": {"data": {}}}, events)
    m._initialized = True
    m._check_device_alarms({"boiler_unit": {"data": {"frost_protect": True, "ihb_sensor_lost": True}}}, events)
    by_text = {e.message: e.level for e in events}
    assert any("замерзания" in t and lvl == "ERROR" for t, lvl in by_text.items())
    assert any("бойлера ГВС" in t and lvl == "WARNING" for t, lvl in by_text.items())
