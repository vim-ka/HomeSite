"""Async command dispatcher — debounce + grouping + retry + ack tracking.

Accumulates params per device, deduplicates keys (last write wins),
flushes as a single grouped MQTT message per device after debounce.
Retries on ack timeout, marks as unsynced after max retries.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from device_gateway.publisher import CommandPublisher

logger = structlog.get_logger(__name__)

ACK_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2


@dataclass
class PendingCommand:
    value: str
    sent_at: datetime
    retries: int = 0


class AsyncCommandDispatcher:
    def __init__(self, publisher: CommandPublisher, debounce_seconds: float = 5.0):
        self.publisher = publisher
        self.debounce_seconds = debounce_seconds
        self._device_store: dict[str, dict[str, Any]] = {}
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

        # Tracks sent commands awaiting ack: {device_id: {key: PendingCommand}}
        self._pending_acks: dict[str, dict[str, PendingCommand]] = {}
        self._ack_lock = asyncio.Lock()

        # Keys that failed after all retries: {device_id: set(keys)}
        self.unsynced: dict[str, set[str]] = {}

    async def add_param(self, device_id: str, key: str, value: Any) -> None:
        """Queue a parameter for a device. Resets the debounce timer."""
        async with self._lock:
            if device_id not in self._device_store:
                self._device_store[device_id] = {}
            self._device_store[device_id][key] = value
            self._schedule_flush()

        # Clear unsync flag — user is sending a new value
        if device_id in self.unsynced:
            self.unsynced[device_id].discard(key)
            if not self.unsynced[device_id]:
                del self.unsynced[device_id]

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

                async with self._ack_lock:
                    if device_id not in self._pending_acks:
                        self._pending_acks[device_id] = {}
                    for key, value in str_params.items():
                        self._pending_acks[device_id][key] = PendingCommand(
                            value=value, sent_at=now
                        )

            except Exception as e:
                logger.error("dispatch_publish_error", device_id=device_id, error=str(e))

    async def handle_ack(self, device_name: str, acked_keys: dict[str, str]) -> None:
        """Process ack from device — remove keys from pending and unsynced."""
        async with self._ack_lock:
            pending = self._pending_acks.get(device_name, {})
            for key in acked_keys:
                pending.pop(key, None)
            if not pending:
                self._pending_acks.pop(device_name, None)

        # Clear unsync flags for acked keys
        if device_name in self.unsynced:
            for key in acked_keys:
                self.unsynced[device_name].discard(key)
            if not self.unsynced[device_name]:
                del self.unsynced[device_name]

        logger.info("ack_received", device=device_name, keys=list(acked_keys.keys()))

    async def check_ack_timeouts(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """Check for commands that were not acknowledged within timeout.

        Returns (retried, failed):
          retried: list of (device, key) that were re-sent
          failed: list of (device, key) that exhausted retries → marked unsynced
        """
        now = datetime.now(UTC)
        timeout = getattr(self, "_ack_timeout", ACK_TIMEOUT_SECONDS)
        to_retry: dict[str, dict[str, str]] = {}  # device → {key: value}
        failed: list[tuple[str, str]] = []

        async with self._ack_lock:
            for device_id, keys in list(self._pending_acks.items()):
                for key, cmd in list(keys.items()):
                    if (now - cmd.sent_at).total_seconds() > timeout:
                        if cmd.retries < MAX_RETRIES:
                            # Schedule retry
                            cmd.retries += 1
                            cmd.sent_at = now
                            if device_id not in to_retry:
                                to_retry[device_id] = {}
                            to_retry[device_id][key] = cmd.value
                            logger.info("command_retry", device=device_id, key=key, attempt=cmd.retries)
                        else:
                            # Max retries exhausted
                            failed.append((device_id, key))
                            del keys[key]
                            # Mark as unsynced
                            if device_id not in self.unsynced:
                                self.unsynced[device_id] = set()
                            self.unsynced[device_id].add(key)
                if not keys:
                    del self._pending_acks[device_id]

        # Re-send retried commands
        retried: list[tuple[str, str]] = []
        for device_id, params in to_retry.items():
            try:
                await self.publisher.publish_grouped(device_id, params)
                retried.extend((device_id, k) for k in params)
            except Exception as e:
                logger.error("retry_publish_error", device_id=device_id, error=str(e))

        return retried, failed

    @property
    def queued_count(self) -> int:
        """Commands in debounce queue (not yet sent)."""
        return sum(len(p) for p in self._device_store.values())

    @property
    def awaiting_ack_count(self) -> int:
        """Commands sent, waiting for device ack."""
        return sum(len(k) for k in self._pending_acks.values())

    @property
    def unsynced_count(self) -> int:
        """Total keys that failed after all retries."""
        return sum(len(keys) for keys in self.unsynced.values())

    async def pending_for(self, device_id: str) -> dict[str, Any]:
        async with self._lock:
            return dict(self._device_store.get(device_id, {}))

    async def shutdown(self) -> None:
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        await self.flush_all()
