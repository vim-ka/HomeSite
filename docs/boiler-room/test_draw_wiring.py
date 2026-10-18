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
    assert {"A1", "A2.1", "A2.2", "G1", "G2", "QF1", "QF2", "QF3", "QF4", "QF5", "QF6", "KM1", "KM2", "EK1",
            "M1", "M2", "M3", "M4", "M5", "YA1", "YA2", "YA3", "HL1", "HL2", "HA1", "SK1", "XT1", "A4", "A5",
            "SK2", "SP1"} <= refs
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
    # receive on GPIO13 (freed relay K0): GPIO36/39 get spurious pulses while ADC1 runs (ESP32 errata),
    # and the OpenTherm library decodes on interrupts
    assert "GPIO13" in txt and "GPIO5" in txt
    assert "GPIO13 (вход)" in txt and "приём → GPIO13" in txt
    assert "GPIO36 (вход)" not in txt and "приём → GPIO36" not in txt   # the note may still explain why not 36
    assert "OT" in txt


def test_hardware_interlocks_sit_in_the_power_lines_not_only_in_software():
    txt = text_of(render_structure())
    assert "KM1 → SK2 → EK1" in txt          # TEH: emergency cut-out with manual reset
    assert "KM2 → SP1 → M4" in txt           # well pump: pressure switch in series
    assert "30 мА" in txt and "QF5" in txt   # separate RCDs for the TEH and the well pump


def test_relay_channels_given_to_opentherm_are_marked_free():
    load = {ch: text for ch, _, text, _ in RELAYS}
    assert "OpenTherm" in load[0] and "GPIO13" in load[0]
    assert "OpenTherm" in load[15] and "GPIO5" in load[15]


RF_PINOUT = Path(__file__).resolve().parents[2] / "firmware" / "esp32-rf-gateway" / "PINOUT.md"


def test_rf_gateway_pins_match_its_firmware_pinout():
    from draw_wiring import RF_PINS
    fw = {}
    for line in RF_PINOUT.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1].isdigit() and cells[0].isupper():
            fw[cells[0]] = int(cells[1])
    assert {k: v for k, v in RF_PINS.items()} == {k: fw[k] for k in RF_PINS}
    assert {"SCK", "MISO", "MOSI", "CSN", "GDO0"} <= RF_PINS.keys()


def test_rf_gateway_sheet_shows_wiring_power_and_antenna():
    from draw_wiring import render_rf_gateway
    svg = render_rf_gateway()
    _, refs = svg_refs(svg)
    assert "A4" in refs
    txt = text_of(svg)
    for needle in ("CC1101", "GPIO18", "GPIO19", "GPIO23", "GPIO5", "GPIO4", "3,3 В", "100 нФ", "10 мкФ",
                   "17,3 см", "433,92 МГц"):
        assert needle in txt, needle
