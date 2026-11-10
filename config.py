"""Loyiha sozlamalari (.env fayldan o‘qiladi)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv o‘rnatilmagan bo‘lsa ham ishlayveradi
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from zoneinfo import ZoneInfo


def _parse_ids(raw: str) -> Tuple[int, ...]:
    ids = []
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            raise SystemExit("ADMIN_IDS noto‘g‘ri qiymat: %r (faqat raqamli Telegram ID)" % part)
    return tuple(ids)


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def _normalize_db_url(url: str) -> str:
    """postgres:// manzillarini asyncpg ga moslaydi; nisbiy SQLite yo‘lini loyiha papkasiga bog‘laydi.

    `sqlite+aiosqlite:///ielts.db` — qaysi papkadan yoki qaysi qurilmada (kompyuter, Termux)
    ishga tushirilsa ham fayl loyiha papkasida bo‘ladi, shuning uchun .env ko‘chirib yuriladi.
    """
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("sqlite") and ":///" in url:
        prefix, path = url.split(":///", 1)
        if path and not path.startswith(":memory:") and not os.path.isabs(path):
            return "%s:///%s" % (prefix, os.path.join(PROJECT_DIR, path).replace("\\", "/"))
    return url


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    admin_ids: Tuple[int, ...]
    timezone: str
    default_report_time: str
    default_countdown_time: str
    log_level: str

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


config = Config(
    bot_token=os.getenv("BOT_TOKEN", "").strip(),
    database_url=_normalize_db_url(
        os.getenv("DATABASE_URL", "postgresql+asyncpg://ielts:ielts@localhost:5432/ielts").strip()
    ),
    admin_ids=_parse_ids(os.getenv("ADMIN_IDS", "")),
    timezone=(os.getenv("TIMEZONE", "") or "Asia/Tashkent").strip(),
    default_report_time=(os.getenv("DEFAULT_REPORT_TIME", "") or "21:00").strip(),
    default_countdown_time=(os.getenv("DEFAULT_COUNTDOWN_TIME", "") or "09:00").strip(),
    log_level=(os.getenv("LOG_LEVEL", "") or "INFO").strip().upper(),
)
