"""MQTT message handler — subscribes to sensor topics, persists data, notifies backend."""

import json
from datetime import UTC, datetime

import aiomqtt
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from device_gateway.config import (
    MQTT_SUBSCRIBE_TOPIC,
    MQTT_TOPIC_PREFIX,
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

    def __init__(self, settings: GatewaySettings, session_factory: async_sessionmaker[AsyncSession]):
        self.settings = settings
        self.session_factory = session_factory
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def run(self) -> None:
        """Main loop — connects to broker, processes messages, auto-reconnects on failure."""
        import asyncio

        while True:
            try:
                await self._connect_and_listen()
            except aiomqtt.MqttError as e:
                self._connected = False
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
            self._connected = True
            logger.info(
                "mqtt_connected",
                host=self.settings.mqtt_broker_host,
                port=self.settings.mqtt_broker_port,
            )
            await client.subscribe(MQTT_SUBSCRIBE_TOPIC)

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
        if not topic_str.startswith(MQTT_TOPIC_PREFIX):
            return

        # Topic format: home/devices/{device_name}
        # The device_name is extracted from after the prefix
        remainder = topic_str[len(MQTT_TOPIC_PREFIX):]
        parts = remainder.split("/")
        device_name = parts[0]

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
