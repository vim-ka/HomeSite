"""Per-problem SMS policy: pure rules (no DB, no I/O). All datetimes are UTC-aware."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from typing import Literal

from app.services.alarm_rules import LEVEL_RANK, Alarm

BANNER_ONLY = {"alarm_check_failed", "lan_down", "sms_phone_silent", "sms_failed"}


def problem_key(a: Alarm) -> str:
    return a.group or a.code


def category(a: Alarm) -> str:
    if a.group == "link":
        return "link"
    if a.code == "internet_down":
        return "internet"
    if a.level == "ERROR":
        return "critical"
    if a.level == "WARNING":
        return "warning"
    return ""


def current_problems(active: Iterable[Alarm]) -> dict[str, Alarm]:
    out: dict[str, Alarm] = {}
    for a in active:
        if a.code in BANNER_ONLY or a.level == "INFO":
            continue
        k = problem_key(a)
        if k not in out or LEVEL_RANK.get(a.level, 0) > LEVEL_RANK.get(out[k].level, 0):
            out[k] = a
    return out


def effective_level(a: Alarm | None, categories: set[str]) -> str | None:
    if a is None or category(a) not in categories:
        return None
    return a.level


@dataclass
class Cfg:
    quiet_start: time | None
    quiet_end: time | None
    merge_s: int = 60
    settle_s: int = 600


def _has_quiet(cfg: Cfg) -> bool:
    return cfg.quiet_start is not None and cfg.quiet_end is not None and cfg.quiet_start != cfg.quiet_end


def in_quiet(now: datetime, cfg: Cfg) -> bool:
    if not _has_quiet(cfg):
        return False
    t, s, e = now.timetz().replace(tzinfo=None), cfg.quiet_start, cfg.quiet_end
    return s <= t < e if s < e else (t >= s or t < e)


def quiet_end_after(now: datetime, cfg: Cfg) -> datetime:
    """Next moment at/after `now` when the quiet window ends (`now` itself if there is no window)."""
    if not _has_quiet(cfg):
        return now
    end = now.replace(hour=cfg.quiet_end.hour, minute=cfg.quiet_end.minute,
                      second=cfg.quiet_end.second, microsecond=0)
    return end if end >= now else end + timedelta(days=1)


@dataclass
class Sub:
    sent: str | None
    seen: str | None
    changes: int
    episode_start: datetime | None


@dataclass
class Decision:
    kind: Literal["none", "first", "summary", "drop"]
    ready_at: datetime | None
    sub: Sub


def _rank(level: str | None) -> int:
    return LEVEL_RANK.get(level, 0) if level else -1


def decide(sub: Sub, eff: str | None, now: datetime, cfg: Cfg) -> Decision:
    if eff == sub.seen:
        return Decision("none", None, sub)
    if eff is not None and (sub.sent is None or _rank(eff) > _rank(sub.sent)):
        fresh = sub.sent is None and sub.seen is None
        new = replace(sub, seen=eff, changes=0, episode_start=now if fresh else (sub.episode_start or now))
        ready, quiet_level, kind = now + timedelta(seconds=cfg.merge_s), eff, "first"
    elif eff == sub.sent:
        if eff is None and sub.sent is None:   # episode ended with nothing to send
            return Decision("drop", None, Sub(None, None, 0, None))
        return Decision("drop", None, replace(sub, seen=eff, changes=sub.changes + 1))
    else:
        new = replace(sub, seen=eff, changes=sub.changes + 1)
        ready, quiet_level, kind = now + timedelta(seconds=cfg.settle_s), sub.sent, "summary"
    if quiet_level == "WARNING" and in_quiet(ready, cfg):
        ready = quiet_end_after(ready, cfg)
    return Decision(kind, ready, new)
