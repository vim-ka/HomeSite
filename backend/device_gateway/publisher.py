"""MQTT command publisher — sends commands to devices."""

import json

import aiomqtt

from device_gateway.config import MQTT_TOPIC_PREFIX, GatewaySettings

import structlog

logger = structlog.get_logger(__name__)


class CommandPublisher:
    """Publishes commands to MQTT topics.

    Topic format: home/devices/{device_id}/command/{parameter}
    Payload: JSON {"value": <value>}
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

    async def publish(self, device_id: str, parameter: str, value: str) -> str | None:
        """Publish a command to a device.

        Returns the topic string on success, None on failure.
        """
        if self._client is None:
            logger.warning("publisher_not_connected")
            return None

        topic = f"{MQTT_TOPIC_PREFIX}{device_id}/command/{parameter}"
        payload = json.dumps({"value": value})

        try:
            await self._client.publish(topic, payload, qos=1, retain=True)
            logger.info("command_published", topic=topic, value=value)
            return topic
        except Exception as e:
            logger.error("publish_failed", topic=topic, error=str(e))
            return None
