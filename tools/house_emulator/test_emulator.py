"""Behavioural tests of the emulator (no MQTT). Run: cd tools && python -m pytest house_emulator"""

import asyncio
from datetime import datetime

import pytest

from house_emulator.plant import Plant
from house_emulator.sim import Simulation

MANUAL = {
    "heating_boiler_automode": "0", "heating_boiler_power": "1",
    "heating_radiator_wbm": "0", "heating_floorheating_wbm": "0",
    "heating_radiator_temp": "50", "watersupply_ihb_temp": "55",
}


def make(settings: dict | None = None, **plant_kw) -> Simulation:
    sim = Simulation(Plant(seed=5, **plant_kw), now=datetime(2026, 1, 20, 12, 0).astimezone())
    for k, v in {**MANUAL, **(settings or {})}.items():
        assert sim.controller.on_setting(k, v) == "ok", k
    sim.warmup(2)
    return sim


def test_heated_house_stays_comfortable_in_winter():
    """Warm during the day; the default −10/−5 °C night setback cools it moderately."""
    sim = make()
    day, night = [], []
    for _ in range(36):
        sim.advance(3600)
        (night if sim.controller.schedule_rad else day).append(sim.plant.t_house)
        rooms = sim.plant.room_local
        assert rooms["clm_street_th"] < 5
        assert -5 < rooms["clm_garage_th"] < 10
    assert max(day) < 24.0 and min(day) > 19.5
    assert min(night) > 19.0
    hum = sim.plant.room_humidity(sim.now, sim.plant.room_local)
    assert 18 < hum["clm_sleep_th"] < 45  # dry winter air indoors


def test_pressure_falls_without_autofill():
    sim = make({"heating_autofill_enabled": "0"}, leak_bar_per_day=0.5)
    p0 = sim.plant.heating_pressure()
    sim.advance(24 * 3600)
    drop = p0 - sim.plant.heating_pressure()
    assert 0.35 < drop < 0.7  # leak ± thermal expansion swings


def test_autofill_holds_pressure():
    sim = make({"heating_autofill_enabled": "1", "heating_pressure_min": "1.0"}, leak_bar_per_day=1.0)
    lows = []
    for _ in range(36):
        sim.advance(3600)
        lows.append(sim.plant.heating_pressure())
    assert min(lows) > 0.9
    assert not sim.controller.autofill_fault


def test_big_leak_locks_out_autofill():
    sim = make({"heating_autofill_enabled": "1"}, leak_bar_per_day=400)  # pipe burst
    sim.advance(2 * 3600)
    assert sim.controller.autofill_fault
    assert sim.controller.critical
    assert not sim.controller.relays["af_open"]


def test_acks_mirror_firmware_validation():
    c = make().controller
    assert c.on_setting("heating_boiler_max_temp", "150") == "invalid_value"
    assert c.on_setting("no_such_key", "1") == "unknown_key"
    assert c.on_setting("heating_radiator_schedule_start", "7:30") == "ok"
    assert c.settings["heating_radiator_schedule_start"] == "07:30"


def test_lost_boiler_sensor_switches_boiler_off_in_automode():
    sim = make({"heating_boiler_automode": "1"})
    sim.failed.add("tsboiler_s")
    sim.advance(60)
    assert sim.controller.boiler_sensor_lost
    assert not sim.controller.relays["boiler"]


def test_reboot_keeps_settings_and_fault():
    sim = make({"heating_radiator_temp": "47"})
    sim.controller.autofill_fault = True
    sim.controller.reboot()
    assert sim.controller.settings["heating_radiator_temp"] == "47"
    assert sim.controller.autofill_fault
    assert not any(sim.controller.relays.values())


def test_command_handling_acks_and_restart(monkeypatch):
    import argparse

    from house_emulator.__main__ import Emulator

    args = argparse.Namespace(
        prefix="home/devices/", node="boiler_unit", rf_node="rf-gateway", speed=1, seed=1, outdoor=-12,
        leak=0.3, boiler_panel=75, prs_heating="prs_heating", prs_water="prs_water", local_outdoor=False,
        quiet=True,
    )
    emu = Emulator(args)
    sent = []

    async def fake_publish(topic, payload, qos=0):
        sent.append((topic, payload))

    monkeypatch.setattr(emu, "publish", fake_publish)
    monkeypatch.setattr(emu, "save", lambda: None)
    emu.sim.controller.t = 5000
    asyncio.run(emu.on_boiler_command({"heating_boiler_temp": "60", "heating_pressure_min": "9", "restart": "1"}))
    assert ("boiler_unit/ack", {"heating_boiler_temp": "ok", "heating_pressure_min": "invalid_value", "restart": "ok"}) in sent
    assert emu.sim.controller.t == 0  # rebooted → uptime restarts, gateway will resync
    assert emu.sim.controller.settings["heating_boiler_temp"] == "60"


def test_night_setback_lowers_valve_targets_in_manual_boiler_mode():
    """Night delta must reach the mixing valves, not only the boiler auto target."""
    sim = Simulation(Plant(seed=5), now=datetime(2026, 1, 20, 21, 0).astimezone())  # Tuesday
    for k, v in {**MANUAL, "heating_radiator_schedule_enabled": "1", "heating_radiator_schedule_days": "1,2,3,4,5",
                 "heating_radiator_schedule_delta": "-10", "heating_radiator_schedule_start": "23:00",
                 "heating_radiator_schedule_end": "06:00"}.items():
        assert sim.controller.on_setting(k, v) == "ok"
    sim.warmup(2)
    day = sim.plant.pipes["tsrad_s"]
    assert abs(day - 50) < 2
    sim.advance(3 * 3600)  # → 00:00, inside the 23:00–06:00 window
    assert sim.controller.schedule_rad
    assert sim.controller.radiator_target() == 40
    assert abs(sim.plant.pipes["tsrad_s"] - 40) < 2.5
    assert sim.controller.heartbeat(None, None)["rad_target"] == 40
