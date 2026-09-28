"""Background health monitor — single source of truth for service/sensor status.

Caches state in memory, writes EventLog on changes. Health endpoints read cached state.
"""

import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.models.config import Actuator, ConfigKV
from app.models.event import EventLog
from app.models.pending_sensor import PendingSensor
from app.models.sensor import MountPoint, Sensor, SensorData
from app.services.alarm_rules import Alarm, AlarmTracker, Snapshot, evaluate, unknown
from app.services.scheme_service import SchemeService

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_STALE_MINUTES = 5

# Safety flags reported in the boiler controller heartbeat → event text


@dataclass
class HealthState:
    """Cached health state — read by /health/* endpoints."""

    # Services
    backend: bool = True
    database: bool = False
    gateway: bool = False
    mqtt: bool = False

    # Sensors
    sensor_total: int = 0
    sensor_active: int = 0
    sensor_pending: int = 0

    # Devices (actuators with heartbeat)
    device_total: int = 0
    device_online: int = 0

    # Pending commands awaiting ack
    pending_commands: int = 0
    unsynced_commands: int = 0

    # Alarms active right now (most severe first) — the scheme panel and the header read these
    active_alarms: list[dict] = field(default_factory=list)

    # Config (exposed to frontend)
    poll_seconds: int = DEFAULT_POLL_INTERVAL

    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class HealthMonitor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        gateway_url: str,
    ):
        self.session_factory = session_factory
        self.gateway_url = gateway_url
        self.state = HealthState()

        # Previous state for change detection
        self._prev_active_sensor_ids: set[int] = set()
        self._prev_pending_names: set[str] = set()
        self._initialized = False
        self.alarms = AlarmTracker()
        self._now = lambda: datetime.now(UTC)  # replaceable clock (tests)

    async def run(self) -> None:
        """Main loop — polls at configured interval."""
        while True:
            try:
                await self._check()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("health_monitor_error", error=str(e))
                # Don't keep serving the last "all good" snapshot: the failing
                # part is almost always the DB (session / config query)
                self.state = replace(self.state, database=False)
            await asyncio.sleep(self._poll_interval)

    @property
    def _poll_interval(self) -> int:
        return self.state.poll_seconds if hasattr(self.state, "poll_seconds") else DEFAULT_POLL_INTERVAL

    async def _check(self) -> None:
        async with self.session_factory() as session:
            events: list[EventLog] = []

            # --- Load config from config_kv ---
            config_keys = [
                "sensor_stale_minutes", "health_poll_seconds", "gateway_timeout_seconds",
                "heating_pressure_min", "heating_pressure_max", "heating_boiler_max_temp",
                "heartbeat_timeout_seconds",
            ]
            result = await session.execute(
                select(ConfigKV.key, ConfigKV.value).where(ConfigKV.key.in_(config_keys))
            )
            kv = {r[0]: r[1] for r in result}

            stale_minutes = DEFAULT_STALE_MINUTES
            try:
                stale_minutes = int(kv.get("sensor_stale_minutes", DEFAULT_STALE_MINUTES))
            except ValueError:
                pass

            poll_seconds = DEFAULT_POLL_INTERVAL
            try:
                poll_seconds = int(kv.get("health_poll_seconds", DEFAULT_POLL_INTERVAL))
            except ValueError:
                pass

            gateway_timeout = 3.0
            try:
                gateway_timeout = float(kv.get("gateway_timeout_seconds", "3"))
            except ValueError:
                pass

            # --- Service checks (their alarms come from the rules below) ---
            services, gateway_health = await self._check_services(session, gateway_timeout)

            # --- Sensor activity checks ---
            now = self._now()
            stale_threshold = now - timedelta(minutes=stale_minutes)

            result = await session.execute(select(Sensor.id))
            all_ids = {row[0] for row in result}

            result = await session.execute(
                select(SensorData.sensor_id).where(
                    SensorData.timestamp >= stale_threshold
                ).distinct()
            )
            active_ids = {row[0] for row in result} & all_ids

            if self._initialized:
                lost = self._prev_active_sensor_ids - active_ids
                if lost:
                    for name, place in await self._sensor_places(session, lost):
                        events.append(EventLog(
                            level="WARNING",
                            source="health_monitor",
                            message=f"Датчик «{place}» ({name}) не присылает данные {stale_minutes} мин",
                        ))

                recovered = active_ids - self._prev_active_sensor_ids
                if recovered:
                    for name, place in await self._sensor_places(session, recovered):
                        events.append(EventLog(
                            level="INFO",
                            source="health_monitor",
                            message=f"Датчик «{place}» ({name}) снова на связи",
                        ))

            self._prev_active_sensor_ids = active_ids

            # --- Pending (new) sensor checks ---
            result = await session.execute(select(PendingSensor.device_name))
            current_pending = {row[0] for row in result}

            if self._initialized:
                new_pending = current_pending - self._prev_pending_names
                for name in new_pending:
                    events.append(EventLog(
                        level="INFO",
                        source="health_monitor",
                        message=f"Обнаружен новый датчик: '{name}' — привяжите его в настройках",
                    ))

            self._prev_pending_names = current_pending

            # --- Device (actuator) checks via heartbeats from gateway ---
            pending_commands = 0
            unsynced_commands = 0
            device_online = 0

            result = await session.execute(select(func.count()).select_from(Actuator))
            device_total = result.scalar() or 0

            if gateway_health is not None:
                try:
                    hb_timeout = int(kv.get("heartbeat_timeout_seconds", "60"))
                except ValueError:
                    hb_timeout = 60
                pending_commands = gateway_health.get("pending_commands", 0)
                unsynced_commands = gateway_health.get("unsynced_commands", 0)
                heartbeats = gateway_health.get("heartbeats", {}) or {}
                for _device, hb_info in heartbeats.items():
                    try:
                        ts_str = hb_info["timestamp"] if isinstance(hb_info, dict) else hb_info
                        ts = datetime.fromisoformat(ts_str)
                        if (now - ts).total_seconds() < hb_timeout:
                            device_online += 1
                    except (ValueError, TypeError, KeyError):
                        pass

            # --- Alarms: rules over the scheme state, raised/cleared through the tracker ---
            try:
                await self._check_alarms(session, now, services, gateway_health, events)
            except Exception as e:
                logger.exception("health_alarm_check_error", error=str(e))
                await session.rollback()  # keep the session usable for the rest of the poll
                # a crashing rule set must not look like "no alarms"
                broken = Alarm("alarm_check_failed", "ERROR",
                               "Проверка аварий не работает — смотрите журнал сервера. Аварии сейчас не отслеживаются")
                raised, _ = self.alarms.update([broken], now, hold_prefixes=("",))
                events.extend(EventLog(level=a.level, source="alarms", message=a.text) for a in raised)

            # --- Write events ---
            if events:
                for e in events:
                    session.add(e)
                await session.commit()
                for e in events:
                    logger.info("health_event", level=e.level, message=e.message)

            # --- Update cached state ---
            self.state = HealthState(
                backend=True,
                database=services.get("database", False),
                gateway=services.get("gateway", False),
                mqtt=services.get("mqtt", False),
                sensor_total=len(all_ids),
                sensor_active=len(active_ids),
                sensor_pending=len(current_pending),
                device_total=device_total,
                device_online=device_online,
                pending_commands=pending_commands,
                unsynced_commands=unsynced_commands,
                poll_seconds=poll_seconds,
                active_alarms=self.alarms.active_list(),
                updated_at=now,
            )

            self._initialized = True

    async def _sensor_places(self, session: AsyncSession, ids: set[int]) -> list[tuple[str, str]]:
        rows = await session.execute(
            select(Sensor.name, MountPoint.name)
            .join(MountPoint, MountPoint.id == Sensor.mount_point_id)
            .where(Sensor.id.in_(ids)).order_by(Sensor.id)
        )
        return [(name, place) for name, place in rows]

    async def _check_alarms(
        self, session: AsyncSession, now: datetime, services: dict[str, bool],
        gateway_health: dict | None, events: list[EventLog],
    ) -> None:
        async def fetch() -> dict | None:
            return gateway_health

        scheme = SchemeService(session, fetch)
        state = await scheme.build_state(now)
        c = state["controller"]
        snap = Snapshot(
            now=now,
            services={"gateway": services.get("gateway", False), "mqtt": services.get("mqtt", False)},
            online=c["online"], values=state["values"], relays=c["relays"], flags=c["flags"],
            targets=c["targets"], settings=state["settings"],
            rooms=[(r["name"], None if r["stale"] else r["value"]) for r in state["rooms"]],
            hb=scheme.heartbeat_data,
        )
        # while the controller is unreachable its flags are unknown, not cleared
        hold = () if c["online"] else ("flag:", "pza_", "alm_")
        raised, cleared = self.alarms.update(evaluate(snap, set(self.alarms.active)), now, hold, unknown(snap))
        for a in raised:
            events.append(EventLog(level=a.level, source="alarms", message=a.text))
        for a in cleared:
            events.append(EventLog(level="INFO", source="alarms", message=f"Снято: {a.text}"))

    async def _check_services(
        self, session: AsyncSession, gateway_timeout: float = 3.0
    ) -> tuple[dict[str, bool], dict | None]:
        """Returns service flags and the gateway /health payload (None if unreachable)."""
        db_ok = True
        try:
            await session.execute(text("SELECT 1"))
        except Exception:
            db_ok = False

        gw_health: dict | None = None
        try:
            async with httpx.AsyncClient(base_url=self.gateway_url, timeout=gateway_timeout) as client:
                resp = await client.get("/health")
                if resp.status_code == 200:
                    gw_health = resp.json()
        except Exception:
            pass

        return {
            "database": db_ok,
            "gateway": gw_health is not None,
            "mqtt": bool(gw_health and gw_health.get("mqtt_connected", False)),
        }, gw_health
