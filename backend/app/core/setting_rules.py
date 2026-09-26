"""Allowlist and validation rules for runtime settings (config_kv).

Every key writable through ``PUT /settings`` / ``/settings/toggle`` must be
listed here. Device limits mirror the hard limits in the boiler firmware
(``firmware/esp32-homesite/src/boiler_logic.cpp``, SETTINGS table) — the
firmware rejects anything outside them with ack ``invalid_value``.
"""

import math
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from app.models.user import UserRole

Kind = Literal["bool", "float", "int", "time", "days", "enum", "str", "url", "rate"]


@dataclass(frozen=True)
class SettingRule:
    kind: Kind
    min: float | None = None
    max: float | None = None
    choices: tuple[str, ...] = ()
    # Safety limits and system parameters: admin only
    admin_only: bool = False
    # Setting is routed to a device (heating_* / watersupply_*)
    device: bool = False


def _dev(kind: Kind, lo: float | None = None, hi: float | None = None, admin: bool = False) -> SettingRule:
    return SettingRule(kind=kind, min=lo, max=hi, admin_only=admin, device=True)


def _sys(kind: Kind, lo: float | None = None, hi: float | None = None, choices: tuple[str, ...] = ()) -> SettingRule:
    return SettingRule(kind=kind, min=lo, max=hi, choices=choices, admin_only=True)


RULES: dict[str, SettingRule] = {
    # Boiler
    "heating_boiler_automode": _dev("bool"),
    "heating_boiler_power": _dev("bool"),
    "heating_boiler_temp": _dev("float", 30, 90),
    "heating_boiler_max_temp": _dev("float", 60, 90, admin=True),
    # Radiators / floor
    "heating_radiator_pump": _dev("bool"),
    "heating_radiator_off_ihb": _dev("bool"),
    "heating_radiator_temp": _dev("float", 20, 90),
    "heating_radiator_wbm": _dev("bool"),
    "heating_radiator_curve": _dev("int", 1, 5),
    "heating_radiator_schedule_enabled": _dev("bool"),
    "heating_radiator_schedule_days": _dev("days"),
    "heating_radiator_schedule_delta": _dev("float", -20, 10),
    "heating_radiator_schedule_start": _dev("time"),
    "heating_radiator_schedule_end": _dev("time"),
    "heating_floorheating_pump": _dev("bool"),
    "heating_floorheating_off_ihb": _dev("bool"),
    "heating_floorheating_temp": _dev("float", 20, 50),
    "heating_floorheating_wbm": _dev("bool"),
    "heating_floorheating_curve": _dev("int", 1, 5),
    "heating_floorheating_schedule_enabled": _dev("bool"),
    "heating_floorheating_schedule_days": _dev("days"),
    "heating_floorheating_schedule_delta": _dev("float", -20, 10),
    "heating_floorheating_schedule_start": _dev("time"),
    "heating_floorheating_schedule_end": _dev("time"),
    # Pressure / autofill (safety)
    "heating_autofill_enabled": _dev("bool"),
    "heating_pressure_min": _dev("float", 0.5, 2.0, admin=True),
    "heating_pressure_max": _dev("float", 1.0, 2.8, admin=True),
    # Water supply / IHB
    "watersupply_pump": _dev("bool"),
    "watersupply_pump_hot": _dev("bool"),
    "watersupply_ihb_automode": _dev("bool"),
    "watersupply_ihb_pump": _dev("bool"),
    "watersupply_ihb_temp": _dev("float", 30, 75),
    "watersupply_ihb_teh_automode": _dev("bool"),
    "watersupply_ihb_teh_power": _dev("bool"),
    "watersupply_ihb_teh_heating_delay": _dev("int", 0, 240),  # minutes
    "watersupply_ihb_alm_mode": _dev("bool"),
    "watersupply_alm_temp": _dev("float", 55, 75),
    "watersupply_alm_days": _dev("days"),
    "watersupply_alm_duration": _dev("int", 10, 240),
    "watersupply_alm_start_time": _dev("time"),
    # System (admin)
    "access_token_expire_minutes": _sys("int", 5, 1440),
    "refresh_token_expire_days": _sys("int", 1, 90),
    "sensor_stale_minutes": _sys("int", 1, 1440),
    "health_poll_seconds": _sys("int", 5, 3600),
    "gateway_timeout_seconds": _sys("int", 1, 60),
    "ack_timeout_seconds": _sys("int", 5, 600),
    "heartbeat_timeout_seconds": _sys("int", 30, 3600),
    "chart_history_days": _sys("int", 1, 3650),
    "frontend_poll_seconds": _sys("int", 2, 600),
    "mqtt_topic_prefix": _sys("str"),
    "log_level": _sys("enum", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")),
    "device_gateway_url": _sys("url"),
    "rate_limit_default": _sys("rate"),
    # Forward an outdoor sensor reading to a device for PZA (empty = disabled)
    "pza_outdoor_sensor": _sys("str"),
    "pza_outdoor_device": _sys("str"),
}

# Never returned by GET /settings (admin reads MQTT credentials via /settings/mqtt)
SECRET_KEYS = frozenset({"mqtt_pass"})

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
_DAYS_RE = re.compile(r"^([1-7](,[1-7])*)?$")
_RATE_RE = re.compile(r"^\d+/(second|minute|hour|day)$")
_STR_RE = re.compile(r"^[\w./#+-]{0,128}$")


class SettingsValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


class SettingsPermissionError(Exception):
    def __init__(self, keys: list[str]):
        super().__init__(f"admin role required for: {', '.join(keys)}")
        self.keys = keys


def _normalize(rule: SettingRule, raw: object) -> str:
    """Return the canonical string form or raise ValueError."""
    if rule.kind == "bool":
        if isinstance(raw, bool):
            return "1" if raw else "0"
        value = str(raw).strip().lower()
        if value in ("1", "true", "on"):
            return "1"
        if value in ("0", "false", "off"):
            return "0"
        raise ValueError("expected 0/1")

    if raw is None or isinstance(raw, bool):
        raise ValueError("value required")
    value = str(raw).strip()

    if rule.kind in ("float", "int"):
        try:
            num = float(value)
        except ValueError:
            raise ValueError("not a number") from None
        if not math.isfinite(num):
            raise ValueError("not a number")
        if rule.kind == "int":
            if num != int(num):
                raise ValueError("expected an integer")
            value = str(int(num))
        else:
            value = f"{num:g}"
        if rule.min is not None and num < rule.min or rule.max is not None and num > rule.max:
            raise ValueError(f"must be between {rule.min:g} and {rule.max:g}")
        return value

    if rule.kind == "time":
        if not _TIME_RE.match(value):
            raise ValueError("expected HH:MM")
        h, m = value.split(":")
        return f"{int(h):02d}:{m}"
    if rule.kind == "days":
        if not _DAYS_RE.match(value):
            raise ValueError("expected comma-separated days 1-7")
        return value
    if rule.kind == "enum":
        if value.upper() not in rule.choices:
            raise ValueError(f"expected one of {', '.join(rule.choices)}")
        return value.upper()
    if rule.kind == "url":
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("expected http(s) URL")
        return value.rstrip("/")
    if rule.kind == "rate":
        if not _RATE_RE.match(value):
            raise ValueError("expected N/second|minute|hour|day")
        return value
    if not _STR_RE.match(value):
        raise ValueError("invalid characters")
    return value


def validate_settings(
    updates: dict[str, object],
    current: dict[str, str],
    role: str,
) -> dict[str, str]:
    """Validate and normalize a settings update.

    Raises SettingsPermissionError (403) or SettingsValidationError (422).
    """
    errors: dict[str, str] = {}
    forbidden: list[str] = []
    normalized: dict[str, str] = {}

    for key, raw in updates.items():
        rule = RULES.get(key)
        if rule is None:
            errors[key] = "unknown setting"
            continue
        if rule.admin_only and role != UserRole.ADMIN.value:
            forbidden.append(key)
            continue
        try:
            normalized[key] = _normalize(rule, raw)
        except ValueError as e:
            errors[key] = str(e)

    if forbidden:
        raise SettingsPermissionError(forbidden)

    # Cross-field checks against the merged (current + new) state
    merged = {**current, **normalized}

    def _num(key: str) -> float | None:
        try:
            return float(merged[key])
        except (KeyError, ValueError):
            return None

    p_min, p_max = _num("heating_pressure_min"), _num("heating_pressure_max")
    if p_min is not None and p_max is not None and p_min >= p_max:
        errors.setdefault("heating_pressure_min", "must be lower than heating_pressure_max")
    b_temp, b_max = _num("heating_boiler_temp"), _num("heating_boiler_max_temp")
    if b_temp is not None and b_max is not None and b_temp > b_max:
        errors.setdefault("heating_boiler_temp", "must not exceed heating_boiler_max_temp")

    if errors:
        raise SettingsValidationError(errors)
    return normalized


def is_device_setting(key: str) -> bool:
    rule = RULES.get(key)
    return rule is not None and rule.device
