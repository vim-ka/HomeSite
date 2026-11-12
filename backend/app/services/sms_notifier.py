"""SmsNotifier: turns the active alarms into SMS queue items, one (problem, recipient) pair at a time.

The per-pair rules are in `sms_policy.decide`; this class keeps their state in `sms_subscription` (so a backend
restart does not re-send), writes `sms_item` rows and keeps the still-pending ones current. Forming items into
messages and marking them sent is the queue's job (`sms_queue`)."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sms import SmsItem, SmsMessage, SmsSubscription
from app.models.user import User
from app.services.alarm_rules import LEVEL_RANK, Alarm
from app.services.sms_queue import SMS_LOCK
from app.services.sms_policy import Cfg, Sub, category, current_problems, decide, effective_level
from app.services.sms_text import raised_text, summary_text

STARTUP_GRACE_S = 900      # after a restart the tracker is empty until the raise delays pass: no lowering yet
RETENTION_DAYS = 90


def _utc(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def _rank(level: str | None) -> int:
    return LEVEL_RANK.get(level, 0) if level else -1


def _categories(u: User) -> set[str]:
    return {c.strip() for c in (u.sms_categories or "").split(",") if c.strip()}


def _alarm_categories(u: User) -> set[str] | None:
    """Alarm categories of a recipient, None if the user gets no alarm SMS (inactive, no number, only tests)."""
    cats = _categories(u) - {"test"}
    return cats if u.is_active and u.phone and cats else None


def _category_of(problem: str, code: str, level: str) -> str:
    return category(Alarm(code, level, "", group=problem if problem != code else None))


def _item_category(it: SmsItem) -> str:
    return _category_of(it.problem, it.code, it.level)


def _told_category(row: SmsSubscription) -> str | None:
    """Category of the alarm this pair's episode is about (last one the user saw), None if there is no episode.

    Judged by the alarm the user was told about, not the current one: an ERROR lowered to WARNING for a
    critical-only user is still their episode and ends with «Снято»."""
    level = row.seen or row.sent
    return _category_of(row.problem, row.code, level) if level else None


class SmsNotifier:
    def __init__(self, started_at: datetime) -> None:
        self.started_at = started_at

    async def apply(self, session: AsyncSession, active: Iterable[Alarm], now: datetime, cfg: Cfg) -> None:
        async with SMS_LOCK:      # the phone API forms items and updates subscriptions in another session
            await self._apply(session, active, now, cfg)

    async def _apply(self, session: AsyncSession, active: Iterable[Alarm], now: datetime, cfg: Cfg) -> None:
        problems = current_problems(active)
        users = {u.id: u for u in (await session.execute(select(User))).scalars()}
        recipients = {uid: cats for uid, u in users.items() if (cats := _alarm_categories(u)) is not None}
        subs = {(s.problem, s.user_id): s for s in (await session.execute(select(SmsSubscription))).scalars()}
        waiting: dict[tuple[str, int | None], list[SmsItem]] = {}
        for it in (await session.execute(select(SmsItem).where(
                SmsItem.state == "pending", SmsItem.is_test.is_(False)))).scalars():
            waiting.setdefault((it.problem, it.user_id), []).append(it)

        pairs = {(p, uid) for p in problems for uid in recipients}
        pairs |= {k for k, s in subs.items() if s.sent is not None or s.seen is not None}
        in_grace = now < self.started_at + timedelta(seconds=STARTUP_GRACE_S)

        for problem, uid in sorted(pairs):
            if uid not in users:
                continue
            a = problems.get(problem)
            cats = recipients.get(uid)
            row = subs.get((problem, uid))
            told = _told_category(row) if row is not None else None
            if told is not None and (cats is None or told not in cats):
                # the user stopped getting this kind of SMS (number, activity or category changed): forget the
                # episode, so the next raise is a fresh first SMS and no «Снято» comes for it later
                row.sent, row.seen, row.changes, row.episode_start = None, None, 0, None
                for it in waiting.pop((problem, uid), []):
                    it.state = "not_needed"
                continue
            if cats is None:
                continue
            eff = effective_level(a, cats)
            sub = Sub(row.sent, row.seen, row.changes, _utc(row.episode_start)) if row else Sub(None, None, 0, None)
            if in_grace and _rank(eff) < _rank(sub.seen):
                continue
            d = decide(sub, eff, now, cfg)
            if d.kind != "none" and row is None:
                row = SmsSubscription(problem=problem, user_id=uid, changes=0, last_text="", code="")
                session.add(row)
                subs[(problem, uid)] = row
            if row is not None and a is not None and eff is not None:
                row.last_text, row.code = raised_text(a), a.code
            if d.kind == "none":
                continue
            for it in waiting.pop((problem, uid), []):
                it.state = "not_needed" if d.kind == "drop" else "superseded"
            row.sent, row.seen, row.changes, row.episode_start = (
                d.sub.sent, d.sub.seen, d.sub.changes, d.sub.episode_start)
            if d.kind == "drop":
                continue
            if d.kind == "first":
                code, level, raised, text = a.code, eff, True, raised_text(a)
            else:
                start = d.sub.episode_start or now
                if eff is None:
                    code, level, raised = row.code, d.sub.sent, False
                    text = summary_text(row.code, None, row.last_text, d.sub.changes, start, now)
                else:
                    code, level, raised = a.code, eff, True
                    text = summary_text(a.code, a, row.last_text, d.sub.changes, start, now)
            item = SmsItem(problem=problem, code=code, level=level, raised=raised, kind=d.kind, user_id=uid,
                           phone=users[uid].phone, text=text, is_test=False, state="pending",
                           created_at=now, ready_at=d.ready_at)
            session.add(item)
            waiting[(problem, uid)] = [item]

        # still-pending items: current number and text; the recipient may have dropped the category or number
        for (problem, uid), its in waiting.items():
            cats = recipients.get(uid)
            a = problems.get(problem)
            row = subs.get((problem, uid))
            for it in its:
                if cats is None or _item_category(it) not in cats:
                    it.state = "not_needed"
                    continue
                it.phone = users[uid].phone
                if it.raised and a is not None and a.level == it.level:
                    if it.kind == "first" or row is None:
                        it.text = raised_text(a)
                    else:
                        it.text = summary_text(a.code, a, row.last_text, row.changes,
                                               _utc(row.episode_start) or now, now)
        await session.commit()

    async def cleanup(self, session: AsyncSession, now: datetime) -> None:
        """Delete queue items and messages older than RETENTION_DAYS (items first: they point at messages)."""
        cutoff = now - timedelta(days=RETENTION_DAYS)
        async with SMS_LOCK:
            await session.execute(delete(SmsItem).where(SmsItem.created_at < cutoff))
            await session.execute(delete(SmsMessage).where(SmsMessage.created_at < cutoff))
            await session.commit()
