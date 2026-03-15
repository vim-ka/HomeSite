"""PZA (погодозависимая автоматика) — supply temperature calculation.

Curves match frontend/src/lib/pzaCurves.ts and firmware/pza_controller.cpp.
"""

OUTDOOR_TEMPS = [20, 10, 0, -10, -20, -35]

RADIATOR_CURVES = [
    [20, 29, 38, 44, 50, 55],
    [20, 32.5, 45, 52.5, 60, 67],
    [20, 34, 48, 56, 64, 70],
    [20, 36.5, 53, 61.5, 70, 78],
    [20, 39, 58, 67, 76, 85],
]

FLOOR_CURVES = [
    [20, 22, 24, 26, 28, 29.5],
    [20, 23.5, 27, 29.5, 32, 34],
    [20, 23.5, 27, 30, 33, 36],
    [20, 24.5, 29, 32, 35, 38],
    [20, 25.5, 31, 34, 37, 40],
]


def interpolate_pza(curve_data: list[float], outdoor_temp: float) -> float:
    """Interpolate supply temperature from outdoor temperature using a PZA curve."""
    if outdoor_temp >= OUTDOOR_TEMPS[0]:
        return curve_data[0]
    if outdoor_temp <= OUTDOOR_TEMPS[-1]:
        return curve_data[-1]

    for i in range(len(OUTDOOR_TEMPS) - 1):
        o0 = OUTDOOR_TEMPS[i]
        o1 = OUTDOOR_TEMPS[i + 1]
        if outdoor_temp <= o0 and outdoor_temp >= o1:
            t = (o0 - outdoor_temp) / (o0 - o1)
            return round(curve_data[i] + t * (curve_data[i + 1] - curve_data[i]), 1)

    return curve_data[0]


def get_pza_target(
    circuit_type: str,
    curve_index: int,
    outdoor_temp: float,
) -> float | None:
    """Get target supply temperature for a circuit.

    circuit_type: "radiator" or "floor"
    curve_index: 1-5
    outdoor_temp: current outdoor temperature
    """
    curves = RADIATOR_CURVES if circuit_type == "radiator" else FLOOR_CURVES
    idx = max(0, min(curve_index - 1, len(curves) - 1))
    return interpolate_pza(curves[idx], outdoor_temp)
