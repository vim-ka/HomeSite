"""Controller settings table — mirror of the firmware SETTINGS table.

Source of truth: firmware/esp32-homesite/src/boiler_logic.cpp (SETTINGS[]).
Same keys, limits and defaults, so the emulator acks exactly like the device:
"ok" / "unknown_key" / "invalid_value".
"""

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Spec:
    kind: str  # bool | float | int | time | days
    lo: float = 0
    hi: float = 0
    default: str = ""


SETTINGS: dict[str, Spec] = {
    "heating_boiler_automode": Spec("bool", default="1"),
    "heating_boiler_power": Spec("bool", default="1"),
    "heating_boiler_temp": Spec("float", 30, 90, "50"),
    "heating_boiler_max_temp": Spec("float", 60, 90, "85"),
    "heating_radiator_pump": Spec("bool", default="1"),
    "heating_radiator_off_ihb": Spec("bool", default="1"),
    "heating_radiator_temp": Spec("float", 20, 90, "45"),
    "heating_floorheating_pump": Spec("bool", default="1"),
    "heating_floorheating_off_ihb": Spec("bool", default="0"),
    "heating_floorheating_temp": Spec("float", 20, 50, "30"),
    "watersupply_ihb_automode": Spec("bool", default="1"),
    "watersupply_ihb_pump": Spec("bool", default="1"),
    "watersupply_ihb_temp": Spec("float", 30, 75, "45"),
    "watersupply_ihb_teh_automode": Spec("bool", default="1"),
    "watersupply_ihb_teh_power": Spec("bool", default="0"),
    "watersupply_ihb_teh_heating_delay": Spec("int", 0, 240, "120"),  # minutes
    "watersupply_pump": Spec("bool", default="1"),
    "watersupply_pump_hot": Spec("bool", default="1"),
    "heating_autofill_enabled": Spec("bool", default="1"),
    "heating_pressure_min": Spec("float", 0.5, 2.0, "1.0"),
    "heating_pressure_max": Spec("float", 1.0, 2.8, "1.8"),
    "heating_radiator_schedule_enabled": Spec("bool", default="1"),
    "heating_radiator_schedule_days": Spec("days", default="1,2,3,4,5"),
    "heating_radiator_schedule_delta": Spec("float", -20, 10, "-10"),
    "heating_radiator_schedule_start": Spec("time", default="23:00"),
    "heating_radiator_schedule_end": Spec("time", default="06:00"),
    "heating_floorheating_schedule_enabled": Spec("bool", default="1"),
    "heating_floorheating_schedule_days": Spec("days", default="1,2,3,4,5"),
    "heating_floorheating_schedule_delta": Spec("float", -20, 10, "-5"),
    "heating_floorheating_schedule_start": Spec("time", default="23:00"),
    "heating_floorheating_schedule_end": Spec("time", default="06:00"),
    "watersupply_ihb_alm_mode": Spec("bool", default="1"),
    "watersupply_alm_temp": Spec("float", 55, 75, "60"),
    "watersupply_alm_days": Spec("days", default=""),
    "watersupply_alm_duration": Spec("int", 10, 240, "30"),
    "watersupply_alm_start_time": Spec("time", default="03:00"),
    "heating_radiator_wbm": Spec("bool", default="1"),
    "heating_radiator_curve": Spec("int", 1, 5, "3"),
    "heating_floorheating_wbm": Spec("bool", default="1"),
    "heating_floorheating_curve": Spec("int", 1, 5, "3"),
}

_TIME = re.compile(r"^\d{1,2}:\d{2}$")
_DAYS = re.compile(r"^([1-7](,[1-7])*)?$")


def is_valid(spec: Spec, value: str) -> bool:
    if spec.kind == "bool":
        return value in ("0", "1")
    if spec.kind in ("float", "int"):
        try:
            v = float(value)
        except ValueError:
            return False
        if not math.isfinite(v) or (spec.kind == "int" and v != int(v)):
            return False
        return spec.lo <= v <= spec.hi
    if spec.kind == "time":
        if not _TIME.match(value):
            return False
        h, m = (int(x) for x in value.split(":"))
        return 0 <= h <= 23 and 0 <= m <= 59
    if spec.kind == "days":
        return bool(_DAYS.match(value))
    return False


def defaults() -> dict[str, str]:
    return {k: s.default for k, s in SETTINGS.items()}
