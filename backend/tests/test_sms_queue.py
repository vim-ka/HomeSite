"""SMS queue: forming pending items into messages, leases, retries and the phone's health (DB-backed)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.config import ConfigKV
from app.models.sms import SmsItem, SmsMessage, SmsSubscription
from app.models.user import User
from app.services.sms_queue import (
    LEASE_S,
    MAX_ATTEMPTS,
    RETRY_S,
    issue_key,
    key_mode,
    mark_done,
    next_message,
    phone_status,
    touch_poll,
)

T0 = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
PHONE = "+79990000001"


def _utc(ts: datetime | None) -> datetime | None:
    return None if ts is None else (ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts)


async def add_user(db, name: str, phone: str | None = PHONE, cats: str = "critical,warning") -> User:
    u = User(username=name, password_hash="x", email=f"{name}@x", role="viewer", phone=phone, sms_categories=cats)
    db.add(u)
    await db.commit()
    return u


async def add_sub(db, problem: str, user: User, sent: str | None = None, changes: int = 0,
                  episode_start: datetime | None = None) -> SmsSubscription:
    s = SmsSubscription(problem=problem, user_id=user.id, sent=sent, seen=sent, changes=changes,
                        episode_start=episode_start, last_text="", code=problem)
    db.add(s)
    await db.commit()
    return s


async def add_item(db, problem: str, user: User | None, text: str, *, level: str = "ERROR", raised: bool = True,
                   kind: str = "first", phone: str = PHONE, ready_at: datetime = T0, is_test: bool = False,
                   created_at: datetime | None = None) -> SmsItem:
    it = SmsItem(problem=problem, code=problem, level=level, raised=raised, kind=kind,
                 user_id=user.id if user else None, phone=phone, text=text, is_test=is_test, state="pending",
                 created_at=created_at or ready_at - timedelta(seconds=60), ready_at=ready_at)
    db.add(it)
    await db.commit()
    return it


async def all_items(db) -> list[SmsItem]:
    db.expire_all()
    return list((await db.execute(select(SmsItem).order_by(SmsItem.id))).scalars())


@pytest.mark.asyncio
async def test_merge_same_phone_into_one_message(db_session):
    u = await add_user(db_session, "a")
    await add_item(db_session, "pressure", u, "Низкое давление: 0.4 бар")
    await add_item(db_session, "rooms", u, "Холодно в доме: 12 °C", level="WARNING")
    msg = await next_message(db_session, False, T0)
    assert msg is not None
    assert msg.items == 2
    assert msg.phone == PHONE
    assert msg.state == "leased"
    assert msg.text == "Низкое давление: 0.4 бар; Холодно в доме: 12 °C"
    msg_id = msg.id
    got = await all_items(db_session)
    assert [i.state for i in got] == ["formed", "formed"]
    assert {i.message_id for i in got} == {msg_id}
    assert await next_message(db_session, False, T0) is None


@pytest.mark.asyncio
async def test_shared_number_one_sms_problem_once(db_session):
    a = await add_user(db_session, "a")
    b = await add_user(db_session, "b")
    sa = await add_sub(db_session, "pressure", a)
    sb = await add_sub(db_session, "pressure", b)
    await add_item(db_session, "pressure", a, "Низкое давление: 0.4 бар")
    await add_item(db_session, "pressure", b, "Низкое давление: 0.4 бар")
    msg = await next_message(db_session, False, T0)
    assert msg.text == "Низкое давление: 0.4 бар"
    msg_id = msg.id
    got = await all_items(db_session)
    assert [i.state for i in got] == ["formed", "formed"]
    assert {i.message_id for i in got} == {msg_id}
    await db_session.refresh(sa)
    await db_session.refresh(sb)
    assert sa.sent == "ERROR" and sb.sent == "ERROR"


@pytest.mark.asyncio
async def test_not_ready_not_issued(db_session):
    u = await add_user(db_session, "a")
    await add_item(db_session, "pressure", u, "Низкое давление", ready_at=T0 + timedelta(seconds=30))
    assert await next_message(db_session, False, T0) is None
    assert (await all_items(db_session))[0].state == "pending"
    msg = await next_message(db_session, False, T0 + timedelta(seconds=30))
    assert msg is not None


@pytest.mark.asyncio
async def test_not_ready_item_of_same_phone_waits(db_session):
    u = await add_user(db_session, "a")
    await add_item(db_session, "pressure", u, "Низкое давление")
    await add_item(db_session, "rooms", u, "Холодно", ready_at=T0 + timedelta(minutes=10))
    msg = await next_message(db_session, False, T0)
    assert msg.items == 1
    assert [i.state for i in await all_items(db_session)] == ["formed", "pending"]


@pytest.mark.asyncio
async def test_expired_lease_reissues_same_text(db_session):
    u = await add_user(db_session, "a")
    await add_item(db_session, "pressure", u, "Низкое давление")
    msg = await next_message(db_session, False, T0)
    first_id, first_text = msg.id, msg.text
    assert await next_message(db_session, False, T0 + timedelta(seconds=LEASE_S - 1)) is None
    later = T0 + timedelta(seconds=LEASE_S + 1)
    again = await next_message(db_session, False, later)
    assert again is not None
    assert (again.id, again.text, again.state) == (first_id, first_text, "leased")
    assert _utc(again.leased_until) == later + timedelta(seconds=LEASE_S)


@pytest.mark.asyncio
async def test_failure_retries_then_failed(db_session):
    assert RETRY_S == (300, 900, 3600) and MAX_ATTEMPTS == 3 and LEASE_S == 600
    u = await add_user(db_session, "a")
    await add_item(db_session, "pressure", u, "Низкое давление")
    now = T0
    msg = await next_message(db_session, False, now)
    for attempt, pause in enumerate((300, 900), start=1):
        assert await mark_done(db_session, msg.id, False, False, "нет сети", now) is True
        await db_session.refresh(msg)
        assert (msg.state, msg.attempts, msg.error) == ("ready", attempt, "нет сети")
        assert _utc(msg.ready_at) == now + timedelta(seconds=pause)
        assert await next_message(db_session, False, now + timedelta(seconds=pause - 1)) is None
        now = now + timedelta(seconds=pause)
        again = await next_message(db_session, False, now)
        assert again.id == msg.id and again.text == msg.text and again.state == "leased"
    assert await mark_done(db_session, msg.id, False, False, "нет сети", now) is True
    await db_session.refresh(msg)
    assert (msg.state, msg.attempts) == ("failed", 3)
    assert await next_message(db_session, False, now + timedelta(days=1)) is None


@pytest.mark.asyncio
async def test_done_ok_and_repeat(db_session):
    u = await add_user(db_session, "a")
    await add_item(db_session, "pressure", u, "Низкое давление")
    msg = await next_message(db_session, False, T0)
    assert await mark_done(db_session, msg.id, False, True, None, T0 + timedelta(seconds=5)) is True
    await db_session.refresh(msg)
    assert msg.state == "sent" and _utc(msg.sent_at) == T0 + timedelta(seconds=5)
    assert await mark_done(db_session, msg.id, False, False, "x", T0 + timedelta(seconds=9)) is True
    await db_session.refresh(msg)
    assert msg.state == "sent" and msg.attempts == 0 and _utc(msg.sent_at) == T0 + timedelta(seconds=5)
    assert await mark_done(db_session, msg.id + 100, False, True, None, T0) is False
    assert await mark_done(db_session, msg.id, True, True, None, T0) is False


@pytest.mark.asyncio
async def test_formed_message_is_immutable(db_session):
    u = await add_user(db_session, "a")
    await add_sub(db_session, "pressure", u)
    await add_item(db_session, "pressure", u, "Низкое давление: 0.4 бар")
    first = await next_message(db_session, False, T0)
    await add_item(db_session, "pressure", u, "Снято: Низкое давление", raised=False, kind="summary",
                   ready_at=T0 + timedelta(seconds=10))
    second = await next_message(db_session, False, T0 + timedelta(seconds=10))
    assert second is not None and second.id != first.id
    assert second.text == "Снято: Низкое давление"
    await db_session.refresh(first)
    assert first.text == "Низкое давление: 0.4 бар" and first.items == 1 and first.state == "leased"


@pytest.mark.asyncio
async def test_formation_sets_sent(db_session):
    u = await add_user(db_session, "a")
    start = T0 - timedelta(minutes=30)
    sub = await add_sub(db_session, "pressure", u, changes=0, episode_start=start)
    await add_item(db_session, "pressure", u, "Низкое давление")
    await next_message(db_session, False, T0)
    await db_session.refresh(sub)
    assert (sub.sent, sub.changes, _utc(sub.episode_start)) == ("ERROR", 0, start)

    sub.changes = 3
    await db_session.commit()
    await add_item(db_session, "pressure", u, "Снято: Низкое давление", raised=False, kind="summary")
    await next_message(db_session, False, T0 + timedelta(seconds=1))
    await db_session.refresh(sub)
    assert (sub.sent, sub.changes, sub.episode_start) == (None, 0, None)


@pytest.mark.asyncio
async def test_test_and_live_isolated(db_session):
    u = await add_user(db_session, "a", cats="critical,test")
    await add_item(db_session, "test", u, "Тестовое СМС", level="INFO", kind="test", is_test=True)
    assert await next_message(db_session, False, T0) is None
    await add_item(db_session, "pressure", u, "Низкое давление")
    live = await next_message(db_session, False, T0)
    assert live.text == "Низкое давление" and live.is_test is False
    test = await next_message(db_session, True, T0)
    assert test.text == "Тестовое СМС" and test.is_test is True
    assert await mark_done(db_session, live.id, True, True, None, T0) is False
    assert await mark_done(db_session, test.id, False, True, None, T0) is False
    assert await mark_done(db_session, test.id, True, True, None, T0) is True


@pytest.mark.asyncio
async def test_keys_hashed_and_modes(db_session):
    live = await issue_key(db_session, "live")
    test = await issue_key(db_session, "test")
    assert live != test and len(live) >= 40
    rows = {r.key: r.value for r in (await db_session.execute(select(ConfigKV))).scalars()}
    assert live not in rows.values() and test not in rows.values()
    assert len(rows["sms_key_live_hash"]) == 64
    assert "sms_key_live_issued_at" in rows and "sms_key_test_issued_at" in rows
    assert await key_mode(db_session, live) == "live"
    assert await key_mode(db_session, test) == "test"
    assert await key_mode(db_session, "nope") is None
    assert await key_mode(db_session, "") is None
    new_live = await issue_key(db_session, "live")
    assert await key_mode(db_session, live) is None
    assert await key_mode(db_session, new_live) == "live"


@pytest.mark.asyncio
async def test_phone_silent_threshold(db_session, monkeypatch):
    import app.services.sms_queue as q

    # no live key, no recipient → never silent
    st = await phone_status(db_session, T0, 60)
    assert st == {"last_poll_at": None, "silent": False, "pending": 0, "failed": 0}

    real_now = q._now
    monkeypatch.setattr(q, "_now", lambda: T0)
    await issue_key(db_session, "live")
    monkeypatch.setattr(q, "_now", real_now)
    assert (await phone_status(db_session, T0 + timedelta(hours=2), 60))["silent"] is False  # no recipient yet

    u = await add_user(db_session, "a")
    # never polled: counted from the key's issue time; threshold max(900, 3 × poll_s)
    assert (await phone_status(db_session, T0 + timedelta(seconds=900), 60))["silent"] is False
    assert (await phone_status(db_session, T0 + timedelta(seconds=901), 60))["silent"] is True
    assert (await phone_status(db_session, T0 + timedelta(seconds=901), 600))["silent"] is False
    assert (await phone_status(db_session, T0 + timedelta(seconds=1801), 600))["silent"] is True

    await touch_poll(db_session, T0 + timedelta(hours=1))
    st = await phone_status(db_session, T0 + timedelta(hours=1, seconds=900), 60)
    assert st["silent"] is False
    assert st["last_poll_at"] == (T0 + timedelta(hours=1)).isoformat()
    assert (await phone_status(db_session, T0 + timedelta(hours=1, seconds=901), 60))["silent"] is True

    # an inactive user or one without a number is not a recipient
    u.is_active = False
    await db_session.commit()
    assert (await phone_status(db_session, T0 + timedelta(hours=5), 60))["silent"] is False


@pytest.mark.asyncio
async def test_phone_status_counts(db_session):
    u = await add_user(db_session, "a")
    await add_item(db_session, "pressure", u, "Низкое давление")
    await add_item(db_session, "rooms", u, "Холодно", ready_at=T0 + timedelta(hours=1))
    await add_item(db_session, "test", u, "Тест", level="INFO", kind="test", is_test=True)
    st = await phone_status(db_session, T0, 60)
    assert st["pending"] == 2 and st["failed"] == 0
    msg = await next_message(db_session, False, T0)
    now = T0
    for _ in range(MAX_ATTEMPTS):
        await mark_done(db_session, msg.id, False, False, "x", now)
        now += timedelta(hours=2)
        await next_message(db_session, False, now)
    st = await phone_status(db_session, now, 60)
    assert st["failed"] == 1


@pytest.mark.asyncio
async def test_notifier_and_queue_do_not_interleave(db_session, engine):
    """Lost-raise race: the phone forms a pending «Снято» while the notifier, which already read the
    subscription, sees the alarm back at the sent level. Serialised by SMS_LOCK, the end state stays consistent."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.services.alarm_rules import Alarm
    from app.services.sms_notifier import SmsNotifier
    from app.services.sms_policy import Cfg

    u = await add_user(db_session, "a", cats="critical")
    sub = await add_sub(db_session, "pressure", u, sent="ERROR", changes=1, episode_start=T0 - timedelta(minutes=20))
    sub.seen = None
    sub.code, sub.last_text = "pressure_low", "Низкое давление"
    await db_session.commit()
    await add_item(db_session, "pressure", u, "Снято: Низкое давление", raised=False, kind="summary")

    phone_session = async_sessionmaker(engine, expire_on_commit=False)()
    phone_task: asyncio.Task | None = None
    real_commit = db_session.commit

    async def commit_after_phone_ran():
        # the notifier's await point after its reads: let the phone's `next` run in between if it can
        nonlocal phone_task
        if phone_task is None:
            phone_task = asyncio.create_task(next_message(phone_session, False, T0))
            await asyncio.wait({phone_task}, timeout=0.5)
        await real_commit()

    db_session.commit = commit_after_phone_ran
    low = Alarm("pressure_low", "ERROR", "Низкое давление отопления: 0.4 бар", 60, group="pressure")
    try:
        await SmsNotifier(started_at=T0 - timedelta(hours=1)).apply(db_session, [low], T0, Cfg(None, None))
    finally:
        db_session.commit = real_commit
    await phone_task
    await phone_session.close()

    pending_items = [i for i in await all_items(db_session) if i.state == "pending"]  # expires the session
    sub = (await db_session.execute(select(SmsSubscription))).scalar_one()
    assert not (sub.seen == "ERROR" and sub.sent is None and not pending_items), (sub.sent, sub.seen)
    assert pending_items or sub.sent == sub.seen


@pytest.mark.asyncio
async def test_queue_waits_for_lock(db_session):
    import asyncio

    from app.services.sms_queue import SMS_LOCK

    u = await add_user(db_session, "a")
    await add_item(db_session, "pressure", u, "Низкое давление")
    async with SMS_LOCK:
        task = asyncio.create_task(next_message(db_session, False, T0))
        done, _ = await asyncio.wait({task}, timeout=0.3)
        assert not done
    assert (await task) is not None
