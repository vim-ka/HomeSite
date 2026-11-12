"""SMS per-problem policy: pure rules."""

from datetime import UTC, datetime, time, timedelta

from app.services.alarm_rules import Alarm
from app.services.sms_policy import Cfg, Sub, current_problems, decide, effective_level

CFG = Cfg(time(18), time(4))
T0 = datetime(2026, 1, 20, 1, 0, tzinfo=UTC)


def at(h, m=0, day=20):
    return datetime(2026, 1, day, h, m, tzinfo=UTC)


def test_first_error_immediate():
    d = decide(Sub(None, None, 0, None), "ERROR", at(2), CFG)
    assert d.kind == "first"
    assert d.ready_at == at(2) + timedelta(seconds=60)
    assert d.sub.seen == "ERROR" and d.sub.episode_start == at(2)


def test_first_warning_waits_quiet_end():
    d = decide(Sub(None, None, 0, None), "WARNING", at(2), CFG)
    assert d.kind == "first"
    assert d.ready_at == at(4)


def test_quiet_window_wraps_midnight():
    cfg = Cfg(time(22), time(8))
    d = decide(Sub(None, None, 0, None), "WARNING", at(23, 30), cfg)
    assert d.ready_at == at(8, day=21)
    d = decide(Sub(None, None, 0, None), "WARNING", at(12), cfg)
    assert d.ready_at == at(12) + timedelta(seconds=60)


def test_clear_after_error_settles_and_ignores_quiet():
    d = decide(Sub("ERROR", "ERROR", 0, T0), None, at(2), CFG)
    assert d.kind == "summary"
    assert d.ready_at == at(2) + timedelta(seconds=600)


def test_clear_after_warning_waits_morning():
    d = decide(Sub("WARNING", "WARNING", 0, T0), None, at(2), CFG)
    assert d.kind == "summary"
    assert d.ready_at == at(4)


def test_back_to_sent_is_drop():
    d = decide(Sub("ERROR", None, 1, T0), "ERROR", at(2), CFG)
    assert d.kind == "drop"
    assert d.sub.changes == 2
    assert d.ready_at is None


def test_escalation_is_first():
    d = decide(Sub("WARNING", "WARNING", 0, T0), "ERROR", at(2), CFG)
    assert d.kind == "first"
    assert d.sub.episode_start == T0


def test_deescalation_is_summary():
    d = decide(Sub("ERROR", "ERROR", 0, T0), "WARNING", at(2), CFG)
    assert d.kind == "summary"
    assert d.ready_at == at(2) + timedelta(seconds=600)


def test_warning_raised_and_cleared_at_night_is_drop():
    d = decide(Sub(None, "WARNING", 0, T0), None, at(3), CFG)
    assert d.kind == "drop"


def test_no_change_is_none():
    sub = Sub("ERROR", "ERROR", 0, T0)
    d = decide(sub, "ERROR", at(2), CFG)
    assert d.kind == "none" and d.sub is sub


def test_no_quiet_hours():
    for cfg in (Cfg(None, None), Cfg(time(4), time(4))):
        d = decide(Sub(None, None, 0, None), "WARNING", at(2), cfg)
        assert d.ready_at == at(2) + timedelta(seconds=60)


def test_effective_level_filters_category():
    w = Alarm("x", "WARNING", "t")
    assert effective_level(w, {"critical"}) is None
    assert effective_level(w, {"warning"}) == "WARNING"
    assert effective_level(None, {"critical"}) is None
    nl = Alarm("no_link", "ERROR", "t", group="link")
    assert effective_level(nl, {"link"}) == "ERROR"
    assert effective_level(nl, {"critical"}) is None
    assert effective_level(Alarm("internet_down", "ERROR", "t"), {"internet"}) == "ERROR"
    assert effective_level(Alarm("i", "INFO", "t"), {"critical", "warning"}) is None


def test_current_problems_group_and_banner_only():
    low = Alarm("pressure_low", "WARNING", "a", group="p")
    long = Alarm("pressure_low_long", "ERROR", "b", group="p")
    res = current_problems([low, long, Alarm("sms_failed", "ERROR", "c"), Alarm("i", "INFO", "d")])
    assert res == {"p": long}
    assert current_problems([long, low]) == {"p": long}
