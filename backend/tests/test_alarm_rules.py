"""Alarm rules (what is wrong right now) and the tracker (delays, raise/clear events)."""

from datetime import UTC, datetime, timedelta

from app.services.alarm_rules import Alarm, AlarmTracker, Snapshot, evaluate

NOW = datetime(2026, 1, 20, 3, 0, tzinfo=UTC)


def reading(v: float | None) -> dict:
    return {"value": v, "stale": v is None}


def snap(**over) -> Snapshot:
    values = {r: reading(None) for r in (
        "boiler_supply", "boiler_return", "rad_supply", "floor_supply", "tank", "cold_water",
        "heating_pressure", "outdoor", "boiler_room")}
    values.update({"boiler_supply": reading(60), "boiler_return": reading(45), "rad_supply": reading(50),
                   "floor_supply": reading(30), "tank": reading(50), "cold_water": reading(8),
                   "heating_pressure": reading(1.4), "outdoor": reading(-10), "boiler_room": reading(15)})
    values.update(over.pop("values", {}))
    relays = {"boiler": True, "rad_pump": True, "floor_pump": True, "ihb_pump": False}
    relays.update(over.pop("relays", {}))
    base = dict(
        now=NOW,
        services={"gateway": True, "mqtt": True},
        online=True,
        values=values,
        relays=relays,
        flags={},
        targets={"boiler": 65.0, "rad": 52.0, "floor": 31.0, "ihb": 55.0},
        settings={"heating_pressure_min": "1.0", "heating_pressure_max": "2.0", "heating_autofill_enabled": "1",
                  "watersupply_alm_temp": "60"},
        rooms=[("Детская", 21.0), ("Кухня", 22.0)],
        hb={"rad_wbm": False, "floor_wbm": False, "outdoor": -10},
    )
    base.update(over)
    return Snapshot(**base)


def codes(s: Snapshot, active: set[str] | None = None) -> dict[str, Alarm]:
    return {a.code: a for a in evaluate(s, active or set())}


def test_normal_winter_night_has_no_alarms():
    assert codes(snap()) == {}


# ---------------------------------------------------------------- rooms and the boiler room
def test_room_temperature_levels_with_names():
    a = codes(snap(rooms=[("Детская", 14.0), ("Кухня", 9.0), ("Спальня", 4.0)]))
    assert a["room:Детская"].level == "WARNING" and "Детская" in a["room:Детская"].text
    assert a["room:Кухня"].level == "ERROR" and "Холодно" in a["room:Кухня"].text
    assert a["room:Спальня"].level == "ERROR" and "замерзания" in a["room:Спальня"].text
    assert all(x.delay_s == 600 for x in a.values())


def test_room_alarm_clears_only_1_degree_above_the_threshold():
    s = snap(rooms=[("Детская", 15.5)])
    assert "room:Детская" in codes(s, {"room:Детская"})
    assert "room:Детская" not in codes(s)
    assert "room:Детская" not in codes(snap(rooms=[("Детская", 16.1)]), {"room:Детская"})


def test_stale_room_sensor_is_not_a_cold_room():
    assert codes(snap(rooms=[("Детская", None)])) == {}


def test_boiler_room_and_cold_water_near_freezing():
    a = codes(snap(values={"boiler_room": reading(2.5), "cold_water": reading(2.0)}))
    assert a["boiler_room"].level == "ERROR" and "РАЗМОРОЗКИ" in a["boiler_room"].text
    assert a["cold_water"].level == "ERROR"
    assert codes(snap(values={"boiler_room": reading(7.0)}))["boiler_room"].level == "WARNING"


# ---------------------------------------------------------------- pressure
def test_pressure_just_below_min_is_the_autofill_working_not_an_alarm_yet():
    a = codes(snap(values={"heating_pressure": reading(0.95)}))
    assert set(a) == {"pressure_low_long"}
    assert a["pressure_low_long"].level == "WARNING" and a["pressure_low_long"].delay_s == 600
    assert "подпитка не справляется" in a["pressure_low_long"].text


def test_pressure_low_with_autofill_off_says_so():
    s = snap(values={"heating_pressure": reading(0.95)})
    s.settings["heating_autofill_enabled"] = "0"
    assert "автоподпитка выключена" in codes(s)["pressure_low_long"].text


def test_pressure_below_the_emergency_level_is_an_error_within_a_minute():
    a = codes(snap(values={"heating_pressure": reading(0.7)}))
    assert a["pressure_low"].level == "ERROR" and a["pressure_low"].delay_s == 60


def test_zero_pressure_is_left_to_the_controller_flag():
    a = codes(snap(values={"heating_pressure": reading(0.0)}, flags={"pressure_zero": True}))
    assert "pressure_low" not in a and "flag:pressure_zero" in a


def test_pressure_near_the_relief_valve():
    a = codes(snap(values={"heating_pressure": reading(2.6)}))
    assert a["pressure_high"].level == "ERROR"
    assert codes(snap(values={"heating_pressure": reading(2.2)}))["pressure_high_long"].level == "WARNING"


# ---------------------------------------------------------------- controller link, services, flags
def test_controller_offline_in_frost_warns_that_everything_may_be_off():
    a = codes(snap(online=False, flags={}, hb={}))
    assert a["no_link"].level == "ERROR" and a["no_link"].delay_s == 60
    assert "насосы" in a["no_link"].text and "−10" in a["no_link"].text


def test_gateway_down_is_one_alarm_not_also_no_link():
    a = codes(snap(online=False, services={"gateway": False, "mqtt": True}, hb={}))
    assert set(a) == {"svc:gateway"}


def test_controller_flags_become_alarms():
    a = codes(snap(flags={"frost_protect": True, "overtemp": False}))
    assert set(a) == {"flag:frost_protect"} and "замерзания" in a["flag:frost_protect"].text


def test_pza_without_outdoor_temperature():
    a = codes(snap(hb={"rad_wbm": True, "floor_wbm": False}))
    assert a["pza_no_outdoor"].level == "WARNING"


# ---------------------------------------------------------------- circuits and DHW
def test_circuit_that_does_not_warm_up_although_the_boiler_is_hot():
    a = codes(snap(values={"rad_supply": reading(30), "boiler_supply": reading(70)}))
    assert a["no_heat:rad"].level == "ERROR" and a["no_heat:rad"].delay_s == 20 * 60
    assert "Радиаторы" in a["no_heat:rad"].text


def test_circuit_with_its_pump_off_is_not_checked():
    assert "no_heat:rad" not in codes(snap(values={"rad_supply": reading(30), "boiler_supply": reading(70)},
                                           relays={"rad_pump": False}))


def test_tank_overheat_and_tank_not_heating():
    assert codes(snap(values={"tank": reading(82)}))["tank_overheat"].level == "ERROR"
    a = codes(snap(values={"tank": reading(40), "boiler_supply": reading(70)}, relays={"ihb_pump": True}))
    assert a["tank_no_heat"].level == "WARNING" and a["tank_no_heat"].delay_s == 60 * 60


def test_supply_colder_than_return():
    a = codes(snap(values={"boiler_supply": reading(40), "boiler_return": reading(45)}))
    assert a["supply_below_return"].level == "WARNING"


def test_anti_legionella_result_and_missing_clock():
    a = codes(snap(hb={"rad_wbm": False, "floor_wbm": False, "outdoor": -10, "alm_last": "failed", "alm_no_time": True}))
    assert a["alm_failed"].level == "WARNING" and "60" in a["alm_failed"].text
    assert a["alm_no_time"].level == "WARNING"


# ---------------------------------------------------------------- tracker
def test_tracker_raises_after_the_delay_and_clears_with_the_condition():
    t = AlarmTracker()
    a = Alarm("room:Детская", "ERROR", "Холодно", delay_s=600)
    raised, cleared = t.update([a], NOW)
    assert raised == [] and t.active == {}
    raised, _ = t.update([a], NOW + timedelta(seconds=599))
    assert raised == []
    raised, _ = t.update([a], NOW + timedelta(seconds=600))
    assert raised == [a] and "room:Детская" in t.active
    _, cleared = t.update([], NOW + timedelta(seconds=700))
    assert [c.code for c in cleared] == ["room:Детская"] and t.active == {}


def test_tracker_restarts_the_delay_when_the_condition_blinks():
    t = AlarmTracker()
    a = Alarm("pressure_low", "ERROR", "x", delay_s=60)
    t.update([a], NOW)
    t.update([], NOW + timedelta(seconds=30))
    raised, _ = t.update([a], NOW + timedelta(seconds=70))
    assert raised == []


def test_tracker_logs_an_escalation_but_not_a_repeat():
    t = AlarmTracker()
    t.update([Alarm("room:Кухня", "WARNING", "Прохладно")], NOW)
    raised, _ = t.update([Alarm("room:Кухня", "WARNING", "Прохладно")], NOW)
    assert raised == []
    raised, _ = t.update([Alarm("room:Кухня", "ERROR", "Холодно")], NOW)
    assert [r.level for r in raised] == ["ERROR"]


def test_tracker_holds_flags_while_the_controller_is_unreachable():
    t = AlarmTracker()
    t.update([Alarm("flag:autofill_fault", "ERROR", "x")], NOW)
    raised, cleared = t.update([Alarm("no_link", "ERROR", "y")], NOW, hold_prefixes=("flag:",))
    assert cleared == [] and "flag:autofill_fault" in t.active
    raised, _ = t.update([Alarm("flag:autofill_fault", "ERROR", "x")], NOW)   # link back, flag still set
    assert raised == []


def test_tracker_active_list_is_most_severe_first():
    t = AlarmTracker()
    t.update([Alarm("a", "WARNING", "w"), Alarm("b", "ERROR", "e")], NOW)
    assert [a["code"] for a in t.active_list()] == ["b", "a"]


def test_tracker_acknowledgement_and_its_reset_on_escalation():
    t = AlarmTracker()
    t.update([Alarm("room:Кухня", "WARNING", "Прохладно")], NOW)
    [item] = t.active_list()
    assert item["acked"] is False and item["since"] == NOW.isoformat()
    assert t.ack("room:Кухня") is True and t.active_list()[0]["acked"] is True
    assert t.ack("no:such") is False
    t.update([Alarm("room:Кухня", "WARNING", "Прохладно")], NOW + timedelta(minutes=1))
    assert t.active_list()[0]["acked"] is True           # same alarm: stays acknowledged
    t.update([Alarm("room:Кухня", "ERROR", "Холодно")], NOW + timedelta(minutes=2))
    assert t.active_list()[0]["acked"] is False          # got worse: needs attention again
    t.update([], NOW + timedelta(minutes=3))
    t.update([Alarm("room:Кухня", "WARNING", "Прохладно")], NOW + timedelta(minutes=4))
    assert t.active_list()[0]["acked"] is False          # a new occurrence is not acknowledged
