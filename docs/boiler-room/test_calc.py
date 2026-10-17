"""Tests for calc.py — run: python3 -m pytest docs/boiler-room -q"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from calc import PIPES, expansion_tank_l, flow_m3h, pick_pipe, velocity_ms


def test_flow_is_heat_over_capacity_and_delta():
    # 10 kW at ΔT 10 K: 10 / (1.163 · 10) ≈ 0.86 m³/h
    assert flow_m3h(10, 10) == pytest.approx(0.86, abs=0.01)


def test_velocity_in_a_known_bore():
    # 1 m³/h through 25.6 mm bore: 1/3600 / (π·0.0256²/4) ≈ 0.54 m/s
    assert velocity_ms(1.0, 25.6) == pytest.approx(0.54, abs=0.01)


def test_pick_pipe_takes_the_smallest_within_the_speed_limit():
    od, v = pick_pipe(1.0, 0.8)
    assert od == 28 and v <= 0.8                      # 22×1.2 (bore 19.6) would run at 0.92 m/s
    smaller = [p for p in PIPES if p[0] < od]
    assert all(velocity_ms(1.0, bore) > 0.8 for _, bore in smaller)


def test_pick_pipe_refuses_a_flow_no_size_carries():
    with pytest.raises(ValueError):
        pick_pipe(50.0, 0.8)


def test_expansion_tank_textbook_case():
    # 100 L, e = 0.04, P0 1 bar, Pmax 2.5 bar, no reserve: 4 / (1 − 2/3.5) = 9.33 L
    assert expansion_tank_l(100, 0.04, 1.0, 2.5, reserve_l=0) == pytest.approx(9.33, abs=0.01)


def test_json_report_has_every_key_the_docs_quote():
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("calc.py")), "--json"],
                         capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    for key in ("heat_load_kw", "flow_boiler_m3h", "flow_rad_m3h", "flow_floor_m3h", "flow_ihb_m3h",
                "dn_boiler", "dn_rad", "dn_floor", "dn_ihb", "system_volume_l", "exp_heating_l", "exp_dhw_l",
                "tank_load_min"):
        assert key in data, key
    # catalogue sizes only
    assert data["exp_heating_l"] in (8, 12, 18, 24, 35, 50)
    assert data["exp_dhw_l"] in (8, 12, 18, 24)
