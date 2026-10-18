"""Tests for draw_panel_node.py — run: python3 -m pytest docs/boiler-room -q"""

import xml.etree.ElementTree as ET

from check_docs import svg_refs
from draw_panel_node import PANEL_NETS, render_panel_node
from draw_schematic import DEVKIT_LEFT, DEVKIT_RIGHT

ADC1 = {"IO32", "IO33", "IO34", "IO35", "IO36", "IO39"}       # ADC2 is dead while Wi-Fi runs


def text_of(svg: str) -> str:
    return " ".join(ET.fromstring(svg).itertext())


def test_nets_sit_on_real_devkit_pins_and_analog_inputs_on_adc1():
    pins = set(DEVKIT_LEFT + DEVKIT_RIGHT)
    assert set(PANEL_NETS) <= pins
    by_net = {net: pin for pin, net in PANEL_NETS.items()}
    assert by_net["VIN_OK"] in ADC1 and by_net["VBAT"] in ADC1
    # UART2 to the meter: ESP TX → PZEM RX, PZEM TX → ESP RX
    assert by_net["PZEM_TX"] == "IO17" and by_net["PZEM_RX"] == "IO16"


def test_sheet_has_meter_clamp_backup_power_and_dividers():
    svg = render_panel_node()
    _, refs = svg_refs(svg)
    assert {"A7", "A8", "TA1", "G3", "A9", "GB1", "QF7", "FU1", "R6", "R7", "R8", "R9", "C6", "C7"} <= refs
    txt = text_of(svg)
    for needle in ("PZEM-004T", "100 А", "18650", "MQTT", "+3V3", "VIN_OK", "VBAT"):
        assert needle in txt, needle


def test_divider_outputs_stay_below_3v3():
    from draw_panel_node import DIVIDERS
    for net, (v_in, r_top, r_bottom) in DIVIDERS.items():
        assert v_in * r_bottom / (r_top + r_bottom) <= 3.1, net
