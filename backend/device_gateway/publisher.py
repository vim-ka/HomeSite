"""MQTT command publisher — sends grouped commands to devices."""

import json

import aiomqtt

from device_gateway.config import GatewaySettings

import structlog

logger = structlog.get_logger(__name__)


class CommandPublisher:
    """Publishes grouped commands to MQTT topics.

    Topic format: home/devices/{device_id}/command
    Payload: JSON {"key1": "value1", "key2": "value2", ...}
    QoS: 1 (at least once), retain: True
    """

    def __init__(self, settings: GatewaySettings):
        self.settings = settings
        self._client: aiomqtt.Client | None = None

    async def connect(self) -> None:
        """Create a persistent MQTT client for publishing."""
        connect_kwargs: dict = {
            "hostname": self.settings.mqtt_broker_host,
            "port": self.settings.mqtt_broker_port,
        }
        if self.settings.mqtt_username:
            connect_kwargs["username"] = self.settings.mqtt_username
            connect_kwargs["password"] = self.settings.mqtt_password

        self._client = aiomqtt.Client(**connect_kwargs)
        await self._client.__aenter__()
        logger.info("publisher_connected")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None
            logger.info("publisher_disconnected")

    async def publish_grouped(self, device_id: str, params: dict[str, str]) -> str | None:
        """Publish grouped commands as a single MQTT message.

        Topic: {prefix}{device_id}/command
        Payload: {"heating_boiler_temp": "60", "heating_boiler_power": "1", ...}
        Duplicate keys are already deduplicated by the dispatcher.
        """
        if self._client is None:
            logger.warning("publisher_not_connected")
            return None

        topic = f"{self.settings.mqtt_topic_prefix}{device_id}/cmd"

        try:
            payload = json.dumps(params)
            await self._client.publish(topic, payload, qos=1, retain=True)
            logger.info("command_published", topic=topic, params=list(params.keys()))
            return topic
        except Exception as e:
            logger.error("publish_failed", topic=topic, error=str(e))
            return None
