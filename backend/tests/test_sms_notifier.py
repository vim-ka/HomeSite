"""SmsNotifier: per-(problem, recipient) subscriptions and the SMS queue items (DB-backed)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.sms import SmsItem, SmsMessage, SmsSubscription
from app.models.user import User
from app.services.alarm_rules import Alarm
from app.services.sms_notifier import STARTUP_GRACE_S, SmsNotifier
from app.services.sms_policy import Cfg

T0 = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
CFG = Cfg(None, None)
LOW = Alarm("pressure_low", "ERROR", "Низкое давление отопления: 0.4 бар", 60, group="pressure")


def low(value: float = 0.4) -> Alarm:
    return Alarm("pressure_low", "ERROR", f"Низкое давление отопления: {value} бар", 60, group="pressure")


async def add_user(db, name: str, phone: str | None, cats: str) -> User:
    u = User(username=name, password_hash="x", email=f"{name}@x", role="viewer",
             phone=phone, sms_categories=cats)
    db.add(u)
    await db.commit()
    return u


async def items(db) -> list[SmsItem]:
    return list((await db.execute(select(SmsItem).order_by(SmsItem.id))).scalars())


async def pending(db) -> list[SmsItem]:
    return [i for i in await items(db) if i.state == "pending"]


async def form_all(db) -> None:
    """What the queue (Task 5) does when it forms pending items into a message."""
    for it in await pending(db):
        it.state = "formed"
        sub = (await db.execute(select(SmsSubscription).where(
            SmsSubscription.problem == it.problem, SmsSubscription.user_id == it.user_id))).scalar_one()
        sub.sent = it.level if it.raised else None
        sub.changes = 0
    await db.commit()


def notifier() -> SmsNotifier:
    return SmsNotifier(started_at=T0 - timedelta(hours=1))


@pytest.mark.asyncio
async def test_first_raise_creates_item_for_subscribed_only(db_session):
    crit = await add_user(db_session, "a", "+79990000001", "critical")
    await add_user(db_session, "b", "+79990000002", "warning")
    await notifier().apply(db_session, [LOW], T0, CFG)
    got = await items(db_session)
    assert len(got) == 1
    it = got[0]
    assert (it.user_id, it.phone, it.problem, it.code) == (crit.id, "+79990000001", "pressure", "pressure_low")
    assert (it.kind, it.level, it.raised, it.state, it.is_test) == ("first", "ERROR", True, "pending", False)
    assert it.text == LOW.text
    assert it.ready_at.replace(tzinfo=UTC) == T0 + timedelta(seconds=60)


async def _flap(db, n: SmsNotifier, end_raised: bool) -> datetime:
    await n.apply(db, [LOW], T0, CFG)
    await form_all(db)
    t = T0
    for _ in range(5):
        t += timedelta(minutes=1)
        await n.apply(db, [], t, CFG)
        t += timedelta(minutes=1)
        await n.apply(db, [LOW], t, CFG)
    if not end_raised:
        t += timedelta(minutes=1)
        await n.apply(db, [], t, CFG)
    return t


@pytest.mark.asyncio
async def test_flapping_leaves_one_summary(db_session):
    await add_user(db_session, "a", "+79990000001", "critical")
    last = await _flap(db_session, notifier(), end_raised=False)
    p = await pending(db_session)
    assert len(p) == 1
    assert (p[0].kind, p[0].raised, p[0].level) == ("summary", False, "ERROR")
    assert p[0].text.startswith("Снято: Низкое давление отопления")
    assert p[0].ready_at.replace(tzinfo=UTC) == last + timedelta(seconds=600)
    states = [i.state for i in await items(db_session)]
    assert states[0] == "formed"
    assert set(states[1:-1]) <= {"superseded", "not_needed"}


@pytest.mark.asyncio
async def test_flapping_back_to_raised_needs_nothing(db_session):
    await add_user(db_session, "a", "+79990000001", "critical")
    await _flap(db_session, notifier(), end_raised=True)
    assert await pending(db_session) == []


@pytest.mark.asyncio
async def test_value_change_is_not_a_change(db_session):
    await add_user(db_session, "a", "+79990000001", "critical")
    n = notifier()
    await n.apply(db_session, [low(0.4)], T0, CFG)
    await n.apply(db_session, [low(0.3)], T0 + timedelta(seconds=20), CFG)
    got = await items(db_session)
    assert len(got) == 1
    assert got[0].text == "Низкое давление отопления: 0.3 бар"
    assert got[0].ready_at.replace(tzinfo=UTC) == T0 + timedelta(seconds=60)


async def _restored(db) -> User:
    u = await add_user(db, "a", "+79990000001", "critical")
    db.add(SmsSubscription(problem="pressure", user_id=u.id, sent="ERROR", seen="ERROR", changes=0,
                           episode_start=T0 - timedelta(hours=2), last_text=LOW.text, code=LOW.code))
    await db.commit()
    return u


@pytest.mark.asyncio
async def test_restart_sends_nothing(db_session):
    await _restored(db_session)
    n = SmsNotifier(started_at=T0)
    await n.apply(db_session, [], T0, CFG)
    await n.apply(db_session, [LOW], T0 + timedelta(minutes=10), CFG)
    assert await items(db_session) == []


@pytest.mark.asyncio
async def test_vanished_during_downtime_cleared_after_grace(db_session):
    await _restored(db_session)
    n = SmsNotifier(started_at=T0)
    await n.apply(db_session, [], T0, CFG)
    await n.apply(db_session, [], T0 + timedelta(minutes=10), CFG)
    assert await items(db_session) == []
    t = T0 + timedelta(seconds=STARTUP_GRACE_S + 60)
    await n.apply(db_session, [], t, CFG)
    p = await pending(db_session)
    assert len(p) == 1
    assert (p[0].kind, p[0].raised, p[0].code) == ("summary", False, "pressure_low")
    assert p[0].text == f"Снято: {LOW.text}"
    assert p[0].ready_at.replace(tzinfo=UTC) == t + timedelta(seconds=600)


@pytest.mark.asyncio
async def test_recipient_changes_mid_episode(db_session):
    u = await add_user(db_session, "a", "+79990000001", "critical")
    n = notifier()
    await n.apply(db_session, [LOW], T0, CFG)
    u.phone = "+79990000009"
    await db_session.commit()
    await n.apply(db_session, [LOW], T0 + timedelta(seconds=20), CFG)
    p = await pending(db_session)
    assert len(p) == 1 and p[0].phone == "+79990000009"
    u.sms_categories = "warning"
    await db_session.commit()
    await n.apply(db_session, [LOW], T0 + timedelta(seconds=40), CFG)
    got = await items(db_session)
    assert [i.state for i in got] == ["not_needed"]


@pytest.mark.asyncio
async def test_phone_removed_mid_episode(db_session):
    u = await add_user(db_session, "a", "+79990000001", "critical")
    n = notifier()
    await n.apply(db_session, [LOW], T0, CFG)
    u.phone = None
    await db_session.commit()
    await n.apply(db_session, [LOW], T0 + timedelta(seconds=20), CFG)
    assert [i.state for i in await items(db_session)] == ["not_needed"]
    # number back while the alarm is still on: nothing was sent, so it is a first SMS again
    u.phone = "+79990000001"
    await db_session.commit()
    await n.apply(db_session, [LOW], T0 + timedelta(seconds=40), CFG)
    assert len(await pending(db_session)) == 1


@pytest.mark.asyncio
async def test_cleanup_removes_older_than_90_days(db_session):
    old, new = T0 - timedelta(days=91), T0 - timedelta(days=89)
    for ts in (old, new):
        msg = SmsMessage(phone="+79990000001", text="x", is_test=False, state="sent", items=1, attempts=0,
                         created_at=ts, ready_at=ts)
        db_session.add(msg)
        await db_session.flush()
        db_session.add(SmsItem(problem="pressure", code="pressure_low", level="ERROR", raised=True, kind="first",
                               user_id=None, phone="+79990000001", text="x", is_test=False, state="formed",
                               message_id=msg.id, created_at=ts, ready_at=ts))
    await db_session.commit()
    await notifier().cleanup(db_session, T0)
    left_items = await items(db_session)
    left_msgs = list((await db_session.execute(select(SmsMessage))).scalars())
    assert [i.created_at.replace(tzinfo=UTC) for i in left_items] == [new]
    assert [m.created_at.replace(tzinfo=UTC) for m in left_msgs] == [new]
