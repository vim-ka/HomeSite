"""Tests for draw_ups_board.py — run: python3 -m pytest docs/boiler-room -q"""

import xml.etree.ElementTree as ET

from check_docs import svg_refs
from draw_schematic import DEVKIT_LEFT, DEVKIT_RIGHT
from draw_ups_board import CABLE, UPS_NETS, render_ups_board


def text_of(svg: str) -> str:
    return " ".join(ET.fromstring(svg).itertext())


def test_uart2_on_real_devkit_pins_as_the_firmware_plan():
    assert set(UPS_NETS) <= set(DEVKIT_LEFT + DEVKIT_RIGHT)
    by_net = {net: pin for pin, net in UPS_NETS.items()}
    assert by_net["UPS_TX"] == "IO17" and by_net["UPS_RX"] == "IO16"


def test_cable_is_three_wires_wired_like_apc_940_0024c():
    # our transmit → UPS contact 1 (its RxD), UPS contact 2 (its TxD) → our receive, ground on contact 4
    assert [(a10, contact) for a10, contact, _ in CABLE] == [("T1OUT", 1), ("R1IN", 2), ("GND", 4)]


def test_sheet_has_board_converter_cable_and_panel_supply():
    svg = render_ups_board()
    _, refs = svg_refs(svg)
    assert {"A9", "A10", "W1", "G1", "C7", "C8"} <= refs   # C7, C8: 5 V filter at the board
    txt = text_of(svg)
    for needle in ("MAX3232", "2400 8N1", "940-0024C", "+3V3", "+5V", "esp32-ups", "Лист 11"):
        assert needle in txt, needle
