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
from app.services.advice_rules import AdviceHistory, evaluate_advice
from app.services.alarm_rules import Alarm, AlarmTracker, Snapshot, evaluate, unknown
from app.services.gateway_client import GatewayClient
from app.services.internet_probe import default_router, reachable, target
from app.services.scheme_service import CONTROLLER_DEVICE, SchemeService
from app.services.sms_notifier import SmsNotifier
from app.services.sms_queue import (
    CFG_KEYS,
    DEFAULT_INTERNET_DOWN_MINUTES,
    cfg_from_kv,
    phone_status,
    poll_seconds,
)

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_STALE_MINUTES = 5

DEFAULT_INTERNET_HOSTS = "77.88.8.8:53,1.1.1.1:53,ya.ru:443,8.8.8.8:53"
PROBE_EVERY_S = 60
PROBE_TIMEOUT_S = 3.0
SMS_KEYS = (*CFG_KEYS, "internet_check_hosts", "internet_router_host")

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

    # Efficiency advice (supply − return differences, boiler return, tank coil) — not alarms
    active_advice: list[dict] = field(default_factory=list)

    # The targets the controller reports (boiler auto / radiators / floor, PZA with its smoothed street
    # temperature, night setback, room correction) — None while it is offline
    controller_targets: dict | None = None

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
        self._targets: dict | None = None
        self.advice_history = AdviceHistory()
        self.advice = AlarmTracker()

        # Previous state for change detection
        self._prev_active_sensor_ids: set[int] = set()
        self._prev_pending_names: set[str] = set()
        self._initialized = False
        self.alarms = AlarmTracker()
        self._now = lambda: datetime.now(UTC)  # replaceable clock (tests)
        self.sms = SmsNotifier(started_at=self._now())
        self._net: tuple[datetime, dict] | None = None   # last probe: (when, {"internet", "router"})
        self._sms_cleanup_at: datetime | None = None

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
            self._targets = None
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
                controller_targets=self._targets,
                active_advice=self.advice.active_list(),
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
        if gateway_health is not None:
            await self._forward_indoor(state)
        c = state["controller"]
        self._targets = dict(c["targets"]) if c["online"] else None
        kv = await self._kv(session, SMS_KEYS)
        net = await self._probe_net(kv, now)
        sms_state: dict = {}
        try:
            async with self.session_factory() as s:
                st = await phone_status(s, now, await poll_seconds(s))
            sms_state = {"silent": st["silent"], "failed": st["failed"]}
        except Exception as e:
            logger.exception("sms_status_error", error=str(e))
        snap = Snapshot(
            now=now,
            services={"gateway": services.get("gateway", False), "mqtt": services.get("mqtt", False)},
            online=c["online"], values=state["values"], relays=c["relays"], flags=c["flags"],
            targets=c["targets"], settings=state["settings"],
            rooms=[(r["name"], None if r["stale"] else r["value"]) for r in state["rooms"]],
            hb=scheme.heartbeat_data, net=net, sms=sms_state,
        )
        # while the controller is unreachable its flags are unknown, not cleared
        hold = () if c["online"] else ("flag:", "pza_", "alm_")
        raised, cleared = self.alarms.update(evaluate(snap, set(self.alarms.active)), now, hold, unknown(snap))
        for a in raised:
            events.append(EventLog(level=a.level, source="alarms", message=a.text))
        for a in cleared:
            events.append(EventLog(level="INFO", source="alarms", message=f"Снято: {a.text}"))
        await self._notify_sms(kv, now)

        # efficiency advice over the last 30 min of steady operation (a rule that can't judge holds its advice)
        self.advice_history.add(snap)
        advice, held = evaluate_advice(self.advice_history, now, set(self.advice.active))
        raised, cleared = self.advice.update(advice, now, hold_codes=held)
        for a in raised:
            events.append(EventLog(level="INFO", source="advice", message=f"Совет: {a.text}"))
        for a in cleared:
            events.append(EventLog(level="INFO", source="advice", message=f"Совет снят: {a.text.split(' — ')[0]}"))

    @staticmethod
    async def _kv(session: AsyncSession, keys) -> dict[str, str]:
        rows = await session.execute(select(ConfigKV.key, ConfigKV.value).where(ConfigKV.key.in_(keys)))
        return {k: v for k, v in rows}

    async def _probe_net(self, kv: dict[str, str], now: datetime) -> dict:
        """Internet and router reachability (at most once a minute); {} when the check is switched off."""
        raw = kv.get("internet_check_hosts", DEFAULT_INTERNET_HOSTS).split(",")
        hosts = [t for h in raw if (t := target(h, 443))]
        if not hosts:   # switched off (or nothing parseable — never read as «no internet»)
            self._net = None
            return {}
        try:
            minutes = int(kv.get("internet_down_minutes", DEFAULT_INTERNET_DOWN_MINUTES))
        except ValueError:
            minutes = DEFAULT_INTERNET_DOWN_MINUTES
        if self._net is None or (now - self._net[0]).total_seconds() >= PROBE_EVERY_S:
            router = (target(kv["internet_router_host"], 80) if kv.get("internet_router_host", "").strip()
                      else default_router())
            try:
                internet, router_ok = await asyncio.gather(
                    reachable(hosts, PROBE_TIMEOUT_S),
                    reachable([router], PROBE_TIMEOUT_S) if router else asyncio.sleep(0, result=None),
                )
            except Exception as e:
                logger.exception("internet_probe_error", error=str(e))
                return {"internet": None, "router": None, "down_s": minutes * 60}   # unknown: alarms held
            self._net = (now, {"internet": internet, "router": router_ok})
        return {**self._net[1], "down_s": minutes * 60}

    async def _notify_sms(self, kv: dict[str, str], now: datetime) -> None:
        """Feed the active alarms to the SMS notifier; its own session and try — it never breaks the alarms."""
        try:
            cfg = cfg_from_kv(kv)
            async with self.session_factory() as s:
                await self.sms.apply(s, list(self.alarms.active.values()), now, cfg)
            if self._sms_cleanup_at is None or now - self._sms_cleanup_at >= timedelta(days=1):
                self._sms_cleanup_at = now
                async with self.session_factory() as s:
                    await self.sms.cleanup(s, now)
        except Exception as e:
            logger.exception("sms_notify_error", error=str(e))

    async def _forward_indoor(self, state: dict) -> None:
        """The house average → the controller, for the room correction of its weather curves.

        Only while the correction is on; a stale average is not sent — the controller then drops
        the correction by itself after its TTL.
        """
        try:
            factor = float(state["settings"].get("heating_room_factor", "0"))
        except ValueError:
            factor = 0.0
        indoor = state["values"].get("indoor_avg") or {}
        if factor <= 0 or indoor.get("stale", True) or indoor.get("value") is None:
            return
        await self._send_telemetry({"indoor_temp": f"{indoor['value']:.1f}"})

    async def _send_telemetry(self, params: dict[str, str]) -> None:
        await GatewayClient(base_url=self.gateway_url, timeout=3.0).send_telemetry(CONTROLLER_DEVICE, params)

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
