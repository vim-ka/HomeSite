"""SMS text helpers: categories and phone number normalisation."""

import re
from dataclasses import dataclass
from datetime import datetime

from app.services.alarm_rules import Alarm

SMS_CATEGORIES = ("critical", "warning", "link", "internet", "test")


def normalize_phone(raw: str) -> str:
    """Return the number as +7XXXXXXXXXX; 8XXXXXXXXXX and 7XXXXXXXXXX are accepted. ValueError on garbage."""
    s = raw.strip()
    if not re.fullmatch(r"\+?[\d\s()\-]+", s):
        raise ValueError(f"Неверный номер телефона: {raw!r}")
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    raise ValueError(f"Неверный номер телефона: {raw!r}")


SMS_LIMIT = 134
_SEP = "; "
_LEVEL_ORDER = {"ERROR": 0, "WARNING": 1}


@dataclass
class Part:
    problem: str
    level: str
    raised: bool
    text: str


def raised_text(a: Alarm) -> str:
    return a.text


def _minutes(start: datetime, now: datetime) -> int:
    return max(0, int((now - start).total_seconds() // 60))


def summary_text(code: str, a: Alarm | None, last_text: str, changes: int,
                 episode_start: datetime, now: datetime) -> str:
    """Text for a problem summarised after a debounce: cleared (a is None) or still active."""
    minutes = _minutes(episode_start, now)
    if a is None:
        text = f"Интернет есть, не было {minutes} мин" if code == "internet_down" else f"Снято: {last_text}"
    else:
        text = a.text
    if changes > 1:
        text += f" (за {minutes} мин {changes} раз туда-обратно)"
    return text


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(limit - 1, 0)] + "…"


def merge(parts: list[Part], limit: int = SMS_LIMIT) -> tuple[str, list[Part]]:
    """One SMS text from the parts; returns (text, all deduplicated parts in sorted order).

    Parts that do not fit are summarised as «…и ещё N, подробнее на сайте» and still count as reported."""
    ordered = sorted(parts, key=lambda p: (_LEVEL_ORDER.get(p.level, 2), 0 if p.raised else 1))
    # one raise and one clear per problem: a short ERROR's first SMS and its «Снято» may be formed together
    seen: set[tuple[str, bool]] = set()
    uniq: list[Part] = []
    for p in ordered:
        if (p.problem, p.raised) not in seen:
            seen.add((p.problem, p.raised))
            uniq.append(p)
    if not uniq:
        return "", []
    full = _SEP.join(p.text for p in uniq)
    if len(full) <= limit:
        return full, uniq
    if len(uniq) == 1:
        return _truncate(full, limit), uniq
    for k in range(len(uniq) - 1, 0, -1):
        text = _SEP.join(p.text for p in uniq[:k]) + _SEP + f"…и ещё {len(uniq) - k}, подробнее на сайте"
        if len(text) <= limit:
            return text, uniq
    tail = f"…и ещё {len(uniq) - 1}, подробнее на сайте"
    return _truncate(uniq[0].text, limit - len(_SEP) - len(tail)) + _SEP + tail, uniq
