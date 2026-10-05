"""Efficiency advice: averaged, steady-state supply − return differences per circuit, boiler return, tank coil."""

from datetime import UTC, datetime, timedelta

from app.services.advice_rules import AdviceHistory, evaluate_advice
from app.services.alarm_rules import AlarmTracker, Snapshot

T0 = datetime(2026, 1, 20, 12, 0, tzinfo=UTC)
NORMAL = {"boiler_supply": 70.0, "boiler_return": 58.0, "rad_supply": 55.0, "rad_return": 43.0,
          "floor_supply": 32.0, "floor_return": 26.0, "tank": 50.0, "coil_supply": 24.0, "coil_return": 24.0}
RUNNING = {"boiler": True, "rad_pump": True, "floor_pump": True, "ihb_pump": False}


def snap(t: datetime, values: dict, relays: dict, flags: dict | None = None, ihb_target: float = 55.0) -> Snapshot:
    return Snapshot(now=t, services={"gateway": True, "mqtt": True}, online=True,
                    values={k: {"value": v, "stale": False} for k, v in values.items()},
                    relays=relays, flags=flags or {}, targets={"ihb": ihb_target}, settings={}, rooms=[])


def run(minutes: float, values: dict | None = None, relays: dict | None = None, flags=None,
        h: AdviceHistory | None = None, tracker: AlarmTracker | None = None, start: datetime = T0, **kw):
    """Poll every 30 s like the HealthMonitor; returns (history, tracker, codes of active advice, end time)."""
    h, tracker = h or AdviceHistory(), tracker or AlarmTracker()
    t = start
    for _ in range(int(minutes * 2)):
        h.add(snap(t, values or NORMAL, relays or RUNNING, flags, **kw))
        advice, held = evaluate_advice(h, t, set(tracker.active))
        tracker.update(advice, t, hold_codes=held)
        t += timedelta(seconds=30)
    return h, tracker, set(tracker.active), t


def test_normal_differences_give_no_advice():
    assert run(120)[2] == set()


def test_an_overpumped_floor_gets_advice_after_the_average_and_the_delay():
    floor = {**NORMAL, "floor_supply": 30.0, "floor_return": 28.5}          # 1.5°
    _, _, early, _ = run(60, floor)
    assert "delta_low:floor" not in early                                     # steady 10 + delay 60 not yet
    _, tracker, codes, _ = run(100, floor)
    assert "delta_low:floor" in codes
    assert "Тёплый пол: разница подачи и обратки 1.5°" in tracker.active["delta_low:floor"].text


def test_too_little_flow_in_the_radiators():
    _, _, codes, _ = run(100, {**NORMAL, "rad_supply": 60.0, "rad_return": 30.0})
    assert codes == {"delta_high:rad"}


def test_a_stopped_pump_holds_the_advice_instead_of_clearing_it():
    floor = {**NORMAL, "floor_supply": 30.0, "floor_return": 28.5}
    h, tracker, codes, t = run(100, floor)
    assert "delta_low:floor" in codes
    _, _, codes, _ = run(30, floor, {**RUNNING, "floor_pump": False}, h=h, tracker=tracker, start=t)
    assert "delta_low:floor" in codes                                         # pump off: can't judge, kept


def test_advice_clears_once_the_circuit_is_back_in_its_norm():
    floor = {**NORMAL, "floor_supply": 30.0, "floor_return": 28.5}
    h, tracker, _, t = run(100, floor)
    _, _, codes, _ = run(40, NORMAL, h=h, tracker=tracker, start=t)
    assert "delta_low:floor" not in codes


def test_the_minutes_after_a_pump_start_do_not_count():
    """A standing circuit after a start: the sensors see standing water — a big difference that means nothing."""
    h, tracker, _, t = run(60, NORMAL, {**RUNNING, "rad_pump": False})
    h, tracker, codes, t = run(9, {**NORMAL, "rad_return": 20.0}, h=h, tracker=tracker, start=t)
    assert not any(c.endswith(":rad") for c in codes)
    assert h.average(t, "rad_pump", "schedule_rad", lambda x: 1.0) is None   # not steady yet


def test_a_night_setback_switch_pauses_the_judgement():
    h, tracker, _, t = run(60, NORMAL, flags={"schedule_rad": False})
    h.add(snap(t, NORMAL, RUNNING, {"schedule_rad": True}))
    assert h.average(t + timedelta(minutes=5), "rad_pump", "schedule_rad", lambda x: 1.0) is None


def test_a_cold_boiler_return_on_a_non_condensing_boiler():
    _, tracker, codes, _ = run(70, {**NORMAL, "boiler_supply": 60.0, "boiler_return": 46.0})   # 10 + 20 + delay 30
    assert "boiler_return_low" in codes
    assert "термосмесительный клапан" in tracker.active["boiler_return_low"].text


def test_a_coil_that_gives_little_heat_to_a_cold_tank():
    h, tracker, _, t = run(15, NORMAL, {**RUNNING, "ihb_pump": False})
    poor = {**NORMAL, "tank": 35.0, "coil_supply": 70.0, "coil_return": 67.0}   # cold tank, 3° over the coil
    _, _, codes, _ = run(20, poor, {**RUNNING, "ihb_pump": True}, h=h, tracker=tracker, start=t)
    assert "coil_poor" in codes


def test_a_coil_that_works_is_fine():
    h, tracker, _, t = run(15, NORMAL, {**RUNNING, "ihb_pump": False})
    good = {**NORMAL, "tank": 35.0, "coil_supply": 70.0, "coil_return": 48.0}
    _, _, codes, _ = run(20, good, {**RUNNING, "ihb_pump": True}, h=h, tracker=tracker, start=t)
    assert "coil_poor" not in codes


# ---------------------------------------------------------------- expansion vessel
def day_of_pressure(swing_bar: float) -> AdviceHistory:
    """24 h, cold nights (35°) and hot days (75°); the pressure follows the temperature by `swing_bar`."""
    h = AdviceHistory()
    t = T0
    for i in range(24 * 12):
        hot = (i // 36) % 2 == 1                         # 3 h cold, 3 h hot
        temp = 75.0 if hot else 35.0
        bar = 1.2 + (swing_bar if hot else 0.0)
        h.add(snap(t, {**NORMAL, "boiler_supply": temp, "heating_pressure": bar}, RUNNING))
        t += timedelta(minutes=5)
    return h


def test_a_vessel_that_lost_its_air():
    h = day_of_pressure(0.7)
    advice, _ = evaluate_advice(h, h.long[-1][0], set())
    a = {x.code: x for x in advice}["expansion_vessel"]
    assert "0.70 бар" in a.text and "расширительном баке" in a.text


def test_a_healthy_vessel():
    h = day_of_pressure(0.2)
    advice, held = evaluate_advice(h, h.long[-1][0], set())
    assert "expansion_vessel" not in {x.code for x in advice} and "expansion_vessel" not in held


def test_not_enough_history_holds_the_advice():
    h = AdviceHistory()
    h.add(snap(T0, {**NORMAL, "heating_pressure": 1.2}, RUNNING))
    _, held = evaluate_advice(h, T0, set())
    assert "expansion_vessel" in held
