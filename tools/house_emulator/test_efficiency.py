"""Efficiency rules of the controller (firmware port): DHW boiler target, minimum boiler temperature for a
non-condensing boiler, anti short-cycling, room correction of the weather curve, recirculation schedule.

Run: cd tools && python -m pytest house_emulator
"""

from datetime import datetime

from house_emulator.controller import Controller

NOW = datetime(2026, 1, 20, 12, 0)   # Tuesday noon
AUTO = {"heating_boiler_automode": "1", "heating_radiator_wbm": "0", "heating_radiator_temp": "60",
        "heating_floorheating_wbm": "0", "heating_floorheating_temp": "30", "heating_floorheating_pump": "1",
        "heating_radiator_pump": "1", "watersupply_ihb_automode": "1", "watersupply_ihb_temp": "50",
        "heating_radiator_schedule_enabled": "0", "heating_floorheating_schedule_enabled": "0"}
TEMPS = {"tsboiler_s": 60.0, "tswatersupply_h": 55.0, "tsrad_s": 55.0, "tsfloor_s": 30.0}


def make(**settings: str) -> Controller:
    c = Controller()
    for k, v in {**AUTO, **settings}.items():
        assert c.on_setting(k, v) == "ok", k
    return c


def run(c: Controller, seconds: float, temps: dict, now: datetime = NOW, step: float = 10.0) -> list[bool]:
    """Control cycles every `step` s; returns the boiler relay after each one."""
    out, t = [], 0.0
    while t < seconds:
        c.tick(step)
        c.update(now, temps, 1.5, None)
        out.append(c.relays["boiler"])
        t += step
    return out


# ---------------------------------------------------------------- 1. the tank in the boiler target
def test_a_satisfied_tank_does_not_hold_the_boiler_at_dhw_temperature():
    c = make(heating_radiator_temp="40", heating_boiler_min_temp="30")
    run(c, 60, {**TEMPS, "tswatersupply_h": 55.0})            # tank above its 50° target
    assert not c.ihb_heating
    assert c.boiler_auto_target == 40                 # radiators only


def test_a_loading_tank_gets_the_boiler_15_above_its_target():
    c = make(heating_radiator_temp="40", heating_boiler_min_temp="30")
    run(c, 60, {**TEMPS, "tswatersupply_h": 40.0})            # tank cold
    assert c.ihb_heating
    assert c.boiler_auto_target == 65                 # 50 + 15: the coil can actually reach the target


def test_the_dhw_boost_still_respects_the_overtemp_cap():
    c = make(heating_boiler_max_temp="70", watersupply_ihb_temp="60", heating_boiler_min_temp="30")
    run(c, 60, {**TEMPS, "tswatersupply_h": 40.0})
    assert c.boiler_auto_target == 70 - 5 - 2


# ---------------------------------------------------------------- 4. non-condensing boiler minimum
def test_a_non_condensing_boiler_never_targets_below_its_minimum():
    c = make(heating_radiator_temp="40", heating_floorheating_temp="30")   # default min 55
    run(c, 60, TEMPS)
    assert c.boiler_auto_target == 55


def test_the_minimum_is_a_setting():
    c = make(heating_radiator_temp="40", heating_boiler_min_temp="45")
    run(c, 60, TEMPS)
    assert c.boiler_auto_target == 45


# ---------------------------------------------------------------- 3. anti short-cycling
def test_the_boiler_runs_at_least_five_minutes():
    c = make(heating_radiator_temp="60")
    run(c, 30, {**TEMPS, "tsboiler_s": 50.0})                 # cold → on
    assert c.relays["boiler"]
    log = run(c, 4 * 60, {**TEMPS, "tsboiler_s": 70.0})       # hot right away
    assert all(log)                                           # still on: minimum run time
    log = run(c, 2 * 60, {**TEMPS, "tsboiler_s": 70.0})
    assert not log[-1]                                        # then off


def test_the_boiler_pauses_at_least_five_minutes():
    c = make(heating_radiator_temp="60")
    run(c, 30, {**TEMPS, "tsboiler_s": 50.0})
    run(c, 5 * 60, {**TEMPS, "tsboiler_s": 70.0})             # ran its minimum, off at ~5 min
    assert not c.relays["boiler"]
    log = run(c, 4 * 60, {**TEMPS, "tsboiler_s": 50.0})       # cold again at once
    assert not any(log)                                       # minimum pause
    log = run(c, 2 * 60, {**TEMPS, "tsboiler_s": 50.0})
    assert log[-1]


def test_overtemp_beats_the_minimum_run_time():
    c = make(heating_radiator_temp="60")
    run(c, 30, {**TEMPS, "tsboiler_s": 50.0})
    log = run(c, 20, {**TEMPS, "tsboiler_s": 86.0})           # above max 85
    assert not log[-1]


def test_frost_protection_beats_the_minimum_pause():
    c = make(heating_radiator_temp="60")
    run(c, 30, {**TEMPS, "tsboiler_s": 50.0})
    run(c, 6 * 60, {**TEMPS, "tsboiler_s": 70.0})
    assert not c.relays["boiler"]
    log = run(c, 30, {**TEMPS, "tsboiler_s": 5.0, "tsrad_s": 5.0})
    assert log[-1]


def test_manual_mode_follows_the_command_at_once():
    c = make(heating_boiler_automode="0", heating_boiler_power="1")
    run(c, 30, TEMPS)
    assert c.relays["boiler"]
    assert c.on_setting("heating_boiler_power", "0") == "ok"
    assert not run(c, 10, TEMPS)[-1]


# ---------------------------------------------------------------- 7. room correction of the weather curve
PZA = {"heating_radiator_wbm": "1", "heating_floorheating_wbm": "1", "heating_room_temp": "21",
       "heating_room_factor": "2"}


def pza_targets(c: Controller) -> tuple[float, float]:
    c.set_outdoor(0.0)
    run(c, 10, TEMPS)
    return c.radiator_target(), c.floor_target()


def test_a_cold_house_raises_the_weather_curve():
    base = pza_targets(make(**{**PZA, "heating_room_factor": "0"}))
    c = make(**PZA)
    c.set_indoor(19.0)                                         # 2° below the room target
    rad, floor = pza_targets(c)
    assert rad == base[0] + 4                                  # factor 2 × 2°
    assert floor == base[1] + 2                                # the floor gets half


def test_a_warm_house_lowers_it_within_limits():
    base = pza_targets(make(**{**PZA, "heating_room_factor": "0"}))
    c = make(**{**PZA, "heating_room_factor": "5"})
    c.set_indoor(26.0)                                         # 5° too warm → −25, limited
    rad, floor = pza_targets(c)
    assert rad == base[0] - 10
    assert floor == base[1] - 5


def test_no_room_correction_without_fresh_indoor_data_or_in_manual_mode():
    base = pza_targets(make(**{**PZA, "heating_room_factor": "0"}))
    c = make(**PZA)
    assert pza_targets(c) == base                              # never received
    c.set_indoor(19.0)
    run(c, 11 * 60, TEMPS)                                     # stale after 10 min
    assert pza_targets(c) == base
    manual = make(**{**PZA, "heating_radiator_wbm": "0", "heating_radiator_temp": "50"})
    manual.set_indoor(19.0)
    assert pza_targets(manual)[0] == 50                        # a manual setpoint is what the user asked for


# ---------------------------------------------------------------- 2. recirculation schedule
def recirc_at(c: Controller, hour: int, minute: int = 0) -> bool:
    run(c, 10, TEMPS, now=NOW.replace(hour=hour, minute=minute))
    return c.relays["water_hot_pump"]


def test_recirculation_runs_only_in_its_windows():
    c = make(watersupply_recirc_schedule_enabled="1")          # 06–09 and 18–23
    assert recirc_at(c, 7)
    assert not recirc_at(c, 12)
    assert recirc_at(c, 20, 30)
    assert not recirc_at(c, 23, 30)
    assert not recirc_at(c, 3)


def test_recirculation_without_schedule_follows_the_switch():
    c = make()
    assert recirc_at(c, 3)
    assert c.on_setting("watersupply_pump_hot", "0") == "ok"
    assert not recirc_at(c, 7)


def test_recirculation_switched_off_stays_off_in_its_window():
    c = make(watersupply_recirc_schedule_enabled="1", watersupply_pump_hot="0")
    assert not recirc_at(c, 7)


# ---------------------------------------------------------------- the tank is regulated by the sensor IN the tank
def test_loading_follows_the_tank_not_the_hot_loading_pipe():
    """tswatersupply_h is the tank (upper sleeve); tsihb_s / tsihb_b are the loading pipes. A loading pipe still
    hot after the pump stopped must not keep a cold tank from loading (reported on the stand: tank 68 / target 70,
    loading pipe 72 → no loading)."""
    c = make(heating_boiler_min_temp="30", watersupply_ihb_temp="70")
    run(c, 30, {**TEMPS, "tswatersupply_h": 68.0, "tsihb_s": 72.0}, now=NOW)
    assert c.ihb_heating and c.relays["ihb_pump"]


def test_a_cold_loading_pipe_does_not_start_a_hot_tank():
    c = make(heating_boiler_min_temp="30")
    run(c, 30, {**TEMPS, "tswatersupply_h": 55.0, "tsihb_s": 20.0}, now=NOW)
    assert not c.ihb_heating and not c.relays["ihb_pump"]


# ---------------------------------------------------------------- outdoor smoothing for the weather curves
def outdoor_run(c: Controller, minutes: float, outdoor: float, step: float = 60.0) -> None:
    """The street sensor reports every minute (gateway forward), control cycles in between."""
    t = 0.0
    while t < minutes * 60:
        c.set_outdoor(outdoor)
        c.tick(step)
        c.update(NOW, TEMPS, 1.5, None)
        t += step


def test_the_weather_curve_follows_a_smoothed_street_temperature():
    """A building's inertia is hours (kotelna.tk: TAC default 4 h): a sudden street change moves the curve slowly."""
    c = make(heating_radiator_wbm="1", heating_pza_outdoor_tau_h="4")
    outdoor_run(c, 60, -10.0)
    assert abs(c.outdoor_pza() - (-10.0)) < 0.01
    outdoor_run(c, 30, 5.0)                                   # sunny noon / a warm front
    assert c.outdoor == 5.0                                   # the raw reading is what the sensor says …
    assert -9.0 < c.outdoor_pza() < -7.0                      # … the curve sees ~ -8 after 30 min (τ 4 h)
    outdoor_run(c, 24 * 60, 5.0)
    assert abs(c.outdoor_pza() - 5.0) < 0.1                   # and catches up within a day


def test_no_smoothing_with_zero_inertia():
    c = make(heating_radiator_wbm="1", heating_pza_outdoor_tau_h="0")
    outdoor_run(c, 30, -10.0)
    outdoor_run(c, 2, 5.0)
    assert c.outdoor_pza() == 5.0


def test_a_long_gap_restarts_the_smoothing_from_the_new_reading():
    c = make(heating_radiator_wbm="1", heating_pza_outdoor_tau_h="4")
    outdoor_run(c, 30, -10.0)
    c.tick(20 * 60)                                           # street sensor silent 20 min (> 15 min TTL)
    c.set_outdoor(3.0)
    assert c.outdoor_pza() == 3.0


# ---------------------------------------------------------------- DHW loading boost as a setting (hard water)
def test_the_loading_boost_is_a_setting():
    c = make(heating_radiator_temp="40", heating_boiler_min_temp="30", watersupply_ihb_boost="5")
    run(c, 60, {**TEMPS, "tswatersupply_h": 40.0})
    assert c.boiler_auto_target == 55                         # 50 + 5: gentler on the coil with hard water


# ---------------------------------------------------------------- room correction vs night setback
NIGHT = datetime(2026, 1, 20, 2, 0)   # inside the default 23:00–06:00 window, Tuesday
NIGHT_PZA = {**PZA, "heating_radiator_schedule_enabled": "1", "heating_floorheating_schedule_enabled": "1",
             "heating_radiator_schedule_days": "1,2,3,4,5,6,7", "heating_floorheating_schedule_days": "1,2,3,4,5,6,7",
             "heating_radiator_schedule_delta": "-4", "heating_floorheating_schedule_delta": "-2"}


def night_targets(c: Controller) -> tuple[float, float]:
    c.set_outdoor(0.0)
    run(c, 10, TEMPS, now=NIGHT)
    assert c.schedule_rad and c.schedule_floor
    return c.radiator_target(), c.floor_target()


def test_at_night_a_cooling_house_does_not_undo_the_setback():
    """The setback lets the house cool on purpose: the correction must not push the supply back up."""
    base = night_targets(make(**{**NIGHT_PZA, "heating_room_factor": "0"}))
    c = make(**NIGHT_PZA)
    c.set_indoor(19.0)                                         # 2° below the day target — expected at night
    assert night_targets(c) == base


def test_at_night_an_overheated_house_still_lowers_the_supply():
    base = night_targets(make(**{**NIGHT_PZA, "heating_room_factor": "0"}))
    c = make(**NIGHT_PZA)
    c.set_indoor(23.0)                                         # sun in the evening, a fireplace
    rad, floor = night_targets(c)
    assert rad == base[0] - 4 and floor == base[1] - 2


def test_in_the_morning_the_correction_helps_the_house_catch_up():
    c = make(**NIGHT_PZA)
    c.set_indoor(19.0)
    night = night_targets(c)
    c.set_outdoor(0.0)
    run(c, 10, TEMPS, now=NOW)                                  # noon: outside the window
    assert c.radiator_target() > night[0] + 4                   # setback gone and +4 correction back
