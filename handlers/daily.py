"""Daily IELTS Report menyusi."""
from __future__ import annotations

from typing import Dict, List, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Result
from database.repository import SKILLS, get_goals, get_settings, results_between
from handlers.common import Target, render
from keyboards.skills import SKILL_NAMES, daily_report_kb
from services.band_calculator import fmt_band
from services.channel import result_score
from services.planner import compute_progress, format_progress
from services.streak import get_streak
from utils import dates

router = Router(name="daily")


async def build_daily_report(session: AsyncSession) -> Tuple[str, InlineKeyboardMarkup]:
    settings = await get_settings(session)
    today = dates.today()
    results = await results_between(session, today, today)

    by_skill: Dict[str, List[Result]] = {skill: [] for skill in SKILLS}
    for result in results:
        by_skill[result.skill].append(result)

    lines = [
        "📚 <b>IELTS DAILY REPORT</b>",
        "Bugungi tayyorgarligingizni qayd eting.",
        "",
        "📅 %s" % dates.fmt_long(today),
    ]
    if results:
        lines += ["", "<b>Bugun kiritilgan:</b>"]
        for skill in SKILLS:
            items = by_skill[skill]
            if items:
                last = items[-1]
                lines.append(
                    "%s — %d ta (oxirgi: %s, band %s)"
                    % (SKILL_NAMES[skill], len(items), result_score(last), fmt_band(last.band))
                )

    progress = compute_progress(get_goals(settings), results)
    if progress.items:
        lines += ["", "🎯 <b>Bugungi maqsad</b>"] + format_progress(progress)

    streak = await get_streak(session, today)
    lines += ["", "🔥 Streak: <b>%d kun</b>%s" % (streak.current, "" if streak.today_done else " (bugun hali hisobot yo‘q)")]
    if settings.exam_date and settings.exam_date >= today:
        lines.append("⏳ Imtihongacha: <b>%d kun</b>" % dates.days_left(settings.exam_date, today))
    return "\n".join(lines), daily_report_kb()


async def show_daily_report(target: Target, session: AsyncSession) -> None:
    text, keyboard = await build_daily_report(session)
    await render(target, text, keyboard)


@router.callback_query(F.data == "daily:open")
async def daily_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await callback.answer()
    text, keyboard = await build_daily_report(session)
    await callback.bot.send_message(callback.from_user.id, text, reply_markup=keyboard)
