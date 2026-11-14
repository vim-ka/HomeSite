"""Boiler room sizing — enlarged (укрупнённый) calculation, reproducible.

Usage: python3 docs/boiler-room/calc.py          (readable report)
       python3 docs/boiler-room/calc.py --json   (numbers quoted by the documents)

Every input below is either the owner's data or a marked assumption (ДОПУЩЕНИЕ); 04-calculations.md explains them.
"""

import json
import math
import sys

# --- Owner's data ---
HOUSE_M2 = 200
FLOOR_M2 = 80
RADIATORS, SECTIONS_EACH = 15, 8
BOILER_KW = 28
TANK_L, COIL_KW = 200, 30

# --- Assumptions (ДОПУЩЕНИЕ) ---
SPECIFIC_LOSS_W_M2 = 100       # дом средней утеплённости, потолки ~2,7 м, −25…−30 °C расчётная
FLOOR_W_M2 = 60                # тёплый пол при подаче 35–40 °C
DT = {"boiler": 15, "rad": 20, "floor": 5}   # K: котёл, радиаторы 80/60 (как проверка мощности 4.2), пол
IHB_SHARE = 0.85              # насос загрузки БКН берёт ≤ 85 % расхода котла — гидрострелка не опрокидывается (kotelna.tk 1-1-8-13)
COIL_DERATE = 0.55            # змеевик при подаче ~65 °C отдаёт ~55 % паспортных 30 кВт (паспорт — при 80/60, 10→45 °C)
GAS_KWH_PER_M3, AIR_PER_GAS = 9.3, 9.5   # теплота сгорания метана (низшая), стехиометрия воздух/газ
SPEED_LIMIT = {"boiler": 1.0, "rad": 0.8, "floor": 0.8, "ihb": 1.0}   # м/с: котельная / магистрали
L_PER_SECTION = 0.35           # алюминий/биметалл, л на секцию
FLOOR_PIPE_M_PER_M2, FLOOR_PIPE_L_PER_M = 6.7, 0.113    # шаг 150 мм, труба 16×2
DISTRIBUTION_L = 40            # разводка по дому
BOILER_ROOM_PIPES_L = 10       # трубы котельной
BOILER_L, COIL_L, SEPARATOR_L = 2, 9, 10
VOLUME_MARGIN = 1.10
T_MAX_HEATING, E_HEATING = 90, 0.0359   # расширение воды 10 → 90 °C
T_MAX_DHW, E_DHW = 70, 0.0227           # 10 → 70 °C (анти-легионелла)
STATIC_BAR = 0.8               # высота системы над баком ~6 м + 0,2 бар
SAFETY_HEATING_BAR, SAFETY_DHW_BAR = 3.0, 6.0
WELL_MAX_BAR = 3.0             # верхний порог реле давления скважины (по датчику ~2,9–3,1 бар)
BOILER_INTERNAL_EXP_L = 8      # встроенный бак настенного котла — уточнить по паспорту
TANK_COLD_C, TANK_HOT_C, LOAD_EFFICIENCY = 10, 55, 0.9

# Stainless press-fit (V-profile) — outside diameter × wall, mm → bore
PIPES = [(15, 13.0), (18, 16.0), (22, 19.6), (28, 25.6), (35, 32.0), (42, 39.0), (54, 51.0)]
TANK_SIZES = [8, 12, 18, 24, 35, 50]


def flow_m3h(kw: float, dt: float) -> float:
    """G = Q / (c·ΔT), water c = 1.163 Wh/(kg·K)."""
    return kw / (1.163 * dt)


def velocity_ms(m3h: float, bore_mm: float) -> float:
    return m3h / 3600 / (math.pi * (bore_mm / 1000) ** 2 / 4)


def pick_pipe(m3h: float, limit_ms: float) -> tuple[int, float]:
    """Smallest outside diameter whose speed stays within the limit → (OD, speed)."""
    for od, bore in PIPES:
        v = velocity_ms(m3h, bore)
        if v <= limit_ms:
            return od, v
    raise ValueError(f"{m3h:.2f} м³/ч не проходит ни в одну трубу при {limit_ms} м/с")


def expansion_tank_l(volume_l: float, e: float, p0_bar: float, pmax_bar: float, reserve_l: float) -> float:
    """Membrane tank: (V·e + reserve) / (1 − (P0 + 1) / (Pmax + 1)), pressures gauge."""
    return (volume_l * e + reserve_l) / (1 - (p0_bar + 1) / (pmax_bar + 1))


def next_size(litres: float) -> int:
    return next(s for s in TANK_SIZES if s >= litres)


def report() -> dict:
    heat = HOUSE_M2 * SPECIFIC_LOSS_W_M2 / 1000
    floor_kw = FLOOR_M2 * FLOOR_W_M2 / 1000
    loads = {"boiler": BOILER_KW, "rad": heat - floor_kw, "floor": floor_kw}
    r: dict = {"heat_load_kw": round(heat, 1), "rad_kw": round(loads["rad"], 1), "floor_kw": round(floor_kw, 1)}
    flows = {k: flow_m3h(kw, DT[k]) for k, kw in loads.items()}
    flows["ihb"] = flows["boiler"] * IHB_SHARE
    for k, g in flows.items():
        od, v = pick_pipe(g, SPEED_LIMIT[k])
        r[f"flow_{k}_m3h"] = round(g, 2)
        r[f"dn_{k}"] = od
        r[f"v_{k}_ms"] = round(v, 2)
        # 3-way valve Kvs at 10 kPa (0.1 bar) across it, rounded up to the series 2.5 / 4 / 6.3
        if k in ("rad", "floor"):
            r[f"kvs_{k}"] = next(s for s in (1.6, 2.5, 4.0, 6.3, 10.0) if s >= g / math.sqrt(0.1))

    floor_l = FLOOR_M2 * FLOOR_PIPE_M_PER_M2 * FLOOR_PIPE_L_PER_M
    parts = {"котёл": BOILER_L, "радиаторы": RADIATORS * SECTIONS_EACH * L_PER_SECTION, "тёплый пол": floor_l,
             "разводка": DISTRIBUTION_L, "трубы котельной": BOILER_ROOM_PIPES_L, "змеевик БКН": COIL_L,
             "гидрострелка и коллектор": SEPARATOR_L}
    volume = sum(parts.values()) * VOLUME_MARGIN
    r["volume_parts_l"] = {k: round(v) for k, v in parts.items()}
    r["system_volume_l"] = round(volume)

    pmax_h = SAFETY_HEATING_BAR - 0.5
    reserve = max(3.0, 0.005 * volume)
    need_h = expansion_tank_l(volume, E_HEATING, STATIC_BAR + 0.2, pmax_h, reserve)
    r["exp_heating_need_l"] = round(need_h, 1)
    r["exp_heating_external_min_l"] = round(max(0.0, need_h - BOILER_INTERNAL_EXP_L), 1)
    # the external tank alone covers the system: the built-in one is a reserve, not counted on
    r["exp_heating_l"] = next_size(need_h)
    r["exp_heating_p0_bar"] = STATIC_BAR + 0.2
    r["fill_bar"] = round(STATIC_BAR + 0.2 + 0.3, 1)

    pmax_d = SAFETY_DHW_BAR - 0.5
    need_d = expansion_tank_l(TANK_L, E_DHW, WELL_MAX_BAR, pmax_d, 0)
    r["exp_dhw_need_l"] = round(need_d, 1)
    r["exp_dhw_l"] = next_size(need_d)
    r["exp_dhw_p0_bar"] = WELL_MAX_BAR

    # collector: bore area ≥ sum of its three outlets (boiler-size pipes)
    outlet = dict(PIPES)[r["dn_boiler"]]
    r["dn_collector"] = next(od for od, bore in PIPES if bore ** 2 >= 3 * outlet ** 2)

    kwh = TANK_L * 4.19 * (TANK_HOT_C - TANK_COLD_C) / 3600
    coil_kw = min(BOILER_KW, COIL_KW * COIL_DERATE)
    r["tank_load_kwh"] = round(kwh, 1)
    r["coil_kw_at_65"] = round(coil_kw, 1)
    r["tank_load_min"] = round(kwh / (coil_kw * LOAD_EFFICIENCY) * 60)

    gas = BOILER_KW / 0.9 / GAS_KWH_PER_M3           # м³/ч при КПД 90 %
    r["gas_m3h"] = round(gas, 2)
    r["air_combustion_m3h"] = round(gas * AIR_PER_GAS)
    return r


def main() -> None:
    r = report()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False))
        return
    for k, v in r.items():
        print(f"{k:28} {v}")


if __name__ == "__main__":
    main()
