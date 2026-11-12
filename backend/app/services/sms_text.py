"""SMS text helpers: categories and phone number normalisation."""

import re

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
