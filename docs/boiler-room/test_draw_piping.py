"""Tests for draw_piping.py — run: python3 -m pytest docs/boiler-room -q"""

import xml.etree.ElementTree as ET

from check_docs import svg_refs
from draw_piping import render

SENSORS = {"BK1": "tsboiler_s", "BK2": "tsboiler_b", "BK3": "tsrad_s", "BK4": "tsrad_b", "BK5": "tsfloor_s",
           "BK6": "tsfloor_b", "BK7": "tsihb_s", "BK8": "tsihb_b", "BK9": "tswatersupply_c", "BK10": "tswatersupply_h"}


def test_gost_sheet_is_valid_svg_with_every_hydraulic_position():
    svg = render("gost")
    pos, refs = svg_refs(svg)
    assert {str(p) for p in range(1, 20)} <= pos            # equipment 1–19
    assert {str(p) for p in (20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33, 34, 36, 37, 38, 39, 40, 41, 42,
                             43, 44, 45, 46, 47, 48)} <= pos
    assert {"M1", "M2", "M3", "M4", "M5", "YA1", "YA2", "YA3", "YA4", "EK1", "BP1", "BP2", "SK1", "SK2", "SP1",
            "A5"} <= refs
    assert set(SENSORS) <= refs


def test_each_sensor_is_labelled_with_its_database_name():
    root = ET.fromstring(render("gost"))
    for ref, name in SENSORS.items():
        g = next(el for el in root.iter() if el.get("data-ref") == ref)
        assert name in "".join(g.itertext()), ref


def test_pipe_codes_follow_gost_21_206():
    text = "".join(ET.fromstring(render("gost")).itertext())
    for code in ("Т1", "Т2", "Т3", "Т4", "В1", "Г1"):
        assert code in text, code


def test_colour_overview_keeps_the_main_equipment_and_drops_small_fittings():
    pos, refs = svg_refs(render("color"))
    assert {"1", "2", "3", "4", "5", "6", "7", "8", "11", "12", "13"} <= pos
    # the reviewer looks for these on the overview too: water treatment, DHW mixer, safety, filters, reducer
    assert {"18", "19", "20", "21", "23", "36"} <= pos
    assert "22" not in pos and "25" not in pos


def test_colour_overview_uses_site_colours():
    svg = render("color")
    assert "#ef4444" in svg and "#3b82f6" in svg      # supply red, return blue


def _group(svg: str, pos: str):
    import xml.etree.ElementTree as ET
    return next(el for el in ET.fromstring(svg).iter() if el.get("data-pos") == pos)


def test_boiler_cannot_be_isolated_from_its_safety_group_and_expansion_tank():
    # boiler on the right: "boiler side" of a shut-off = larger x
    from draw_piping import BOILER_SIDE
    assert BOILER_SIDE["safety_group"] > BOILER_SIDE["supply_valve"]
    assert BOILER_SIDE["tank_tee"] > BOILER_SIDE["return_valve"]
    # the boiler filter is cleaned with the boiler valves shut: it sits on the boiler side too
    assert BOILER_SIDE["filter"] > BOILER_SIDE["return_valve"]


def test_separator_takes_boiler_supply_high_and_gives_boiler_return_low():
    from draw_piping import SEPARATOR
    s = SEPARATOR
    assert s["boiler_supply_y"] < s["collector_supply_y"]      # air goes up to the vent
    assert s["boiler_return_y"] > s["collector_return_y"]      # sludge settles at the bottom


def test_make_up_reaches_the_system_through_a_reducer_and_a_flow_limiter():
    from draw_piping import MAKE_UP_ORDER
    # in flow order: shut-off, strainer, reducer, check, limiter, motorised valve — bypass around the last two
    assert MAKE_UP_ORDER == ["29", "29", "36", "29", "37", "13"]


def test_recirculation_pump_points_down_the_loop_towards_the_tank():
    import re
    m5 = _group(render("gost"), "10")
    assert re.search(r"translate\(95 330\) rotate\(90\)", ET.tostring(m5, encoding="unicode"))
