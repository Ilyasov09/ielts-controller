"""Haftalik kanal hisoboti: matn + progress grafigi."""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional, Tuple

from aiogram import Bot
from aiogram.types import BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import SKILLS
from services.band_calculator import fmt_band
from services.channel import SKILL_INFO
from services.charts import build_progress_chart
from services.statistics import _delta, period_stats, previous_period
from services.streak import get_streak
from utils import dates

CAPTION_LIMIT = 1024
log = logging.getLogger(__name__)


def _hm(total: int) -> str:
    hours, minutes = divmod(int(total), 60)
    if hours and minutes:
        return "%dh %dm" % (hours, minutes)
    return "%dh" % hours if hours else "%dm" % minutes


def _span(start: dt.date, end: dt.date) -> str:
    left = "%02d %s" % (start.day, dates.MONTHS_EN[start.month - 1][:3])
    if start.year != end.year:
        left += " %d" % start.year
    return "%s — %02d %s %d" % (left, end.day, dates.MONTHS_EN[end.month - 1][:3], end.year)


async def build_weekly(session: AsyncSession, end: dt.date) -> Optional[Tuple[str, Optional[bytes]]]:
    """Hafta (end dan oldingi 7 kun) uchun post. Natija bo‘lmasa — None."""
    start = end - dt.timedelta(days=6)
    cur = await period_stats(session, start, end)
    if not cur.results:
        return None
    prev = await period_stats(session, *previous_period(start, end))
    streak = await get_streak(session, end)

    lines = [
        "📊 <b>WEEKLY IELTS REPORT</b>",
        "📅 %s" % _span(start, end),
        "",
        "📝 Mocks: <b>%d</b>%s" % (cur.total_mocks, _delta(float(cur.total_mocks), float(prev.total_mocks), "%.0f")),
        "⏱ Study time: <b>%s</b>" % _hm(cur.total_minutes),
        "📆 Active days: <b>%d / 7</b>" % cur.active_days,
        "🔥 Streak: <b>%d %s</b>" % (streak.current, "day" if streak.current == 1 else "days"),
        "",
    ]
    for skill in SKILLS:
        stats = cur.skills[skill]
        if not stats.count:
            continue
        emoji, _upper, name = SKILL_INFO[skill]
        line = "%s %s — %d · avg <b>%s</b>%s" % (
            emoji, name, stats.count, fmt_band(stats.avg_band),
            _delta(stats.avg_band, prev.skills[skill].avg_band),
        )
        if stats.count > 1:
            line += " · best %s" % fmt_band(stats.best_band)
        lines.append(line)
    if cur.overall_estimate is not None:
        lines += ["", "📈 Estimated overall: <b>%s</b>" % fmt_band(cur.overall_estimate)]
    lines += ["", "#IELTS #WeeklyReport"]

    try:
        chart = build_progress_chart(cur.results, start, end, title="Weekly progress")
    except ImportError:
        chart = None  # matplotlib yo‘q — post grafiksiz chiqadi
    except Exception:
        log.exception("Haftalik grafik chizilmadi")
        chart = None
    return "\n".join(lines), chart


async def send_weekly(bot: Bot, chat_id: int, caption: str, chart: Optional[bytes]) -> int:
    if chart is None:
        return (await bot.send_message(chat_id, caption)).message_id
    photo = BufferedInputFile(chart, filename="weekly_report.png")
    if len(caption) <= CAPTION_LIMIT:
        return (await bot.send_photo(chat_id, photo, caption=caption)).message_id
    await bot.send_photo(chat_id, photo)
    return (await bot.send_message(chat_id, caption)).message_id
