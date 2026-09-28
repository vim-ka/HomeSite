"""Tests for CommandPublisher — no retain, errors are raised, follows handler connection."""

import json

import aiomqtt
import pytest

from device_gateway.publisher import CommandPublisher, PublishError


class FakeClient:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.published: list[tuple[str, str, int, bool]] = []

    async def publish(self, topic, payload, qos=0, retain=False):
        if self.fail:
            raise aiomqtt.MqttError("Disconnected")
        self.published.append((topic, payload, qos, retain))


class FakeSource:
    def __init__(self, client):
        self.active_client = client
        self.topic_prefix = "home/devices/"


@pytest.mark.asyncio
async def test_publish_is_not_retained():
    """Retained commands are replayed on reconnect — 'restart' would boot-loop the device."""
    client = FakeClient()
    pub = CommandPublisher(FakeSource(client))
    topic = await pub.publish_grouped("boiler_unit", {"restart": "1"})
    assert topic == "home/devices/boiler_unit/cmd"
    (t, payload, qos, retain), = client.published
    assert json.loads(payload) == {"restart": "1"}
    assert qos == 1
    assert retain is False


@pytest.mark.asyncio
async def test_publish_without_connection_raises():
    pub = CommandPublisher(FakeSource(None))
    assert pub.is_connected is False
    with pytest.raises(PublishError):
        await pub.publish_grouped("boiler_unit", {"k": "v"})


@pytest.mark.asyncio
async def test_publish_failure_raises():
    pub = CommandPublisher(FakeSource(FakeClient(fail=True)))
    with pytest.raises(PublishError):
        await pub.publish_grouped("boiler_unit", {"k": "v"})


@pytest.mark.asyncio
async def test_publisher_follows_reconnected_client():
    """After the handler reconnects, the publisher must use the new connection."""
    source = FakeSource(FakeClient(fail=True))
    pub = CommandPublisher(source)
    with pytest.raises(PublishError):
        await pub.publish_grouped("dev", {"k": "v"})
    source.active_client = FakeClient()
    await pub.publish_grouped("dev", {"k": "v"})
    assert len(source.active_client.published) == 1
