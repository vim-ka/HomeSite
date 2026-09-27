"""Controller safety rules (stage 1 of the alarm review), tested on the firmware port directly.

Run: cd tools && python -m pytest house_emulator
"""

from datetime import datetime

from house_emulator.controller import Controller

NOW = datetime(2026, 1, 20, 12, 0)
WARM = {"tsboiler_s": 60.0, "tsihb_s": 50.0, "tsrad_s": 45.0, "tsfloor_s": 30.0}


def make(**settings: str) -> Controller:
    c = Controller()
    for k, v in settings.items():
        assert c.on_setting(k, v) == "ok", k
    return c


def run(c: Controller, seconds: float, temps: dict, pressure: float | None = 1.5,
        water: float | None = None, step: float = 10.0) -> None:
    """Control cycles every `step` seconds, like the firmware's sensor read interval."""
    t = 0.0
    while t < seconds:
        c.tick(step)
        c.update(NOW, temps, pressure, water)
        t += step


# ---------------------------------------------------------------- B1: pressure 0
def test_zero_pressure_is_critical_and_does_not_open_autofill():
    c = make(heating_autofill_enabled="1")
    run(c, 30, WARM, pressure=0.0)
    assert c.pressure_zero and c.critical and c.relays["lamp_critical"]
    assert not c.relays["af_open"]
    assert c.heartbeat(0.0, None)["pressure_zero"] is True


def test_no_pressure_sensor_is_not_an_alarm():
    c = make()
    run(c, 30, WARM, pressure=None)
    assert not c.pressure_zero and not c.critical


# ---------------------------------------------------------------- B2: target below the overtemp trip
def test_auto_target_stays_below_the_overtemp_trip():
    c = make(heating_boiler_automode="1", heating_boiler_max_temp="85",
             heating_radiator_wbm="0", heating_radiator_temp="90", heating_radiator_pump="1")
    run(c, 30, {**WARM, "tsboiler_s": 70.0})
    assert c.boiler_auto_target <= 85 - 5 - 2
    # at the capped target + hysteresis the boiler switches off by regulation, never by the interlock
    run(c, 30, {**WARM, "tsboiler_s": c.boiler_auto_target + 2})
    assert not c.relays["boiler"] and not c.overtemp
    assert not c.warning   # normal regulation doesn't light the "approaching max" lamp


# ---------------------------------------------------------------- B5 / B6: TEH
def test_teh_backs_up_a_boiler_that_does_not_heat_the_tank():
    c = make(watersupply_ihb_teh_automode="1", watersupply_ihb_teh_heating_delay="0",
             watersupply_ihb_automode="1", watersupply_ihb_temp="55",
             heating_boiler_automode="0", heating_boiler_power="1")
    cold_boiler = {**WARM, "tsboiler_s": 35.0, "tsihb_s": 40.0}   # relay on, but the burner is out
    run(c, 30, cold_boiler)
    assert c.relays["boiler"] and c.relays["ihb_pump"]
    assert c.relays["teh"]


def test_teh_waits_while_the_boiler_really_heats_the_tank():
    c = make(watersupply_ihb_teh_automode="1", watersupply_ihb_teh_heating_delay="0",
             watersupply_ihb_automode="1", watersupply_ihb_temp="55",
             heating_boiler_automode="0", heating_boiler_power="1")
    run(c, 30, {**WARM, "tsboiler_s": 70.0, "tsihb_s": 40.0})
    assert not c.relays["teh"]


def test_teh_is_off_without_a_tank_sensor_even_in_manual_mode():
    c = make(watersupply_ihb_teh_automode="0", watersupply_ihb_teh_power="1")
    temps = {k: v for k, v in WARM.items() if k != "tsihb_s"}
    run(c, 30, temps)
    assert not c.relays["teh"]
    assert c.heartbeat(1.5, None)["ihb_sensor_lost"] is True


# ---------------------------------------------------------------- frost protection
def test_frost_protection_overrides_manual_off():
    c = make(heating_boiler_automode="0", heating_boiler_power="0",
             heating_radiator_pump="0", heating_floorheating_pump="0")
    frozen = {"tsboiler_s": 6.0, "tsihb_s": 30.0, "tsrad_s": 6.5, "tsfloor_s": 8.0}
    run(c, 30, frozen)
    assert c.frost_protect and c.critical
    assert c.relays["boiler"] and c.relays["rad_pump"] and c.relays["floor_pump"]
    assert c.heartbeat(1.5, None)["frost_protect"] is True
    # hysteresis: still on at 12 °C, off once everything is back above 15 °C
    run(c, 30, {k: 12.0 for k in frozen})
    assert c.frost_protect
    run(c, 30, {k: 16.0 for k in frozen})
    assert not c.frost_protect and not c.relays["boiler"] and not c.relays["rad_pump"]


def test_frost_protection_never_beats_overtemp():
    c = make(heating_boiler_max_temp="85")
    run(c, 30, {"tsboiler_s": 90.0, "tsihb_s": 30.0, "tsrad_s": 5.0, "tsfloor_s": 5.0})
    assert c.frost_protect and c.overtemp
    assert not c.relays["boiler"]
    assert c.relays["rad_pump"]   # pumps still move the heat away


# ---------------------------------------------------------------- boiler sensor lost
def test_lost_boiler_sensor_in_frost_keeps_the_boiler_on_its_own_thermostat():
    c = make(heating_boiler_automode="1", heating_radiator_pump="1")
    c.set_outdoor(-15.0)
    temps = {k: v for k, v in WARM.items() if k != "tsboiler_s"}
    run(c, 60, temps)
    assert c.boiler_sensor_lost and c.critical
    assert c.relays["boiler"]


def test_lost_boiler_sensor_in_mild_weather_switches_the_boiler_off():
    c = make(heating_boiler_automode="1", heating_radiator_pump="1")
    c.set_outdoor(10.0)
    temps = {k: v for k, v in WARM.items() if k != "tsboiler_s"}
    run(c, 60, temps)
    assert c.boiler_sensor_lost and not c.relays["boiler"]


# ---------------------------------------------------------------- boiler does not heat
def test_boiler_that_does_not_heat_for_30_minutes_is_flagged():
    c = make(heating_boiler_automode="0", heating_boiler_power="1", heating_boiler_temp="60")
    cold = {**WARM, "tsboiler_s": 30.0}
    run(c, 29 * 60, cold)
    assert not c.boiler_no_heat
    run(c, 2 * 60, cold)
    assert c.boiler_no_heat and c.heartbeat(1.5, None)["boiler_no_heat"] is True
    run(c, 30, {**WARM, "tsboiler_s": 55.0})   # heats again
    assert not c.boiler_no_heat


def test_a_slowly_heating_boiler_is_not_flagged():
    c = make(heating_boiler_automode="0", heating_boiler_power="1", heating_boiler_temp="60")
    t = 20.0
    for _ in range(40 * 6):          # 40 min, +0.25 °C per minute
        t += 0.25 / 6
        run(c, 10, {**WARM, "tsboiler_s": t})
    assert not c.boiler_no_heat


# ---------------------------------------------------------------- well dry run
def test_well_pump_stops_on_dry_run_and_retries_later():
    c = make(watersupply_pump="1")
    run(c, 50, WARM, water=0.2)
    assert c.relays["water_pump"]               # 60 s grace
    run(c, 20, WARM, water=0.2)
    assert not c.relays["water_pump"] and c.well_dry
    assert c.heartbeat(1.5, 0.2)["well_dry"] is True
    run(c, 29 * 60, WARM, water=0.2)
    assert not c.relays["water_pump"]
    run(c, 2 * 60, WARM, water=3.0)             # retry after 30 min, water is back
    assert c.relays["water_pump"] and not c.well_dry


def test_well_pump_latches_after_three_dry_runs_until_switched_off_and_on():
    c = make(watersupply_pump="1")
    for _ in range(3):
        run(c, 31 * 60 + 80, WARM, water=0.2)
    assert c.well_dry and c.well_locked
    run(c, 40 * 60, WARM, water=0.2)
    assert not c.relays["water_pump"]
    c.on_setting("watersupply_pump", "0")
    run(c, 10, WARM, water=0.2)
    c.on_setting("watersupply_pump", "1")
    run(c, 10, WARM, water=3.0)
    assert c.relays["water_pump"] and not c.well_locked


def test_no_water_pressure_sensor_no_dry_run_check():
    c = make(watersupply_pump="1")
    run(c, 300, WARM, water=None)
    assert c.relays["water_pump"] and not c.well_dry
