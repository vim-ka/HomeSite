"""Async command dispatcher — debounce + grouping by device ID.

Accumulates params per device, deduplicates keys (last write wins),
then flushes as a single grouped MQTT message per device after debounce.
"""

import asyncio
from typing import Any

import structlog

from device_gateway.publisher import CommandPublisher

logger = structlog.get_logger(__name__)


class AsyncCommandDispatcher:
    """Debounces outgoing commands per device.

    When add_param() is called, the param is queued. Duplicate keys are
    overwritten (last value wins). After `debounce_seconds` of inactivity,
    all accumulated params are flushed as one MQTT message per device.
    """

    def __init__(self, publisher: CommandPublisher, debounce_seconds: float = 5.0):
        self.publisher = publisher
        self.debounce_seconds = debounce_seconds
        self._device_store: dict[str, dict[str, Any]] = {}
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def add_param(self, device_id: str, key: str, value: Any) -> None:
        """Queue a parameter for a device. Resets the debounce timer."""
        async with self._lock:
            if device_id not in self._device_store:
                self._device_store[device_id] = {}
            self._device_store[device_id][key] = value
            self._schedule_flush()

    def _schedule_flush(self) -> None:
        """Cancel existing timer, start a new one."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        self._flush_task = asyncio.create_task(self._delayed_flush())

    async def _delayed_flush(self) -> None:
        """Wait for debounce period, then flush all queued commands."""
        await asyncio.sleep(self.debounce_seconds)
        await self.flush_all()

    async def flush_all(self) -> None:
        """Flush all queued commands — one grouped MQTT message per device."""
        async with self._lock:
            items = self._device_store.copy()
            self._device_store.clear()

        for device_id, params in items.items():
            try:
                str_params = {k: str(v) for k, v in params.items()}
                await self.publisher.publish_grouped(device_id, str_params)
            except Exception as e:
                logger.error(
                    "dispatch_publish_error",
                    device_id=device_id,
                    error=str(e),
                )

    async def pending_for(self, device_id: str) -> dict[str, Any]:
        """Get pending params for a device (for diagnostics)."""
        async with self._lock:
            return dict(self._device_store.get(device_id, {}))

    async def shutdown(self) -> None:
        """Flush everything and cancel pending timer."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        await self.flush_all()
