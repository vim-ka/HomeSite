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
                "tank_load_min", "dn_collector", "air_combustion_m3h"):
        assert key in data, key
    # catalogue sizes only
    assert data["exp_heating_l"] in (8, 12, 18, 24, 35, 50)
    assert data["exp_dhw_l"] in (8, 12, 18, 24)


def test_loading_pump_moves_less_than_the_boiler_so_the_separator_never_reverses():
    r = _report()
    assert r["flow_ihb_m3h"] <= 0.9 * r["flow_boiler_m3h"]


def test_collector_bore_carries_the_sum_of_its_outlets():
    r = _report()
    bore = dict(PIPES)
    outlet = bore[r["dn_boiler"]]
    assert bore[r["dn_collector"]] ** 2 >= 3 * outlet ** 2


def test_combustion_air_uses_methane_stoichiometry():
    # ~9.5 m³ air per m³ CH4; 28 kW ≈ 3 m³/h gas → ~28–32 m³/h theoretical
    assert 25 <= _report()["air_combustion_m3h"] <= 35


def test_tank_loading_time_accounts_for_the_coil_at_low_supply_temperature():
    assert _report()["tank_load_min"] >= 35


def _report():
    from calc import report
    return report()
