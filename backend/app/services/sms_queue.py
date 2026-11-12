"""SMS queue: hands merged messages to the phone, takes its reports, keeps the API keys and the phone's health.

`SmsNotifier` writes `sms_item` rows (pending); `next_message` forms all ready items for one number into one
immutable `sms_message`, leases it to the phone and retries failures. Captures are guarded `UPDATE … WHERE state`
with a `rowcount` check: the HealthMonitor writes the same tables from its own session."""

import asyncio
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, time, timedelta
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigKV
from app.models.sms import SmsItem, SmsMessage, SmsSubscription
from app.models.user import User
from app.services.sms_policy import Cfg, in_quiet
from app.services.sms_text import Part, merge

LEASE_S = 600
RETRY_S = (300, 900, 3600)
MAX_ATTEMPTS = 3
SILENT_MIN_S = 900
DEFAULT_POLL_S = 60

class _LoopLock:
    """An asyncio.Lock for the running loop (tests run each in its own loop; production has one)."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = asyncio.Lock()

    def _current(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if loop is not self._loop:
            self._loop, self._lock = loop, asyncio.Lock()
        return self._lock

    def locked(self) -> bool:
        return self._lock.locked()

    async def __aenter__(self) -> None:
        await self._current().acquire()

    async def __aexit__(self, *exc) -> None:
        self._lock.release()


# Serialises every read-decide-commit on SMS items/messages/subscriptions (SmsNotifier vs the phone API).
# Assumes one process / one event loop (single uvicorn worker running the HealthMonitor too).
SMS_LOCK = _LoopLock()

Mode = Literal["live", "test"]
_MODES: tuple[Mode, ...] = ("live", "test")
_NO_UPDATE_SYNC = {"synchronize_session": False}


def _now() -> datetime:
    return datetime.now(UTC)


def _utc(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ── config_kv ──────────────────────────────────────────────────────────────


async def _get(session: AsyncSession, key: str) -> str | None:
    return (await session.execute(select(ConfigKV.value).where(ConfigKV.key == key))).scalar_one_or_none()


async def _set(session: AsyncSession, key: str, value: str) -> None:
    row = (await session.execute(select(ConfigKV).where(ConfigKV.key == key))).scalar_one_or_none()
    if row is None:
        session.add(ConfigKV(key=key, value=value))
    else:
        row.value = value


async def poll_seconds(session: AsyncSession) -> int:
    try:
        return max(1, int(await _get(session, "sms_poll_seconds") or DEFAULT_POLL_S))
    except ValueError:
        return DEFAULT_POLL_S


def _parse_hhmm(value: str | None) -> time | None:
    try:
        return time.fromisoformat(value) if value else None
    except ValueError:
        return None


async def quiet_now(session: AsyncSession, now: datetime) -> bool:
    """Whether `now` is inside the quiet hours (`sms_quiet_start`/`sms_quiet_end`, HH:MM UTC; absent → none)."""
    cfg = Cfg(_parse_hhmm(await _get(session, "sms_quiet_start")), _parse_hhmm(await _get(session, "sms_quiet_end")))
    return in_quiet(now, cfg)


# ── keys ───────────────────────────────────────────────────────────────────


async def issue_key(session: AsyncSession, mode: Mode) -> str:
    """New key for the mode (replaces the old one); only its SHA-256 is stored. Shown to the admin once."""
    if mode not in _MODES:
        raise ValueError(f"unknown SMS key mode: {mode!r}")
    key = secrets.token_urlsafe(32)
    await _set(session, f"sms_key_{mode}_hash", _hash(key))
    await _set(session, f"sms_key_{mode}_issued_at", _now().isoformat())
    await session.commit()
    return key


async def key_mode(session: AsyncSession, key: str) -> Mode | None:
    if not key:
        return None
    digest = _hash(key)
    found: Mode | None = None
    for mode in _MODES:
        stored = await _get(session, f"sms_key_{mode}_hash")
        if stored and hmac.compare_digest(stored, digest):
            found = mode
    return found


# ── queue ──────────────────────────────────────────────────────────────────


async def _lease(session: AsyncSession, msg_id: int, from_state: str, extra, now: datetime) -> SmsMessage | None:
    """Atomically move a message from `from_state` (with the extra condition) to `leased`."""
    res = await session.execute(
        update(SmsMessage)
        .where(SmsMessage.id == msg_id, SmsMessage.state == from_state, extra)
        .values(state="leased", leased_until=now + timedelta(seconds=LEASE_S))
        .execution_options(**_NO_UPDATE_SYNC))
    if res.rowcount != 1:
        return None
    await session.commit()
    msg = await session.get(SmsMessage, msg_id)
    await session.refresh(msg)
    return msg


async def _reissue(session: AsyncSession, is_test: bool, now: datetime) -> SmsMessage | None:
    """An expired lease, then a retry that is due: the same message (same text) leased again."""
    for state, cond, order in (
        ("leased", SmsMessage.leased_until < now, SmsMessage.leased_until),
        ("ready", SmsMessage.ready_at <= now, SmsMessage.ready_at),
    ):
        ids = (await session.execute(
            select(SmsMessage.id).where(SmsMessage.is_test.is_(is_test), SmsMessage.state == state, cond)
            .order_by(order, SmsMessage.id))).scalars().all()
        for msg_id in ids:
            msg = await _lease(session, msg_id, state, cond, now)
            if msg is not None:
                return msg
    return None


async def _form(session: AsyncSession, is_test: bool, now: datetime) -> SmsMessage | None:
    """All ready pending items of the oldest ready number → one new leased message."""
    ready = (SmsItem.state == "pending", SmsItem.is_test.is_(is_test), SmsItem.ready_at <= now)
    while True:
        phone = (await session.execute(
            select(SmsItem.phone).where(*ready).order_by(SmsItem.ready_at, SmsItem.id).limit(1))).scalar_one_or_none()
        if phone is None:
            return None
        ids = (await session.execute(
            select(SmsItem.id).where(*ready, SmsItem.phone == phone).order_by(SmsItem.id))).scalars().all()

        msg = SmsMessage(phone=phone, text="", is_test=is_test, state="leased", items=0, attempts=0,
                         created_at=now, ready_at=now, leased_until=now + timedelta(seconds=LEASE_S))
        session.add(msg)
        await session.flush()
        captured: list[int] = []
        for item_id in ids:
            res = await session.execute(
                update(SmsItem).where(SmsItem.id == item_id, SmsItem.state == "pending")
                .values(state="formed", message_id=msg.id).execution_options(**_NO_UPDATE_SYNC))
            if res.rowcount == 1:
                captured.append(item_id)
        if not captured:          # all taken meanwhile (superseded / not needed): try the next number
            await session.delete(msg)
            await session.commit()
            continue

        items = list((await session.execute(
            select(SmsItem).where(SmsItem.id.in_(captured)).order_by(SmsItem.id)
            .execution_options(populate_existing=True))).scalars())
        text, _ = merge([Part(it.problem, it.level, it.raised, it.text) for it in items])
        msg.text, msg.items = text, len(items)
        await _record_sent(session, items)
        await session.commit()
        return msg


async def _record_sent(session: AsyncSession, items: list[SmsItem]) -> None:
    """The formed items are what the recipients were told: a raise sets `sent`, a clear ends the episode."""
    for it in items:
        if it.kind == "test" or it.user_id is None:
            continue
        sub = (await session.execute(select(SmsSubscription).where(
            SmsSubscription.problem == it.problem, SmsSubscription.user_id == it.user_id))).scalar_one_or_none()
        if sub is None:
            continue
        sub.changes = 0
        if it.raised:
            sub.sent = it.level
        else:
            sub.sent, sub.episode_start = None, None


async def next_message(session: AsyncSession, is_test: bool, now: datetime) -> SmsMessage | None:
    """What the phone should send now: an expired lease, a due retry, else a newly formed message."""
    async with SMS_LOCK:
        return await _reissue(session, is_test, now) or await _form(session, is_test, now)


async def mark_done(session: AsyncSession, msg_id: int, is_test: bool, ok: bool, error: str | None,
                    now: datetime) -> bool:
    """The phone's report. False if there is no such message for this key's mode; a repeat changes nothing."""
    async with SMS_LOCK:
        return await _mark_done(session, msg_id, is_test, ok, error, now)


async def _mark_done(session: AsyncSession, msg_id: int, is_test: bool, ok: bool, error: str | None,
                     now: datetime) -> bool:
    msg = (await session.execute(select(SmsMessage).where(
        SmsMessage.id == msg_id, SmsMessage.is_test.is_(is_test)))).scalar_one_or_none()
    if msg is None:
        return False
    if msg.state != "leased":       # already reported (sent / waiting for a retry / failed)
        return True
    if ok:
        values = {"state": "sent", "sent_at": now, "leased_until": None}
    else:
        attempts = msg.attempts + 1
        values = {"attempts": attempts, "error": error, "leased_until": None}
        if attempts < MAX_ATTEMPTS:
            values |= {"state": "ready", "ready_at": now + timedelta(seconds=RETRY_S[attempts - 1])}
        else:
            values["state"] = "failed"
    await session.execute(update(SmsMessage).where(SmsMessage.id == msg_id, SmsMessage.state == "leased")
                          .values(**values).execution_options(**_NO_UPDATE_SYNC))
    await session.commit()
    await session.refresh(msg)
    return True


async def queue_size(session: AsyncSession, is_test: bool) -> int:
    """Items still to be formed plus messages not yet reported sent or failed."""
    items = (await session.execute(select(func.count()).select_from(SmsItem).where(
        SmsItem.state == "pending", SmsItem.is_test.is_(is_test)))).scalar_one()
    msgs = (await session.execute(select(func.count()).select_from(SmsMessage).where(
        SmsMessage.state.in_(("ready", "leased")), SmsMessage.is_test.is_(is_test)))).scalar_one()
    return items + msgs


# ── phone health ───────────────────────────────────────────────────────────


async def touch_poll(session: AsyncSession, now: datetime) -> None:
    await _set(session, "sms_last_poll_at", _utc(now).isoformat())
    await session.commit()


def _parse_ts(value: str | None) -> datetime | None:
    try:
        return _utc(datetime.fromisoformat(value)) if value else None
    except ValueError:
        return None


async def _has_recipient(session: AsyncSession) -> bool:
    users = (await session.execute(select(User).where(User.is_active.is_(True)))).scalars()
    return any(u.phone and ({c.strip() for c in (u.sms_categories or "").split(",")} - {"", "test"})
               for u in users)


async def phone_status(session: AsyncSession, now: datetime, poll_s: int) -> dict:
    """Live-queue health: last poll, whether the phone is silent too long, pending items, failed messages."""
    last_raw = await _get(session, "sms_last_poll_at")
    last = _parse_ts(last_raw)
    silent = False
    if await _get(session, "sms_key_live_hash") and await _has_recipient(session):
        since = last or _parse_ts(await _get(session, "sms_key_live_issued_at"))
        if since is not None:
            silent = (now - since).total_seconds() > max(SILENT_MIN_S, 3 * poll_s)
    pending = (await session.execute(select(func.count()).select_from(SmsItem).where(
        SmsItem.state == "pending", SmsItem.is_test.is_(False)))).scalar_one()
    failed = (await session.execute(select(func.count()).select_from(SmsMessage).where(
        SmsMessage.state == "failed", SmsMessage.is_test.is_(False)))).scalar_one()
    return {"last_poll_at": last.isoformat() if last else None, "silent": silent,
            "pending": pending, "failed": failed}
