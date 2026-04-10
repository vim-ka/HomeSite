"""Background health monitor — single source of truth for service/sensor status.

Caches state in memory, writes EventLog on changes. Health endpoints read cached state.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.models.event import EventLog
from app.models.heating import HeatingCircuit
from app.models.sensor import Sensor, SensorData, SensorDataType
from app.models.pending_sensor import PendingSensor
from app.models.config import Actuator, ConfigKV

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_STALE_MINUTES = 5


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
        self._prev_services: dict[str, bool] = {}
        self._prev_active_sensor_ids: set[int] = set()
        self._prev_pending_names: set[str] = set()
        self._pressure_alert_sensor_ids: set[int] = set()
        self._boiler_overheat: bool = False
        self._initialized = False

    async def run(self) -> None:
        """Main loop — polls at configured interval."""
        while True:
            try:
                await self._check()
            except Exception as e:
                logger.error("health_monitor_error", error=str(e))
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

            # --- Service checks ---
            services = await self._check_services(session, gateway_timeout)
            for name, ok in services.items():
                prev = self._prev_services.get(name)
                if prev is not None and prev != ok:
                    if not ok:
                        events.append(EventLog(
                            level="ERROR",
                            source="health_monitor",
                            message=f"Service '{name}' is down",
                        ))
                    else:
                        events.append(EventLog(
                            level="INFO",
                            source="health_monitor",
                            message=f"Service '{name}' is back online",
                        ))
            self._prev_services = services

            # --- Sensor activity checks ---
            now = datetime.now(UTC)
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
                    result = await session.execute(
                        select(Sensor.id, Sensor.name).where(Sensor.id.in_(lost))
                    )
                    for sid, name in result:
                        events.append(EventLog(
                            level="WARNING",
                            source="health_monitor",
                            message=f"Sensor '{name}' (id={sid}) stopped responding",
                        ))

                recovered = active_ids - self._prev_active_sensor_ids
                if recovered:
                    result = await session.execute(
                        select(Sensor.id, Sensor.name).where(Sensor.id.in_(recovered))
                    )
                    for sid, name in result:
                        events.append(EventLog(
                            level="INFO",
                            source="health_monitor",
                            message=f"Sensor '{name}' (id={sid}) is back online",
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
                        message=f"New device discovered: '{name}'",
                    ))

            self._prev_pending_names = current_pending

            # --- Range monitoring (pressure + boiler overtemp) ---
            if self._initialized:
                pressure_min = 1.0
                pressure_max = 1.8
                boiler_max_temp = 85.0
                try:
                    pressure_min = float(kv.get("heating_pressure_min", "1.0"))
                    pressure_max = float(kv.get("heating_pressure_max", "1.8"))
                    boiler_max_temp = float(kv.get("heating_boiler_max_temp", "85.0"))
                except ValueError:
                    pass

                await self._check_pressure_ranges(
                    session, pressure_min, pressure_max, stale_threshold, events
                )
                await self._check_boiler_overtemp(
                    session, boiler_max_temp, stale_threshold, events
                )

            # --- Write events ---
            if events:
                for e in events:
                    session.add(e)
                await session.commit()
                for e in events:
                    logger.info("health_event", level=e.level, message=e.message)

            # --- Device (actuator) checks via heartbeats from gateway ---
            device_total = 0
            device_online = 0
            pending_commands = 0
            unsynced_commands = 0

            result = await session.execute(select(func.count()).select_from(Actuator))
            device_total = result.scalar() or 0

            # Get heartbeat data from gateway /health response
            if services.get("gateway"):
                try:
                    hb_timeout = int(kv.get("heartbeat_timeout_seconds", "60"))
                    async with httpx.AsyncClient(base_url=self.gateway_url, timeout=gateway_timeout) as client:
                        resp = await client.get("/health")
                        if resp.status_code == 200:
                            data = resp.json()
                            pending_commands = data.get("pending_commands", 0)
                            unsynced_commands = data.get("unsynced_commands", 0)
                            heartbeats = data.get("heartbeats", {})
                            for _device, hb_info in heartbeats.items():
                                try:
                                    ts_str = hb_info["timestamp"] if isinstance(hb_info, dict) else hb_info
                                    ts = datetime.fromisoformat(ts_str)
                                    if (now - ts).total_seconds() < hb_timeout:
                                        device_online += 1
                                except (ValueError, TypeError, KeyError):
                                    pass
                except Exception:
                    pass

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
                updated_at=now,
            )

            self._initialized = True

    async def _check_pressure_ranges(
        self,
        session: AsyncSession,
        p_min: float,
        p_max: float,
        stale_threshold: datetime,
        events: list[EventLog],
    ) -> None:
        """Check all pressure sensors against [p_min, p_max]; emit ERROR/INFO on state changes."""
        result = await session.execute(
            select(SensorData.sensor_id, SensorData.value, Sensor.name)
            .join(Sensor, SensorData.sensor_id == Sensor.id)
            .join(SensorDataType, SensorData.datatype_id == SensorDataType.id)
            .where(SensorDataType.code == "prs")
            .where(SensorData.timestamp >= stale_threshold)
        )
        rows = result.all()

        current_alerts: set[int] = set()
        for sensor_id, value, name in rows:
            if value < p_min or value > p_max:
                current_alerts.add(sensor_id)
                if sensor_id not in self._pressure_alert_sensor_ids:
                    direction = "низкое" if value < p_min else "высокое"
                    events.append(EventLog(
                        level="ERROR",
                        source="health_monitor",
                        message=(
                            f"Давление вне нормы: {name} = {value:.2f} бар"
                            f" ({direction}, норма {p_min}–{p_max} бар)"
                        ),
                    ))
            elif sensor_id in self._pressure_alert_sensor_ids:
                events.append(EventLog(
                    level="INFO",
                    source="health_monitor",
                    message=f"Давление восстановилось: {name} = {value:.2f} бар",
                ))

        self._pressure_alert_sensor_ids = current_alerts

    async def _check_boiler_overtemp(
        self,
        session: AsyncSession,
        max_temp: float,
        stale_threshold: datetime,
        events: list[EventLog],
    ) -> None:
        """Check boiler supply temperature against max_temp; emit ERROR/INFO on state change."""
        # Find boiler supply mount point via HeatingCircuit
        mp_result = await session.execute(
            select(HeatingCircuit.supply_mount_point_id)
            .where(HeatingCircuit.config_prefix == "heating_boiler")
        )
        supply_mp_id = mp_result.scalar_one_or_none()
        if supply_mp_id is None:
            return

        # Find temperature reading for any sensor at that mount point
        temp_dt_result = await session.execute(
            select(SensorDataType.id).where(SensorDataType.code == "tmp")
        )
        tmp_dt_id = temp_dt_result.scalar_one_or_none()
        if tmp_dt_id is None:
            return

        result = await session.execute(
            select(SensorData.value, Sensor.name)
            .join(Sensor, SensorData.sensor_id == Sensor.id)
            .where(Sensor.mount_point_id == supply_mp_id)
            .where(SensorData.datatype_id == tmp_dt_id)
            .where(SensorData.timestamp >= stale_threshold)
        )
        row = result.first()
        if row is None:
            return

        temp, name = row
        if temp > max_temp:
            if not self._boiler_overheat:
                self._boiler_overheat = True
                events.append(EventLog(
                    level="ERROR",
                    source="health_monitor",
                    message=f"Перегрев котла: {name} = {temp:.1f}°C (макс. {max_temp:.0f}°C)",
                ))
        elif self._boiler_overheat:
            self._boiler_overheat = False
            events.append(EventLog(
                level="INFO",
                source="health_monitor",
                message=f"Температура котла в норме: {name} = {temp:.1f}°C",
            ))

    async def _check_services(self, session: AsyncSession, gateway_timeout: float = 3.0) -> dict[str, bool]:
        db_ok = True
        try:
            await session.execute(text("SELECT 1"))
        except Exception:
            db_ok = False

        gw_ok = False
        mqtt_ok = False
        try:
            async with httpx.AsyncClient(base_url=self.gateway_url, timeout=gateway_timeout) as client:
                resp = await client.get("/health")
                if resp.status_code == 200:
                    gw_ok = True
                    mqtt_ok = resp.json().get("mqtt_connected", False)
        except Exception:
            pass

        return {
            "database": db_ok,
            "gateway": gw_ok,
            "mqtt": mqtt_ok,
        }
