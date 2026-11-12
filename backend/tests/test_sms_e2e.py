"""End to end: SmsNotifier.apply → next_message → mark_done over two internet outages, 30-s polls."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.sms import SmsSubscription
from app.models.user import User
from app.services import sms_queue
from app.services.alarm_rules import Alarm
from app.services.sms_notifier import SmsNotifier
from app.services.sms_policy import Cfg

T0 = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
CFG = Cfg(None, None)
NET = Alarm("internet_down", "ERROR", "Нет интернета", 300)


@pytest.mark.asyncio
async def test_two_internet_outages_give_three_sms(db_session):
    db = db_session
    db.add(User(username="u", password_hash="x", email="u@x", role="viewer", phone="+79001234567",
                sms_categories="internet"))
    await db.commit()
    n = SmsNotifier(started_at=T0 - timedelta(hours=1))
    sent: list[tuple[int, str]] = []

    async def poll(i: int, active: list[Alarm]) -> None:
        t = T0 + timedelta(seconds=30 * i)
        await n.apply(db, active, t, CFG)
        m = await sms_queue.next_message(db, False, t)
        if m:
            sent.append((i, m.text))
            assert await sms_queue.mark_done(db, m.id, False, True, None, t)

    for i in range(120):            # first outage: polls 2..79 (39 min)
        await poll(i, [NET] if 2 <= i < 80 else [])
    for i in range(120, 200):       # second outage from poll 150 on
        await poll(i, [NET] if i >= 150 else [])

    assert [text for _, text in sent] == ["Нет интернета", "Интернет есть, не было 44 мин", "Нет интернета"]
    first, clear, again = (i for i, _ in sent)
    assert first == 4                         # after the 60-s merge window
    assert clear == 100                       # cleared at poll 80 + 10 min settle
    assert again == 152
    sub = (await db.execute(select(SmsSubscription))).scalar_one()
    assert (sub.sent, sub.seen) == ("ERROR", "ERROR")
