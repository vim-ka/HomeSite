"""Tests for AsyncCommandDispatcher — debounce logic."""

import asyncio

import pytest


class FakePublisher:
    """Records publish calls instead of using real MQTT."""

    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []

    async def publish(self, device_id: str, parameter: str, value: str) -> str:
        self.calls.append((device_id, parameter, value))
        return f"home/devices/{device_id}/command/{parameter}"


@pytest.fixture
def publisher():
    return FakePublisher()


@pytest.fixture
def dispatcher(publisher):
    from device_gateway.dispatcher import AsyncCommandDispatcher
    return AsyncCommandDispatcher(publisher, debounce_seconds=0.1)


@pytest.mark.asyncio
async def test_add_and_flush(dispatcher, publisher):
    """Commands are queued and flushed after debounce."""
    await dispatcher.add_param("boiler", "tmp", "55")
    await dispatcher.add_param("boiler", "prs", "1.5")

    # Not yet flushed
    assert len(publisher.calls) == 0

    # Wait for debounce to fire
    await asyncio.sleep(0.2)

    assert len(publisher.calls) == 2
    devices = {c[0] for c in publisher.calls}
    assert devices == {"boiler"}
    params = {c[1] for c in publisher.calls}
    assert params == {"tmp", "prs"}


@pytest.mark.asyncio
async def test_debounce_resets(dispatcher, publisher):
    """Each add_param resets the debounce timer."""
    await dispatcher.add_param("pump", "power", "1")
    await asyncio.sleep(0.05)
    # Add another param before debounce fires — should reset timer
    await dispatcher.add_param("pump", "speed", "3")
    await asyncio.sleep(0.05)
    # Should not have flushed yet (0.05 + 0.05 < reset timer of 0.1)
    assert len(publisher.calls) == 0

    # Wait for debounce to complete
    await asyncio.sleep(0.15)
    assert len(publisher.calls) == 2


@pytest.mark.asyncio
async def test_flush_all_immediate(dispatcher, publisher):
    """flush_all sends everything immediately without waiting for debounce."""
    await dispatcher.add_param("dev1", "k1", "v1")
    await dispatcher.add_param("dev2", "k2", "v2")
    await dispatcher.flush_all()

    assert len(publisher.calls) == 2


@pytest.mark.asyncio
async def test_flush_device(dispatcher, publisher):
    """flush_device sends only that device's commands."""
    await dispatcher.add_param("dev1", "k1", "v1")
    await dispatcher.add_param("dev2", "k2", "v2")
    await dispatcher.flush_device("dev1")

    assert len(publisher.calls) == 1
    assert publisher.calls[0] == ("dev1", "k1", "v1")

    # dev2 still pending
    pending = await dispatcher.pending_for("dev2")
    assert pending == {"k2": "v2"}


@pytest.mark.asyncio
async def test_overwrite_same_key(dispatcher, publisher):
    """Later values for the same device+key overwrite earlier ones."""
    await dispatcher.add_param("boiler", "tmp", "50")
    await dispatcher.add_param("boiler", "tmp", "55")
    await dispatcher.flush_all()

    assert len(publisher.calls) == 1
    assert publisher.calls[0] == ("boiler", "tmp", "55")


@pytest.mark.asyncio
async def test_shutdown_flushes(dispatcher, publisher):
    """shutdown() flushes pending commands."""
    await dispatcher.add_param("dev1", "k1", "v1")
    await dispatcher.shutdown()

    assert len(publisher.calls) == 1
