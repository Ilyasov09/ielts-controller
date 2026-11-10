"""Foydalanuvchi kiritgan qiymatlarni tekshirish."""
from __future__ import annotations

import re
from typing import Optional, Union

_INT_RE = re.compile(r"^\s*(\d{1,6})\s*$")
_HM_RE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")
_HOURS_MIN_RE = re.compile(
    r"^\s*(?:(\d{1,2})\s*(?:h|soat|s)\s*)?(?:(\d{1,3})\s*(?:m|min|daq|daqiqa)?\s*)?$",
    re.IGNORECASE,
)
_LINK_RE = re.compile(r"^\s*(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{3,})/?\s*$")
_USERNAME_RE = re.compile(r"^\s*@([A-Za-z][A-Za-z0-9_]{3,})\s*$")
_CHANNEL_ID_RE = re.compile(r"^\s*(-100\d{5,})\s*$")


def parse_int(text: Optional[str], low: int, high: int) -> Optional[int]:
    match = _INT_RE.match(text or "")
    if not match:
        return None
    value = int(match.group(1))
    if value < low or value > high:
        return None
    return value


def parse_band(text: Optional[str]) -> Optional[float]:
    """0–9 oralig‘idagi, 0.5 qadamli IELTS bandini o‘qiydi (6,5 ham qabul qilinadi)."""
    raw = (text or "").strip().replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    if not (0 <= value <= 9):
        return None
    if not (value * 2).is_integer():
        return None
    return value


def parse_minutes(text: Optional[str], high: int = 720) -> Optional[int]:
    """'45', '1:30', '1h 30m', '2 soat' kabi yozuvlarni daqiqaga aylantiradi."""
    raw = (text or "").strip()
    if not raw:
        return None
    match = _HM_RE.match(raw)
    if match:
        total = int(match.group(1)) * 60 + int(match.group(2))
    else:
        match = _HOURS_MIN_RE.match(raw)
        if not match or not (match.group(1) or match.group(2)):
            return None
        total = int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
    if total < 1 or total > high:
        return None
    return total


def parse_channel_ref(text: Optional[str]) -> Optional[Union[int, str]]:
    """@username, t.me/username yoki -100... ko‘rinishidagi kanal identifikatori."""
    raw = text or ""
    for regex in (_USERNAME_RE, _LINK_RE):
        match = regex.match(raw)
        if match:
            return "@" + match.group(1)
    match = _CHANNEL_ID_RE.match(raw)
    if match:
        return int(match.group(1))
    return None


def clean_text(text: Optional[str], limit: int) -> str:
    value = " ".join((text or "").split())
    if len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return value
