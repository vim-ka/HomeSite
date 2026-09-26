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
    def __init__(
        self,
        publisher: CommandPublisher,
        debounce_seconds: float = 5.0,
        max_wait_seconds: float = 15.0,
        retry_delay_seconds: float = 5.0,
    ):
        self.publisher = publisher
        self.debounce_seconds = debounce_seconds
        # Upper bound for debounce: a steady stream of changes must not postpone sending forever
        self.max_wait_seconds = max(max_wait_seconds, debounce_seconds)
        self.retry_delay_seconds = retry_delay_seconds
        self._device_store: dict[str, dict[str, Any]] = {}
        self._batch_started: float | None = None
        # Debounce is a plain timer: cancelling it can never interrupt a flush that is already running
        self._flush_timer: asyncio.TimerHandle | None = None
        self._flush_tasks: set[asyncio.Task] = set()
        self._lock = asyncio.Lock()

        # Tracks sent commands awaiting ack: {device_id: {key: PendingCommand}}
        self._pending_acks: dict[str, dict[str, PendingCommand]] = {}
        self._ack_lock = asyncio.Lock()

        # Keys that failed after all retries: {device_id: set(keys)}
        self.unsynced: dict[str, set[str]] = {}

        # Last publish failure (None when the last publish succeeded)
        self.last_publish_error: str | None = None

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

    def _schedule_flush(self, delay: float | None = None) -> None:
        loop = asyncio.get_running_loop()
        now = loop.time()
        if self._batch_started is None:
            self._batch_started = now
        if delay is None:
            deadline = self._batch_started + self.max_wait_seconds
            delay = max(0.0, min(self.debounce_seconds, deadline - now))
        if self._flush_timer is not None:
            self._flush_timer.cancel()
        self._flush_timer = loop.call_later(delay, self._start_flush)

    def _start_flush(self) -> None:
        self._flush_timer = None
        task = asyncio.create_task(self.flush_all())
        self._flush_tasks.add(task)
        task.add_done_callback(self._flush_tasks.discard)

    async def flush_all(self) -> None:
        """Flush all queued commands — one grouped MQTT message per device.

        If publishing fails, the device's params go back to the queue (newer
        values queued meanwhile win) and a retry is scheduled.
        """
        async with self._lock:
            items = self._device_store.copy()
            self._device_store.clear()
            self._batch_started = None

        failed: dict[str, dict[str, str]] = {}
        for device_id, params in items.items():
            str_params = {k: str(v) for k, v in params.items()}
            try:
                await self.publisher.publish_grouped(device_id, str_params)
            except Exception as e:
                logger.error("dispatch_publish_error", device_id=device_id, error=str(e))
                self.last_publish_error = str(e) or type(e).__name__
                failed[device_id] = str_params
                continue

            self.last_publish_error = None
            now = datetime.now(UTC)
            async with self._ack_lock:
                if device_id not in self._pending_acks:
                    self._pending_acks[device_id] = {}
                for key, value in str_params.items():
                    self._pending_acks[device_id][key] = PendingCommand(value=value, sent_at=now)

        if failed:
            async with self._lock:
                for device_id, params in failed.items():
                    store = self._device_store.setdefault(device_id, {})
                    for key, value in params.items():
                        store.setdefault(key, value)
                self._schedule_flush(self.retry_delay_seconds)

    async def handle_ack(self, device_name: str, acked_keys: dict[str, str]) -> list[tuple[str, str]]:
        """Process ack from device.

        Value "ok" confirms the key. Any other value (e.g. "invalid_value",
        "unknown_key", "persist_failed") means the device rejected it: the key
        is marked unsynced right away instead of being retried.
        Returns the rejected (key, reason) pairs.
        """
        rejected = [(k, str(v)) for k, v in acked_keys.items() if str(v) != "ok"]

        async with self._ack_lock:
            pending = self._pending_acks.get(device_name, {})
            for key in acked_keys:
                pending.pop(key, None)
            if not pending:
                self._pending_acks.pop(device_name, None)

        if device_name in self.unsynced:
            for key in acked_keys:
                self.unsynced[device_name].discard(key)
            if not self.unsynced[device_name]:
                del self.unsynced[device_name]
        for key, _reason in rejected:
            self.unsynced.setdefault(device_name, set()).add(key)

        if rejected:
            logger.warning("ack_rejected", device=device_name, rejected=rejected)
        logger.info("ack_received", device=device_name, keys=list(acked_keys.keys()))
        return rejected

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
                self.last_publish_error = str(e) or type(e).__name__

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

    def sync_status(self) -> dict[str, dict[str, list[str]]]:
        """Keys not confirmed yet (still in the debounce queue or awaiting ack)
        and keys that failed, per device (for the UI)."""
        queued = {device: set(params) for device, params in self._device_store.items() if params}
        devices = set(self._pending_acks) | set(self.unsynced) | set(queued)
        return {
            device: {
                "pending": sorted(set(self._pending_acks.get(device, {})) | queued.get(device, set())),
                "unsynced": sorted(self.unsynced.get(device, set())),
            }
            for device in sorted(devices)
        }

    async def pending_for(self, device_id: str) -> dict[str, Any]:
        async with self._lock:
            return dict(self._device_store.get(device_id, {}))

    async def shutdown(self) -> None:
        if self._flush_timer is not None:
            self._flush_timer.cancel()
            self._flush_timer = None
        if self._flush_tasks:
            await asyncio.gather(*self._flush_tasks, return_exceptions=True)
        await self.flush_all()
        if self._flush_timer is not None:
            # flush failed and scheduled a retry — nobody will run it after shutdown
            self._flush_timer.cancel()
            self._flush_timer = None
