"""Sana va vaqt bilan ishlash yordamchilari."""
from __future__ import annotations

import datetime as dt
import re
from typing import Iterator, Optional, Tuple

from config import config

TZ = config.tz

MONTHS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
WEEKDAYS_UZ = ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba")
WEEKDAYS_SHORT = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")

_DATE_RE = re.compile(r"^\s*(\d{1,2})[./\-\s](\d{1,2})[./\-\s](\d{4})\s*$")
_TIME_RE = re.compile(r"^\s*(\d{1,2})[:.\s](\d{2})\s*$")


def now_local() -> dt.datetime:
    return dt.datetime.now(TZ)


def today() -> dt.date:
    return now_local().date()


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def to_local(value: dt.datetime) -> dt.datetime:
    """Bazadan kelgan vaqtni mahalliy vaqtga o‘tkazadi (naive bo‘lsa UTC deb olinadi)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(TZ)


def fmt_long(day: dt.date) -> str:
    """09 November 2026"""
    return "%02d %s %d" % (day.day, MONTHS_EN[day.month - 1], day.year)


def fmt_short(day: dt.date) -> str:
    """09.11.2026"""
    return "%02d.%02d.%04d" % (day.day, day.month, day.year)


def fmt_compact(day: dt.date) -> str:
    """20261109 — callback_data uchun."""
    return "%04d%02d%02d" % (day.year, day.month, day.day)


def parse_compact(value: str) -> Optional[dt.date]:
    try:
        return dt.datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def parse_date(text: str) -> Optional[dt.date]:
    """DD.MM.YYYY (shuningdek DD/MM/YYYY, DD-MM-YYYY) formatini o‘qiydi."""
    match = _DATE_RE.match(text or "")
    if not match:
        return None
    day, month, year = (int(x) for x in match.groups())
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def parse_time(text: str) -> Optional[str]:
    """HH:MM formatini o‘qiydi va normallashtirilgan 'HH:MM' qaytaradi."""
    match = _TIME_RE.match(text or "")
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return "%02d:%02d" % (hour, minute)


def split_time(value: str) -> Tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def iter_days(start: dt.date, end: dt.date) -> Iterator[dt.date]:
    day = start
    one = dt.timedelta(days=1)
    while day <= end:
        yield day
        day += one


def fmt_minutes(total: Optional[int]) -> str:
    total = int(total or 0)
    hours, minutes = divmod(total, 60)
    if hours and minutes:
        return "%d soat %d daqiqa" % (hours, minutes)
    if hours:
        return "%d soat" % hours
    return "%d daqiqa" % minutes


def days_left(exam_date: dt.date, day: Optional[dt.date] = None) -> int:
    return (exam_date - (day or today())).days
