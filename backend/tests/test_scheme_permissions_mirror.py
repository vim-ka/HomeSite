"""The scheme UI mirrors admin-only settings — keep both lists identical."""

import re
from pathlib import Path

from app.core.setting_rules import RULES

TS = Path(__file__).resolve().parents[2] / "frontend/src/scheme/permissions.ts"


def test_admin_only_keys_mirror_backend():
    text = TS.read_text(encoding="utf-8")
    block = re.search(r"ADMIN_ONLY_KEYS = \[(.*?)\]", text, re.S).group(1)
    ui = set(re.findall(r'"([a-z_]+)"', block))
    backend = {k for k, r in RULES.items() if r.admin_only and r.device}
    assert ui == backend
