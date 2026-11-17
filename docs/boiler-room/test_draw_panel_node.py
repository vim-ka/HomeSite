"""Tests for draw_panel_node.py — run: python3 -m pytest docs/boiler-room -q"""

import xml.etree.ElementTree as ET

from check_docs import svg_refs
from draw_panel_node import PANEL_NETS, render_panel_node
from draw_schematic import DEVKIT_LEFT, DEVKIT_RIGHT


def text_of(svg: str) -> str:
    return " ".join(ET.fromstring(svg).itertext())


def test_nets_sit_on_real_devkit_pins():
    pins = set(DEVKIT_LEFT + DEVKIT_RIGHT)
    assert set(PANEL_NETS) <= pins
    by_net = {net: pin for pin, net in PANEL_NETS.items()}
    # UART2 to the meter: ESP TX → PZEM RX, PZEM TX → ESP RX
    assert by_net["PZEM_TX"] == "IO17" and by_net["PZEM_RX"] == "IO16"


def test_sheet_has_meter_clamp_and_mains_supply_without_battery():
    svg = render_panel_node()
    _, refs = svg_refs(svg)
    assert {"A7", "A8", "TA1", "G3", "QF7", "FU1"} <= refs
    assert not {"A9", "GB1", "R6", "R7", "R8", "R9", "C6", "C7"} & refs   # no battery backup, no dividers
    txt = text_of(svg)
    for needle in ("PZEM-004T", "100 А", "MQTT", "+3V3", "+5V"):
        assert needle in txt, needle
    for gone in ("18650", "VIN_OK", "VBAT"):
        assert gone not in txt, gone
