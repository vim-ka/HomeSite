"""Tests for draw_wiring.py — run: python3 -m pytest docs/boiler-room -q"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from check_docs import parse_relays, svg_refs
from draw_wiring import RELAYS, render_boiler, render_sensors, render_structure

PINOUT = Path(__file__).resolve().parents[2] / "firmware" / "esp32-homesite" / "PINOUT.md"


def text_of(svg: str) -> str:
    return " ".join(ET.fromstring(svg).itertext())


def test_relay_table_matches_firmware_pinout():
    fw = parse_relays(PINOUT.read_text(encoding="utf-8"))
    assert {str(ch): str(gpio) for ch, gpio, *_ in RELAYS} == fw


def test_structure_sheet_shows_every_relay_channel_and_power_device():
    svg = render_structure()
    _, refs = svg_refs(svg)
    assert {"A1", "A2", "G1", "G2", "QF1", "QF2", "QF3", "QF4", "QF5", "QF6", "KM1", "KM2", "EK1",
            "M1", "M2", "M3", "M4", "M5", "YA1", "YA2", "YA3", "HL1", "HL2", "HA1", "SK1", "XT1", "A4", "A5"} <= refs
    txt = text_of(svg)
    for ch in range(16):
        assert re.search(rf"\bK{ch}\b", txt), f"K{ch}"


def test_sensor_sheet_has_bus_pullups_and_every_sensor_on_its_pin():
    svg = render_sensors()
    _, refs = svg_refs(svg)
    assert {f"BK{i}" for i in range(1, 12)} | {"BP1", "BP2", "A1", "G1"} <= refs
    txt = text_of(svg)
    for needle in ("GPIO4", "4,7 кОм", "GPIO15", "10 кОм", "GPIO34", "GPIO35", "100 нФ", "GPIO39",
                   "tsboiler_s", "tswatersupply_h", "prs_heating", "prs_water"):
        assert needle in txt, needle


def test_boiler_sheet_wires_opentherm_to_the_free_pins_and_the_manual_switch():
    svg = render_boiler()
    _, refs = svg_refs(svg)
    assert {"A1", "A3", "A6", "SA1", "A5", "YA4", "QF2", "G2"} <= refs
    txt = text_of(svg)
    assert "GPIO36" in txt and "GPIO5" in txt
    assert "OT" in txt
