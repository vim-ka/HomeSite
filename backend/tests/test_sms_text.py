from datetime import UTC, datetime, timedelta

from app.services.alarm_rules import Alarm
from app.services.sms_text import SMS_LIMIT, Part, merge, summary_text

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)


def P(problem, text="x", level="ERROR", raised=True):
    return Part(problem=problem, level=level, raised=raised, text=text)


def test_merge_orders_error_first():
    parts = [P("a", "w-cleared", "WARNING", False), P("b", "w-raised", "WARNING", True),
             P("c", "e-cleared", "ERROR", False), P("d", "e-raised", "ERROR", True)]
    text, out = merge(parts)
    assert text == "e-raised; e-cleared; w-raised; w-cleared"
    assert [p.problem for p in out] == ["d", "c", "b", "a"]


def test_merge_limit_134_with_tail():
    parts = [P(str(i), "x" * 40) for i in range(5)]
    text, out = merge(parts)
    assert len(text) <= SMS_LIMIT
    assert text.endswith("…и ещё 3, подробнее на сайте")
    assert len(out) == 5


def test_merge_single_too_long_truncated():
    text, out = merge([P("a", "y" * 200)])
    assert len(text) == SMS_LIMIT and text.endswith("…")
    assert len(out) == 1


def test_merge_first_too_long_with_tail_fits():
    text, out = merge([P("a", "y" * 200), P("b", "z")])
    assert len(text) <= SMS_LIMIT and text.endswith("…и ещё 1, подробнее на сайте")
    assert len(out) == 2


def test_merge_dedupes_problem():
    text, out = merge([P("a", "first"), P("a", "second", "WARNING"), P("b", "other")])
    assert text == "first; other"
    assert [p.problem for p in out] == ["a", "b"]


def test_merge_keeps_a_raise_and_its_clear_of_one_problem():
    """A short ERROR whose first SMS and «Снято» are formed together: both are told, raise first."""
    text, out = merge([P("a", "Снято: low", raised=False), P("a", "low")])
    assert text == "low; Снято: low"
    assert [(p.problem, p.raised) for p in out] == [("a", True), ("a", False)]


def test_summary_internet():
    assert summary_text("internet_down", None, "", 1, NOW - timedelta(minutes=47), NOW) == "Интернет есть, не было 47 мин"


def test_summary_cleared_and_active():
    assert summary_text("x", None, "Давление низкое", 1, NOW, NOW) == "Снято: Давление низкое"
    a = Alarm(code="x", level="ERROR", text="Давление низкое")
    assert summary_text("x", a, "old", 1, NOW, NOW) == "Давление низкое"


def test_summary_counts_flaps():
    a = Alarm(code="x", level="ERROR", text="Т")
    t = summary_text("x", a, "", 5, NOW - timedelta(minutes=40), NOW)
    assert "за 40 мин 5 раз туда-обратно" in t


def test_summary_single_change_no_counter():
    a = Alarm(code="x", level="ERROR", text="Т")
    assert summary_text("x", a, "", 1, NOW - timedelta(minutes=40), NOW) == "Т"
