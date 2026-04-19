"""MQTT message handler — subscribes to sensor topics, persists data, notifies backend."""

import asyncio
import json
from datetime import UTC, datetime

import aiomqtt
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from device_gateway.config import (
    PARAMETER_MAP,
    GatewaySettings,
)

import structlog

logger = structlog.get_logger(__name__)


class MQTTHandler:
    """Async MQTT handler with auto-reconnect.

    Responsibilities:
    - Subscribe to home/devices/#
    - Parse incoming messages
    - Upsert SensorData + append SensorDataHistory
    - Notify backend of updates via HTTP callback
    """

    def __init__(self, settings: GatewaySettings, session_factory: async_sessionmaker[AsyncSession], dispatcher=None):
        self.settings = settings
        self.session_factory = session_factory
        self._connected = False
        self._reconnect_requested = False
        self._active_client: aiomqtt.Client | None = None
        self._dispatcher = dispatcher
        # Heartbeat tracking: device_name → {timestamp, data}
        self.heartbeats: dict[str, dict] = {}
        # Scan results: device_name → sensor list (set by /sensors topic)
        self._scan_results: dict[str, list[dict]] = {}
        self._scan_events: dict[str, asyncio.Event] = {}

    @property
    def is_connected(self) -> bool:
        return self._connected

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
        import asyncio

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
                if isinstance(ack_data, dict) and self._dispatcher:
                    await self._dispatcher.handle_ack(device_name, ack_data)
            except Exception:
                pass
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
            await self._notify_rf_debug(device_name, payload_raw)
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
            self.heartbeats[device_name] = {
                "timestamp": datetime.now(UTC),
                "data": hb_data,
            }
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
            await self._notify_backend(device_name, device_id, data)

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
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(
                    f"{self.settings.backend_url}/internal/sensor-update",
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
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(
                    f"{self.settings.backend_url}/internal/rf-debug",
                    json={"device_name": device_name, "payload": payload},
                    headers={"X-Internal-Secret": self.settings.internal_api_secret},
                )
        except httpx.ConnectError:
            pass
        except Exception as e:
            logger.warning("backend_notify_rf_debug_error", error=str(e))

    async def wait_for_scan(self, device_name: str, timeout: float = 10.0) -> list[dict] | None:
        """Wait for scan result from device. Returns sensor list or None on timeout."""
        event = asyncio.Event()
        self._scan_events[device_name] = event
        self._scan_results.pop(device_name, None)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._scan_results.get(device_name)
        except asyncio.TimeoutError:
            return None
        finally:
            self._scan_events.pop(device_name, None)
