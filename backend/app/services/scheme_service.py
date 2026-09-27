"""State of the boiler room scheme page: sensors by role, controller, sync, alarms.

One place maps scheme roles to sensors:
- circuit supply/return — mount points of heating_circuits (by config_prefix),
  exactly like the dashboard;
- water — fixed sensor names; pressure — a bound "prs" sensor if the catalog has
  one, otherwise the value the controller reports in its heartbeat.
"""

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.setting_rules import SECRET_KEYS
from app.models.event import EventLog
from app.services.controller_flags import CONTROLLER_FLAGS
from app.models.heating import HeatingCircuit
from app.models.sensor import MountPoint, Sensor, SensorData, SensorDataType
from app.repositories.sensor_repository import CLIMATE_SYSTEM_ID, SensorRepository
from app.repositories.settings_repository import SettingsRepository

CONTROLLER_DEVICE = "boiler_unit"
HEATING_SYSTEM_ID = 1
WATER_SYSTEM_ID = 2
# Same order as firmware RelayChannel (relay_controller.h)
RELAY_NAMES = [
    "boiler", "rad_pump", "floor_pump", "ihb_pump", "water_pump", "water_hot_pump", "teh",
    "af_open", "af_close", "rad_open", "rad_close", "floor_open", "floor_close",
    "lamp_warning", "lamp_critical", "spare",
]
CIRCUIT_ROLES = {
    "heating_boiler": ("boiler_supply", "boiler_return"),
    "heating_radiator": ("rad_supply", "rad_return"),
    "heating_floorheating": ("floor_supply", "floor_return"),
    "watersupply_ihb": ("tank", "coil_return"),
}
WATER_SENSORS = {"cold_water": "tswatersupply_c", "hot_water": "tswatersupply_h"}
UNHEATED_SENSORS = {"clm_garage_th"}
BOILER_ROOM_SENSOR = "clm_boiler_th"
FLAG_KEYS = [
    "warning", "critical", "alm_active", "schedule_rad", "schedule_floor", "ihb_heating",
    "autofill_active", "autofill_closing", "boiler_auto", *CONTROLLER_FLAGS,
]
ALL_ROLES = [r for pair in CIRCUIT_ROLES.values() for r in pair] + [
    "cold_water", "hot_water", "heating_pressure", "water_pressure", "outdoor", "indoor_avg", "boiler_room",
]

GatewayFetch = Callable[[], Awaitable[dict | None]]


def _utc(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def _iso(ts: datetime | None) -> str | None:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None


def _reading(value: float | None, ts: datetime | None, stale_before: datetime, source: str = "sensor") -> dict:
    ts = _utc(ts)
    stale = value is None or ts is None or ts < stale_before
    return {"value": value, "ts": _iso(ts), "stale": stale, "source": source}


def decode_relays(mask: int | None) -> dict[str, bool]:
    mask = mask or 0
    return {name: bool(mask & (1 << i)) for i, name in enumerate(RELAY_NAMES)}


class CachedFetch:
    """Share one gateway /health response between requests for a short time.

    Every open scheme tab polls every 2–10 s; without this each poll is an HTTP
    call to the gateway.
    """

    def __init__(self, fetch: GatewayFetch, ttl: float = 1.5, now: Callable[[], float] = time.monotonic):
        self._fetch = fetch
        self._ttl = ttl
        self._now = now
        self._at: float | None = None
        self._value: dict | None = None

    async def __call__(self) -> dict | None:
        now = self._now()
        if self._at is None or now - self._at >= self._ttl:
            self._value = await self._fetch()
            self._at = now
        return self._value


async def fetch_gateway_health(url: str, timeout: float) -> dict | None:
    try:
        async with httpx.AsyncClient(base_url=url, timeout=timeout) as client:
            resp = await client.get("/health")
            return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def _num(settings: dict[str, str], key: str, default: float | None = None) -> float | None:
    try:
        return float(settings[key])
    except (KeyError, ValueError):
        return default


class SchemeService:
    def __init__(self, db: AsyncSession, fetch_gateway: GatewayFetch):
        self.db = db
        self.fetch_gateway = fetch_gateway
        self.heartbeat_data: dict = {}

    async def _latest_temps(self) -> dict[int, tuple[float, datetime]]:
        rows = await self.db.execute(
            select(SensorData.sensor_id, SensorData.value, SensorData.timestamp)
            .join(SensorDataType, SensorDataType.id == SensorData.datatype_id)
            .where(SensorDataType.code == "tmp")
        )
        return {sid: (value, ts) for sid, value, ts in rows}

    async def _latest_pressure(self, system_id: int) -> tuple[float, datetime] | None:
        """A pressure sensor bound in the catalog (mount point pressure_sensor_id)."""
        row = (await self.db.execute(
            select(SensorData.value, SensorData.timestamp)
            .join(SensorDataType, SensorDataType.id == SensorData.datatype_id)
            .join(MountPoint, MountPoint.pressure_sensor_id == SensorData.sensor_id)
            .where(SensorDataType.code == "prs", MountPoint.system_id == system_id)
            .order_by(desc(SensorData.timestamp)).limit(1)
        )).first()
        return (row[0], row[1]) if row else None

    async def build_state(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        settings_all = await SettingsRepository(self.db).get_all()
        settings = {k: v for k, v in settings_all.items() if k not in SECRET_KEYS}
        stale_minutes = int(_num(settings_all, "sensor_stale_minutes", 5) or 5)
        hb_timeout = int(_num(settings_all, "heartbeat_timeout_seconds", 60) or 60)
        stale_before = now - timedelta(minutes=stale_minutes)

        temps = await self._latest_temps()
        names = dict((await self.db.execute(select(Sensor.name, Sensor.id))).all())
        values: dict[str, dict] = {role: _reading(None, None, stale_before) for role in ALL_ROLES}

        def put(role: str, sensor_id: int | None) -> None:
            if sensor_id is not None and sensor_id in temps:
                value, ts = temps[sensor_id]
                values[role] = _reading(round(float(value), 2), ts, stale_before)

        circuits = (await self.db.execute(select(HeatingCircuit))).scalars().all()
        mp_sensor = dict((await self.db.execute(select(MountPoint.id, MountPoint.temperature_sensor_id))).all())
        for c in circuits:
            roles = CIRCUIT_ROLES.get(c.config_prefix or "")
            if roles:
                put(roles[0], mp_sensor.get(c.supply_mount_point_id))
                put(roles[1], mp_sensor.get(c.return_mount_point_id))
        for role, name in WATER_SENSORS.items():
            put(role, names.get(name))
        put("boiler_room", names.get(BOILER_ROOM_SENSOR))
        outdoor_id = await SensorRepository(self.db).get_outdoor_sensor_id()
        put("outdoor", outdoor_id)

        excluded = {outdoor_id, names.get(BOILER_ROOM_SENSOR)} | {names.get(n) for n in UNHEATED_SENSORS}
        climate = (await self.db.execute(
            select(Sensor.id, MountPoint.name).join(MountPoint, MountPoint.id == Sensor.mount_point_id)
            .where(MountPoint.system_id == CLIMATE_SYSTEM_ID).order_by(MountPoint.id)
        )).all()
        climate_ids = [sid for sid, _ in climate]
        # heated rooms one by one (by their place name) — the alarm rules watch each of them
        rooms = [{"name": mp_name, **(_reading(round(float(temps[sid][0]), 1), temps[sid][1], stale_before)
                                      if sid in temps else _reading(None, None, stale_before))}
                 for sid, mp_name in climate if sid not in excluded]
        fresh = [temps[i] for i in climate_ids if i not in excluded and i in temps
                 and _utc(temps[i][1]) >= stale_before]
        if fresh:
            values["indoor_avg"] = _reading(round(sum(v for v, _ in fresh) / len(fresh), 1),
                                            max(_utc(ts) for _, ts in fresh), stale_before)

        # Controller via gateway
        gw = await self.fetch_gateway()
        gateway_ok = gw is not None
        hb = (gw or {}).get("heartbeats", {}).get(CONTROLLER_DEVICE)
        last_seen = _utc(datetime.fromisoformat(hb["timestamp"])) if hb and hb.get("timestamp") else None
        online = last_seen is not None and (now - last_seen).total_seconds() < hb_timeout
        data = (hb or {}).get("data", {}) if online else {}
        self.heartbeat_data = data  # raw, for the alarm rules (PZA without outdoor, anti-legionella result)
        flags = {k: bool(data.get(k, False)) for k in FLAG_KEYS}
        controller = {
            "online": online,
            "last_seen": _iso(last_seen),
            "relays": decode_relays(data.get("relays")),
            "flags": flags,
            "targets": {
                "boiler": data.get("boiler_auto_target"), "rad": data.get("rad_target"),
                "floor": data.get("floor_target"), "ihb": data.get("ihb_target"),
            },
        }

        # Pressure: a fresh catalog sensor first, otherwise what the controller reports
        for role, system, hb_key in (
            ("heating_pressure", HEATING_SYSTEM_ID, "prs_heat"), ("water_pressure", WATER_SYSTEM_ID, "prs_water"),
        ):
            bound = await self._latest_pressure(system)
            bound_reading = _reading(round(float(bound[0]), 2), bound[1], stale_before) if bound else None
            if bound_reading and not bound_reading["stale"]:
                values[role] = bound_reading
            elif hb and hb.get("data", {}).get(hb_key) is not None:
                values[role] = _reading(float(hb["data"][hb_key]), last_seen, now - timedelta(seconds=hb_timeout), "heartbeat")
                if not online:
                    values[role]["stale"] = True
            elif bound_reading:
                values[role] = bound_reading  # stale, but better than nothing

        sync = (gw or {}).get("sync", {}).get(CONTROLLER_DEVICE, {})
        events = (await self.db.execute(select(EventLog).order_by(desc(EventLog.timestamp)).limit(3))).scalars().all()

        return {
            "generated_at": _iso(now),
            "values": values,
            "rooms": rooms,
            "controller": controller,
            "settings": settings,
            "sync": {"pending": list(sync.get("pending", [])), "unsynced": list(sync.get("unsynced", []))},
            "events": [{"ts": _iso(_utc(e.timestamp)), "level": e.level, "text": e.message or ""} for e in events],
            "stale_minutes": stale_minutes,
        }
