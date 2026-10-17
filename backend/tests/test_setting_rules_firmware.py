"""Device settings in the allowlist mirror the firmware SETTINGS table (boiler_logic.cpp): same keys and limits.

The firmware rejects anything outside its limits with ack invalid_value, so a wider backend range would
let the UI save values the controller never applies.
"""

import re
from pathlib import Path

from app.core.setting_rules import RULES

FIRMWARE = Path(__file__).resolve().parents[2] / "firmware/esp32-homesite/src/boiler_logic.cpp"
ROW = re.compile(r'\{"(\w+)",\s*Kind::(\w+),\s*(-?[\d.]+),\s*(-?[\d.]+),\s*"([^"]*)"\}')
KINDS = {"Bool": "bool", "Float": "float", "Int": "int", "Time": "time", "Days": "days"}


def test_device_rules_match_the_firmware_table():
    body = FIRMWARE.read_text().split("const SettingSpec SETTINGS[] = {", 1)[1].split("};", 1)[0]
    fw = {k: (KINDS[kind], float(lo), float(hi)) for k, kind, lo, hi, _ in ROW.findall(body)}
    assert len(fw) > 40
    backend = {k: r for k, r in RULES.items() if r.device}
    assert set(backend) == set(fw)
    for key, (kind, lo, hi) in fw.items():
        rule = backend[key]
        assert rule.kind == kind, key
        if kind in ("float", "int"):
            assert (rule.min, rule.max) == (lo, hi), key
