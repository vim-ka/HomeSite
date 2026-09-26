"""Tests for AsyncCommandDispatcher — debounce logic."""

import asyncio

import pytest


class FakePublisher:
    """Records publish_grouped calls instead of using real MQTT."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []  # (device_id, params)

    async def publish_grouped(self, device_id: str, params: dict[str, str]) -> None:
        self.calls.append((device_id, dict(params)))


@pytest.fixture
def publisher():
    return FakePublisher()


@pytest.fixture
def dispatcher(publisher):
    from device_gateway.dispatcher import AsyncCommandDispatcher
    return AsyncCommandDispatcher(publisher, debounce_seconds=0.1)


@pytest.mark.asyncio
async def test_add_and_flush(dispatcher, publisher):
    """Commands are queued and flushed as a single grouped message after debounce."""
    await dispatcher.add_param("boiler", "tmp", "55")
    await dispatcher.add_param("boiler", "prs", "1.5")

    # Not yet flushed
    assert len(publisher.calls) == 0

    # Wait for debounce to fire
    await asyncio.sleep(0.2)

    # One grouped message for the device
    assert len(publisher.calls) == 1
    device_id, params = publisher.calls[0]
    assert device_id == "boiler"
    assert params == {"tmp": "55", "prs": "1.5"}


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

    # Wait for debounce to complete — one grouped message
    await asyncio.sleep(0.15)
    assert len(publisher.calls) == 1
    assert publisher.calls[0][1] == {"power": "1", "speed": "3"}


@pytest.mark.asyncio
async def test_flush_all_immediate(dispatcher, publisher):
    """flush_all sends one grouped message per device immediately."""
    await dispatcher.add_param("dev1", "k1", "v1")
    await dispatcher.add_param("dev2", "k2", "v2")
    await dispatcher.flush_all()

    assert len(publisher.calls) == 2
    devices = {c[0] for c in publisher.calls}
    assert devices == {"dev1", "dev2"}


@pytest.mark.asyncio
async def test_pending_for(dispatcher, publisher):
    """pending_for returns queued params for a device without flushing."""
    await dispatcher.add_param("dev1", "k1", "v1")
    await dispatcher.add_param("dev2", "k2", "v2")

    pending = await dispatcher.pending_for("dev2")
    assert pending == {"k2": "v2"}

    # Nothing flushed yet
    assert len(publisher.calls) == 0


@pytest.mark.asyncio
async def test_overwrite_same_key(dispatcher, publisher):
    """Later values for the same device+key overwrite earlier ones."""
    await dispatcher.add_param("boiler", "tmp", "50")
    await dispatcher.add_param("boiler", "tmp", "55")
    await dispatcher.flush_all()

    assert len(publisher.calls) == 1
    device_id, params = publisher.calls[0]
    assert device_id == "boiler"
    assert params == {"tmp": "55"}


@pytest.mark.asyncio
async def test_shutdown_flushes(dispatcher, publisher):
    """shutdown() flushes pending commands."""
    await dispatcher.add_param("dev1", "k1", "v1")
    await dispatcher.shutdown()

    assert len(publisher.calls) == 1
    assert publisher.calls[0] == ("dev1", {"k1": "v1"})


class FailingPublisher(FakePublisher):
    """Fails the first N publishes, then succeeds."""

    def __init__(self, failures: int):
        super().__init__()
        self.failures = failures

    async def publish_grouped(self, device_id: str, params: dict[str, str]) -> None:
        if self.failures > 0:
            self.failures -= 1
            from device_gateway.publisher import PublishError
            raise PublishError("MQTT not connected")
        await super().publish_grouped(device_id, params)


class SlowPublisher(FakePublisher):
    """Publishing takes a while (QoS1 waits for PUBACK)."""

    async def publish_grouped(self, device_id: str, params: dict[str, str]) -> None:
        await asyncio.sleep(0.1)
        await super().publish_grouped(device_id, params)


@pytest.mark.asyncio
async def test_failed_publish_is_requeued_and_retried():
    """A broker outage must not drop commands: they go back to the queue and are retried."""
    from device_gateway.dispatcher import AsyncCommandDispatcher

    pub = FailingPublisher(failures=1)
    d = AsyncCommandDispatcher(pub, debounce_seconds=0.05, retry_delay_seconds=0.05)
    await d.add_param("boiler", "heating_boiler_temp", "60")
    await asyncio.sleep(0.08)
    assert pub.calls == []
    assert d.last_publish_error
    assert d.queued_count == 1
    assert d.awaiting_ack_count == 0

    await asyncio.sleep(0.1)
    assert pub.calls == [("boiler", {"heating_boiler_temp": "60"})]
    assert d.last_publish_error is None
    assert d.awaiting_ack_count == 1


@pytest.mark.asyncio
async def test_requeue_keeps_newer_value():
    """If a newer value was queued while publishing failed, the newer value wins."""
    from device_gateway.dispatcher import AsyncCommandDispatcher

    pub = FailingPublisher(failures=1)
    d = AsyncCommandDispatcher(pub, debounce_seconds=10, retry_delay_seconds=10)
    await d.add_param("boiler", "k", "old")
    await d.flush_all()  # fails, requeues "old"
    await d.add_param("boiler", "k", "new")
    await d.flush_all()
    assert pub.calls == [("boiler", {"k": "new"})]
    await d.shutdown()


@pytest.mark.asyncio
async def test_new_command_during_flush_does_not_cancel_it():
    """A command arriving while a flush is publishing must not abort that flush."""
    from device_gateway.dispatcher import AsyncCommandDispatcher

    pub = SlowPublisher()
    d = AsyncCommandDispatcher(pub, debounce_seconds=0.02)
    await d.add_param("dev1", "a", "1")
    await d.add_param("dev2", "b", "2")
    await asyncio.sleep(0.05)  # flush started, dev1 publish in progress
    await d.add_param("dev3", "c", "3")
    await asyncio.sleep(0.4)
    assert sorted(c[0] for c in pub.calls) == ["dev1", "dev2", "dev3"]


@pytest.mark.asyncio
async def test_debounce_has_max_wait():
    """A steady stream of changes must not postpone sending forever."""
    from device_gateway.dispatcher import AsyncCommandDispatcher

    pub = FakePublisher()
    d = AsyncCommandDispatcher(pub, debounce_seconds=0.1, max_wait_seconds=0.25)
    for i in range(8):
        await d.add_param("dev", "k", str(i))
        await asyncio.sleep(0.05)
    # 8 * 0.05 = 0.4s of continuous changes > max_wait 0.25s
    assert len(pub.calls) >= 1


@pytest.mark.asyncio
async def test_ack_rejection_marks_unsynced(dispatcher, publisher):
    await dispatcher.add_param("boiler", "heating_boiler_max_temp", "150")
    await dispatcher.flush_all()
    rejected = await dispatcher.handle_ack("boiler", {"heating_boiler_max_temp": "invalid_value"})
    assert rejected == [("heating_boiler_max_temp", "invalid_value")]
    assert dispatcher.unsynced == {"boiler": {"heating_boiler_max_temp"}}
    assert dispatcher.awaiting_ack_count == 0


@pytest.mark.asyncio
async def test_ok_ack_confirms(dispatcher, publisher):
    await dispatcher.add_param("boiler", "heating_boiler_temp", "60")
    await dispatcher.flush_all()
    assert await dispatcher.handle_ack("boiler", {"heating_boiler_temp": "ok"}) == []
    assert dispatcher.awaiting_ack_count == 0
    assert dispatcher.unsynced == {}
