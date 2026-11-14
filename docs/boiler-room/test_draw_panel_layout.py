"""Tests for draw_panel_layout.py — run: python3 -m pytest docs/boiler-room -q"""

from check_docs import svg_refs
from draw_panel_layout import DOOR, ROWS, ROW_MODULES, render_layout


def test_every_rail_fits_its_modules():
    for title, items in ROWS:
        assert sum(m for _, _, m, *_ in items) <= ROW_MODULES, title


def test_rails_hold_every_din_device_and_the_door_every_indicator():
    _, refs = svg_refs(render_layout())
    assert {"QF1", "QF2", "QF3", "QF4", "QF5", "QF6", "KM1", "KM2", "HL1", "HL2", "HA1", "G1", "XT1",
            "A2.1", "A2.2", "A1", "A3"} <= refs
    assert {f"HL{i}" for i in range(3, 16)} | {"SA1"} <= refs
    assert len([r for r, *_ in DOOR]) == 14


def test_230v_rows_sit_above_the_low_voltage_electronics():
    # mains cables enter at the top, sensor cables at the bottom: the ESP32 rail is the last one
    rails = [{ref for ref, *_ in items} for _, items in ROWS]
    assert "QF1" in rails[0] and "A1" in rails[-1]
    assert all("A1" not in r for r in rails[:-1])
