"""MQTT message handler — subscribes to sensor topics, persists data, notifies backend."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import aiomqtt
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from device_gateway.config import (
    PARAMETER_MAP,
    GatewaySettings,
)

import structlog

# ESP32 reset reasons (firmware heartbeat "reset_reason") in words for the event log
RESET_REASONS = {
    "poweron": "включение питания", "software": "программный перезапуск", "panic": "сбой программы",
    "watchdog": "сторожевой таймер", "brownout": "просадка питания", "external": "кнопка сброса",
}
REBOOT_LOOP_WINDOW = timedelta(minutes=30)
REBOOT_LOOP_COUNT = 4

logger = structlog.get_logger(__name__)

# Backend notifications are fire-and-forget; beyond this many in flight new ones are dropped
MAX_PENDING_NOTIFICATIONS = 100


class MQTTHandler:
    """Async MQTT handler with auto-reconnect.

    Responsibilities:
    - Subscribe to home/devices/#
    - Parse incoming messages
    - Upsert SensorData + append SensorDataHistory
    - Notify backend of updates via HTTP callback
    """

    def __init__(
        self,
        settings: GatewaySettings,
        session_factory: async_sessionmaker[AsyncSession],
        dispatcher=None,
        on_device_boot: Callable[[str], Awaitable[object]] | None = None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self._connected = False
        self._reconnect_requested = False
        self._active_client: aiomqtt.Client | None = None
        self._dispatcher = dispatcher
        # Called when a device reboots or is seen for the first time since gateway start
        self._on_device_boot = on_device_boot
        # Heartbeat tracking: device_name → {timestamp, data}
        self.heartbeats: dict[str, dict] = {}
        # Last reported uptime per device — a decrease means the device rebooted
        self._last_uptime: dict[str, float | None] = {}
        self._reboots: dict[str, list[datetime]] = {}
        # Devices reported as lost by check_heartbeats — their return is logged
        self._lost: set[str] = set()
        # Scan results: device_name → sensor list (set by /sensors topic)
        self._scan_results: dict[str, list[dict]] = {}
        self._scan_events: dict[str, asyncio.Event] = {}
        self._http: httpx.AsyncClient | None = None
        self._background: set[asyncio.Task] = set()
        # PZA outdoor forwarding: (sensor name, target mqtt device) or None.
        # Lets a controller without its own street sensor follow the weather curve.
        self.outdoor_forward: tuple[str, str] | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def active_client(self) -> aiomqtt.Client | None:
        """Live MQTT connection, shared with CommandPublisher."""
        return self._active_client if self._connected else None

    @property
    def topic_prefix(self) -> str:
        return self.settings.mqtt_topic_prefix

    def reload_settings(self, new_settings: GatewaySettings) -> None:
        """Update MQTT settings and trigger reconnect."""
        self.settings = new_settings
        self._reconnect_requested = True
        # Force disconnect to trigger reconnect loop with new settings
        if self._active_client is not None:
            self._active_client._disconnected.set_result(None) if not self._active_client._disconnected.done() else None
        logger.info(
            "mqtt_reload_requested",
            host=new_settings.mqtt_broker_host,
            port=new_settings.mqtt_broker_port,
        )

    async def run(self) -> None:
        """Main loop — connects to broker, processes messages, auto-reconnects on failure."""
        while True:
            try:
                self._reconnect_requested = False
                await self._connect_and_listen()
            except aiomqtt.MqttError as e:
                self._connected = False
                if self._reconnect_requested:
                    logger.info("mqtt_reconnecting_with_new_settings")
                else:
                    logger.warning("mqtt_disconnected", error=str(e))
                    await asyncio.sleep(self.settings.mqtt_reconnect_interval)
            except Exception as e:
                self._connected = False
                logger.error("mqtt_unexpected_error", error=str(e))
                await asyncio.sleep(self.settings.mqtt_reconnect_interval)

    async def _connect_and_listen(self) -> None:
        """Connect and process messages until disconnected."""
        connect_kwargs: dict = {
            "hostname": self.settings.mqtt_broker_host,
            "port": self.settings.mqtt_broker_port,
        }
        if self.settings.mqtt_username:
            connect_kwargs["username"] = self.settings.mqtt_username
            connect_kwargs["password"] = self.settings.mqtt_password

        async with aiomqtt.Client(**connect_kwargs) as client:
            self._active_client = client
            self._connected = True
            try:
                logger.info(
                    "mqtt_connected",
                    host=self.settings.mqtt_broker_host,
                    port=self.settings.mqtt_broker_port,
                )
                await client.subscribe(self.settings.mqtt_topic_prefix + "#")

                async for message in client.messages:
                    try:
                        await self._handle_message(message)
                    except Exception as e:
                        logger.error(
                            "mqtt_message_error",
                            topic=str(message.topic),
                            error=str(e),
                        )
            finally:
                self._connected = False
                self._active_client = None

    async def _handle_message(self, message: aiomqtt.Message) -> None:
        """Parse topic, extract device name, upsert sensor values."""
        topic_str = str(message.topic)
        prefix = self.settings.mqtt_topic_prefix
        if not topic_str.startswith(prefix):
            return

        # Topic format: {prefix}{device_name}[/subtopic]
        remainder = topic_str[len(prefix):]
        parts = remainder.split("/")
        device_name = parts[0]
        subtopic = parts[1] if len(parts) > 1 else None

        # Ignore our own outgoing commands
        if subtopic in ("command", "cmd"):
            return

        # Handle ack: home/devices/{name}/ack → confirm commands received
        if subtopic == "ack":
            payload_raw = message.payload
            if isinstance(payload_raw, (bytes, bytearray)):
                payload_raw = payload_raw.decode()
            try:
                ack_data = json.loads(payload_raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning("mqtt_invalid_ack", device=device_name)
                return
            if isinstance(ack_data, dict) and self._dispatcher:
                rejected = await self._dispatcher.handle_ack(device_name, ack_data)
                if rejected:
                    await self._log_event(
                        "ERROR",
                        f"Устройство «{device_name}» отклонило настройки: "
                        + ", ".join(f"{k} ({r})" for k, r in rejected),
                    )
            return

        # Handle scan result: home/devices/{name}/sensors → OneWire scan response
        if subtopic == "sensors":
            payload_raw = message.payload
            if isinstance(payload_raw, (bytes, bytearray)):
                payload_raw = payload_raw.decode()
            try:
                sensors_data = json.loads(payload_raw)
                if isinstance(sensors_data, list):
                    self._scan_results[device_name] = sensors_data
                    event = self._scan_events.get(device_name)
                    if event:
                        event.set()
                    logger.info("scan_result_received", device=device_name, count=len(sensors_data))
            except Exception:
                pass
            return

        # Handle raw RF debug: home/devices/{name}/rf_debug → forward to backend WS
        if subtopic == "rf_debug":
            payload_raw = message.payload
            if isinstance(payload_raw, (bytes, bytearray)):
                payload_raw = payload_raw.decode(errors="replace")
            self._spawn(self._notify_rf_debug(device_name, payload_raw))
            return

        # Handle heartbeat: home/devices/{name}/heartbeat → track device alive + payload
        if subtopic == "heartbeat":
            hb_payload = message.payload
            if isinstance(hb_payload, (bytes, bytearray)):
                hb_payload = hb_payload.decode()
            hb_data = {}
            try:
                hb_data = json.loads(hb_payload)
            except (json.JSONDecodeError, TypeError):
                pass
            if not isinstance(hb_data, dict):
                hb_data = {}
            self.heartbeats[device_name] = {
                "timestamp": datetime.now(UTC),
                "data": hb_data,
            }
            if device_name in self._lost:
                self._lost.discard(device_name)
                self._spawn(self._log_event("INFO", f"Устройство «{device_name}» снова на связи"))
            self._track_boot(device_name, hb_data.get("uptime"), hb_data.get("reset_reason"))
            return

        payload = message.payload
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode()
        data = json.loads(payload)

        if not isinstance(data, dict):
            logger.warning("mqtt_invalid_payload", topic=topic_str, payload=payload)
            return

        async with self.session_factory() as session:
            device_id = await self._get_device_id(session, device_name)
            if device_id is None:
                await self._register_pending(session, device_name, data)
                return

            updated_params = []
            for param, val in data.items():
                datatype_id = PARAMETER_MAP.get(param)
                if datatype_id is not None:
                    await self._upsert_sensor_value(
                        session, device_id, datatype_id, float(val)
                    )
                    updated_params.append(param)

            await session.commit()

            logger.info(
                "mqtt_data_saved",
                device=device_name,
                sensor_id=device_id,
                params=updated_params,
            )

        # Notify backend about the update
        if updated_params:
            self._spawn(self._notify_backend(device_name, device_id, data))
            self._forward_outdoor(device_name, data)

    def _forward_outdoor(self, device_name: str, data: dict) -> None:
        if self.outdoor_forward is None or "tmp" not in data:
            return
        sensor, target = self.outdoor_forward
        client = self.active_client
        if device_name != sensor or client is None:
            return
        self._spawn(self.publish_telemetry(target, {"outdoor_temp": str(data["tmp"])}))

    async def publish_telemetry(self, device: str, params: dict[str, str]) -> bool:
        """Telemetry for a device (outdoor / indoor temperature), not a setting: no dispatcher, no ack,
        not retained — a stale value must never be replayed to a rebooting controller."""
        client = self.active_client
        if client is None:
            return False
        await client.publish(f"{self.topic_prefix}{device}/cmd", json.dumps(params), qos=0, retain=False)
        return True

    def check_heartbeats(self, now: datetime, timeout_s: int, quiet: set[str]) -> list[dict]:
        """Drop devices silent for longer than the timeout; events for those not in `quiet`.

        `quiet` are the command devices (the boiler controller): the backend's "no link" alarm
        covers them with a delay and the frost context, so a second line here would only repeat it.
        """
        events = []
        for name, record in list(self.heartbeats.items()):
            if now - record["timestamp"] > timedelta(seconds=timeout_s):
                del self.heartbeats[name]
                logger.warning("heartbeat_lost", device=name)
                if name not in quiet:
                    self._lost.add(name)
                    events.append({"level": "WARNING", "source": "gateway_watchdog",
                                   "message": f"Устройство «{name}» не на связи — нет сигнала {timeout_s} с"})
        return events

    def _track_reboot(self, device_name: str, reason: object) -> None:
        now = datetime.now(UTC)
        why = RESET_REASONS.get(str(reason), str(reason)) if reason else None
        self._spawn(self._log_event(
            "INFO", f"Устройство «{device_name}» перезагрузилось" + (f" (причина: {why})" if why else "")))
        recent = [t for t in self._reboots.get(device_name, []) if now - t < REBOOT_LOOP_WINDOW] + [now]
        self._reboots[device_name] = recent
        if len(recent) == REBOOT_LOOP_COUNT:
            minutes = int(REBOOT_LOOP_WINDOW.total_seconds() // 60)
            self._spawn(self._log_event(
                "ERROR",
                f"Устройство «{device_name}» постоянно перезагружается: {len(recent)} раза за {minutes} мин"
                + (f" (последняя причина: {why})" if why else ""),
            ))

    def _track_boot(self, device_name: str, uptime: object, reason: object = None) -> None:
        """Fire on_device_boot when a device reboots or is first seen since gateway start."""
        try:
            uptime_s = float(uptime)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            uptime_s = None
        first_seen = device_name not in self._last_uptime
        previous = self._last_uptime.get(device_name)
        self._last_uptime[device_name] = uptime_s if uptime_s is not None else (previous or 0.0)
        rebooted = previous is not None and uptime_s is not None and uptime_s < previous
        if rebooted:
            self._track_reboot(device_name, reason)
        if (first_seen or rebooted) and self._on_device_boot is not None:
            logger.info("device_boot_detected", device=device_name, rebooted=rebooted)
            self._spawn(self._on_device_boot(device_name))

    def _spawn(self, coro: Awaitable[object]) -> None:
        """Run a coroutine in the background without blocking the MQTT loop."""
        if len(self._background) >= MAX_PENDING_NOTIFICATIONS:
            logger.warning("background_queue_full_dropping")
            coro.close()  # type: ignore[attr-defined]
            return
        task = asyncio.ensure_future(coro)
        self._background.add(task)
        task.add_done_callback(self._background_done)

    def _background_done(self, task: asyncio.Task) -> None:
        self._background.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("background_task_error", error=str(task.exception()))

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=3.0)
        return self._http

    async def close(self) -> None:
        for task in list(self._background):
            task.cancel()
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _log_event(self, level: str, message: str) -> None:
        from app.models.event import EventLog

        try:
            async with self.session_factory() as session:
                session.add(EventLog(level=level, source="gateway", message=message))
                await session.commit()
        except Exception as e:
            logger.error("event_log_write_error", error=str(e))

    async def _register_pending(self, session: AsyncSession, device_name: str, data: dict) -> None:
        """Record an unknown device in pending_sensors for user review."""
        from app.models.pending_sensor import PendingSensor

        now = datetime.now(UTC)
        payload_str = json.dumps(data)
        first_value = None
        for v in data.values():
            try:
                first_value = float(v)
                break
            except (ValueError, TypeError):
                pass

        existing = await session.execute(
            select(PendingSensor).where(PendingSensor.device_name == device_name)
        )
        pending = existing.scalar_one_or_none()

        if pending:
            pending.last_payload = payload_str
            pending.last_value = first_value
            pending.last_seen = now
            pending.message_count += 1
        else:
            session.add(PendingSensor(
                device_name=device_name,
                last_payload=payload_str,
                last_value=first_value,
                first_seen=now,
                last_seen=now,
                message_count=1,
            ))
            logger.info("pending_sensor_discovered", device_name=device_name, payload=data)

        await session.commit()

    async def _get_device_id(self, session: AsyncSession, name: str) -> int | None:
        """Look up sensor ID by name."""
        # Import here to avoid circular dependency at module level
        from app.models.sensor import Sensor

        stmt = select(Sensor.id).where(Sensor.name == name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_sensor_value(
        self,
        session: AsyncSession,
        sensor_id: int,
        datatype_id: int,
        value: float,
    ) -> None:
        """Update current value (SensorData) and append history (SensorDataHistory)."""
        from app.models.sensor import SensorData, SensorDataHistory

        now = datetime.now(UTC)

        # Upsert current value
        stmt = select(SensorData).where(
            SensorData.sensor_id == sensor_id,
            SensorData.datatype_id == datatype_id,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = value
            existing.timestamp = now
        else:
            session.add(
                SensorData(
                    sensor_id=sensor_id,
                    datatype_id=datatype_id,
                    value=value,
                    timestamp=now,
                )
            )

        # Append history
        session.add(
            SensorDataHistory(
                sensor_id=sensor_id,
                datatype_id=datatype_id,
                value=value,
                timestamp=now,
            )
        )

    async def _notify_backend(
        self, device_name: str, sensor_id: int, data: dict
    ) -> None:
        """Notify the backend about a sensor update via HTTP callback."""
        try:
            await self._client().post(
                f"{self.settings.backend_url}/api/v1/internal/sensor-update",
                json={
                    "device_name": device_name,
                    "sensor_id": sensor_id,
                    "data": data,
                },
                headers={"X-Internal-Secret": self.settings.internal_api_secret},
            )
        except httpx.ConnectError:
            pass  # Backend may not be running — this is non-critical
        except Exception as e:
            logger.warning("backend_notify_error", error=str(e))

    async def _notify_rf_debug(self, device_name: str, payload: str) -> None:
        """Forward raw RF frame from rtl_433_ESP to backend for WS fan-out."""
        try:
            await self._client().post(
                f"{self.settings.backend_url}/api/v1/internal/rf-debug",
                json={"device_name": device_name, "payload": payload},
                headers={"X-Internal-Secret": self.settings.internal_api_secret},
            )
        except httpx.ConnectError:
            pass
        except Exception as e:
            logger.warning("backend_notify_rf_debug_error", error=str(e))

    def begin_scan(self, device_name: str) -> None:
        """Register interest in a scan result. Call BEFORE publishing scan_sensors,
        otherwise a fast reply can arrive before anyone is waiting and get lost."""
        self._scan_results.pop(device_name, None)
        self._scan_events[device_name] = asyncio.Event()

    async def wait_for_scan(self, device_name: str, timeout: float = 10.0) -> list[dict] | None:
        """Wait for scan result from device. Returns sensor list or None on timeout."""
        event = self._scan_events.get(device_name)
        if event is None:
            self.begin_scan(device_name)
            event = self._scan_events[device_name]
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._scan_results.get(device_name)
        except asyncio.TimeoutError:
            return None
        finally:
            self._scan_events.pop(device_name, None)
