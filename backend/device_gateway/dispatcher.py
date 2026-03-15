"""Async command dispatcher — debounce + grouping by device ID.

Accumulates params per device, deduplicates keys (last write wins),
then flushes as a single grouped MQTT message per device after debounce.
Tracks sent commands and checks for ack from devices.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog

from device_gateway.publisher import CommandPublisher

logger = structlog.get_logger(__name__)

# How long to wait for ack before generating a warning
ACK_TIMEOUT_SECONDS = 30


class AsyncCommandDispatcher:
    def __init__(self, publisher: CommandPublisher, debounce_seconds: float = 5.0):
        self.publisher = publisher
        self.debounce_seconds = debounce_seconds
        self._device_store: dict[str, dict[str, Any]] = {}
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

        # Tracks sent commands awaiting ack: {device_id: {key: sent_at}}
        self._pending_acks: dict[str, dict[str, datetime]] = {}
        self._ack_lock = asyncio.Lock()

        # Callback for unacknowledged commands (set by __main__)
        self.on_ack_timeout: Any = None

    async def add_param(self, device_id: str, key: str, value: Any) -> None:
        """Queue a parameter for a device. Resets the debounce timer."""
        async with self._lock:
            if device_id not in self._device_store:
                self._device_store[device_id] = {}
            self._device_store[device_id][key] = value
            self._schedule_flush()

    def _schedule_flush(self) -> None:
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        self._flush_task = asyncio.create_task(self._delayed_flush())

    async def _delayed_flush(self) -> None:
        await asyncio.sleep(self.debounce_seconds)
        await self.flush_all()

    async def flush_all(self) -> None:
        """Flush all queued commands — one grouped MQTT message per device."""
        async with self._lock:
            items = self._device_store.copy()
            self._device_store.clear()

        now = datetime.now(UTC)
        for device_id, params in items.items():
            try:
                str_params = {k: str(v) for k, v in params.items()}
                await self.publisher.publish_grouped(device_id, str_params)

                # Track for ack
                async with self._ack_lock:
                    if device_id not in self._pending_acks:
                        self._pending_acks[device_id] = {}
                    for key in str_params:
                        self._pending_acks[device_id][key] = now

            except Exception as e:
                logger.error("dispatch_publish_error", device_id=device_id, error=str(e))

    async def handle_ack(self, device_name: str, acked_keys: dict[str, str]) -> None:
        """Process ack from device — remove keys from pending."""
        async with self._ack_lock:
            pending = self._pending_acks.get(device_name, {})
            for key in acked_keys:
                pending.pop(key, None)
            if not pending:
                self._pending_acks.pop(device_name, None)

        logger.info("ack_received", device=device_name, keys=list(acked_keys.keys()))

    async def check_ack_timeouts(self) -> list[tuple[str, str]]:
        """Check for commands that were not acknowledged within timeout.

        Returns list of (device_name, key) that timed out.
        """
        now = datetime.now(UTC)
        timeout = getattr(self, "_ack_timeout", ACK_TIMEOUT_SECONDS)
        timed_out: list[tuple[str, str]] = []

        async with self._ack_lock:
            for device_id, keys in list(self._pending_acks.items()):
                for key, sent_at in list(keys.items()):
                    if (now - sent_at).total_seconds() > timeout:
                        timed_out.append((device_id, key))
                        del keys[key]
                if not keys:
                    del self._pending_acks[device_id]

        return timed_out

    async def pending_for(self, device_id: str) -> dict[str, Any]:
        async with self._lock:
            return dict(self._device_store.get(device_id, {}))

    async def shutdown(self) -> None:
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        await self.flush_all()
