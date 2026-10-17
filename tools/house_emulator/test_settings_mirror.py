"""The emulator's settings table mirrors the firmware SETTINGS table exactly (keys, kinds, limits, defaults).

Run: cd tools && python -m pytest house_emulator
"""

import re
from pathlib import Path

from house_emulator.settings import SETTINGS

FIRMWARE = Path(__file__).resolve().parents[2] / "firmware/esp32-homesite/src/boiler_logic.cpp"
ROW = re.compile(r'\{"(\w+)",\s*Kind::(\w+),\s*(-?[\d.]+),\s*(-?[\d.]+),\s*"([^"]*)"\}')


def firmware_table() -> dict[str, tuple[str, float, float, str]]:
    body = FIRMWARE.read_text().split("const SettingSpec SETTINGS[] = {", 1)[1].split("};", 1)[0]
    return {k: (kind.lower(), float(lo), float(hi), d) for k, kind, lo, hi, d in ROW.findall(body)}


def test_same_keys_kinds_limits_and_defaults():
    fw = firmware_table()
    assert len(fw) > 40                                      # the parser found the table
    emu = {k: (s.kind, float(s.lo), float(s.hi), s.default) for k, s in SETTINGS.items()}
    assert emu == fw


def test_the_tank_is_the_same_sensor_in_the_firmware_and_the_emulator():
    """The tank logic (loading pump, TEH, anti-legionella) reads the sensor in the tank, never a loading pipe."""
    from house_emulator.controller import TANK_SENSOR

    src = FIRMWARE.read_text()
    assert f'TANK_SENSOR = "{TANK_SENSOR}"' in src
    assert 'getTemp(temps, "tsihb_s")' not in src
