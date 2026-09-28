"""MQTT command publisher — sends grouped commands to devices."""

import json
from typing import Protocol

import aiomqtt

import structlog

logger = structlog.get_logger(__name__)


class PublishError(Exception):
    """Command could not be handed to the broker (not connected / publish failed)."""


class MqttConnectionSource(Protocol):
    """Anything that owns the live MQTT connection (MQTTHandler)."""

    @property
    def active_client(self) -> aiomqtt.Client | None: ...

    @property
    def topic_prefix(self) -> str: ...


class CommandPublisher:
    """Publishes grouped commands to MQTT topics.

    Topic format: {prefix}{device_id}/cmd
    Payload: JSON {"key1": "value1", "key2": "value2", ...}
    QoS: 1 (at least once), retain: False

    Commands are never retained: the broker would replay the last message on
    every device reconnect, so a one-shot command like ``restart`` would put the
    device into a boot loop. Desired state is instead re-sent from config_kv by
    the gateway when a device (re)boots — see ``device_gateway.sync``.

    Publishing goes through the subscriber's connection, which already
    reconnects on its own, so a broker restart does not leave a dead publisher.
    """

    def __init__(self, source: MqttConnectionSource | None = None):
        self._source = source

    def attach(self, source: MqttConnectionSource) -> None:
        self._source = source

    @property
    def is_connected(self) -> bool:
        return self._source is not None and self._source.active_client is not None

    async def publish_grouped(self, device_id: str, params: dict[str, str]) -> str:
        """Publish grouped commands as a single MQTT message.

        Returns the topic on success, raises PublishError otherwise.
        Duplicate keys are already deduplicated by the dispatcher.
        """
        client = self._source.active_client if self._source else None
        if client is None:
            logger.warning("publisher_not_connected", device_id=device_id)
            raise PublishError("MQTT not connected")

        topic = f"{self._source.topic_prefix}{device_id}/cmd"
        try:
            await client.publish(topic, json.dumps(params), qos=1, retain=False)
        except aiomqtt.MqttError as e:
            logger.error("publish_failed", topic=topic, error=str(e))
            raise PublishError(str(e)) from e

        logger.info("command_published", topic=topic, params=list(params.keys()))
        return topic
