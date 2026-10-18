"""Tests for draw_schematic.py — run: python3 -m pytest docs/boiler-room -q"""

import xml.etree.ElementTree as ET
from pathlib import Path

from check_docs import parse_relays, svg_refs
from draw_schematic import DEVKIT_LEFT, DEVKIT_RIGHT, OUTPUTS, PIN_NETS, render_logic, render_power

PINOUT = Path(__file__).resolve().parents[2] / "firmware" / "esp32-homesite" / "PINOUT.md"


def text_of(svg: str) -> str:
    return " ".join(ET.fromstring(svg).itertext())


def test_devkit_headers_have_19_pins_each_and_every_gpio_once():
    assert len(DEVKIT_LEFT) == 19 and len(DEVKIT_RIGHT) == 19
    gpios = [p for p in DEVKIT_LEFT + DEVKIT_RIGHT if p.startswith("IO")]
    assert len(gpios) == len(set(gpios))


def test_relay_nets_sit_on_the_gpio_the_firmware_uses():
    fw = parse_relays(PINOUT.read_text(encoding="utf-8"))
    for ch, gpio in fw.items():
        net = PIN_NETS[f"IO{gpio}"]
        if ch == "0":
            assert net == "K0/OT_RX"          # through JP1: relay K0 now, OpenTherm receive after the boiler swap
        elif ch == "15":
            assert net == "OT_TX"             # K15 freed for OpenTherm transmit
        else:
            assert net == f"K{ch}"


def test_sensor_nets_match_the_pinout():
    assert PIN_NETS["IO4"] == "1WIRE" and PIN_NETS["IO15"] == "DHT"
    assert PIN_NETS["IO34"] == "P_HEAT" and PIN_NETS["IO35"] == "P_WATER" and PIN_NETS["IO39"] == "GAS"


def test_logic_sheet_has_every_part_with_values():
    svg = render_logic()
    _, refs = svg_refs(svg)
    assert {"A1", "A2", "A3", "G1", "JP1", "R1", "R2", "R3", "R4", "R5", "C1", "C2", "C3", "C4", "C5", "VD1", "VD2",
            "X1", "X2", "X3", "X4", "X5", "X6", "X7"} <= refs
    txt = text_of(svg)
    for needle in ("4,7 кОм", "10 кОм", "100 нФ", "100 мкФ", "+3V3", "+5V", "JD-VCC", "set_flash_voltage"):
        assert needle in txt, needle
    for ch in range(15):
        assert f"IN{ch}" in txt


def test_every_relay_output_has_its_panel_indicator_in_parallel():
    svg = render_power()
    _, refs = svg_refs(svg)
    for ch, _, loads, hl, _, _ in OUTPUTS:
        if hl:
            assert hl in refs, f"K{ch} indicator"
        for r in loads.split():
            assert r in refs, f"K{ch} load {r}"
    assert {"HL1", "HL2", "HA1", "SK1", "SK2", "SP1", "KM1", "KM2", "XT1", "QF4", "QF2", "HL3"} <= refs
    labels = {label for *_, label, _ in OUTPUTS if label}
    assert {"P1", "P2", "P3", "WP", "RP", "TEN"} <= labels
    # Warn and Alarm share the panel's ALARM position: yellow on K13, red on K14
    by_ch = {ch: (label, colour) for ch, _, _, _, label, colour in OUTPUTS}
    assert by_ch[13] == ("ALARM", "жёлтый") and by_ch[14] == ("ALARM", "красный")
