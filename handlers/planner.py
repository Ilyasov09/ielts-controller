"""🎯 Study Planner — kunlik maqsadlar."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import get_goals, get_settings, results_between
from handlers.common import Target, render, reply_target
from handlers.states import PlannerForm
from keyboards.admin import planner_kb
from keyboards.main import cancel_ikb
from services.planner import GOAL_FIELDS, GOAL_LABELS, compute_progress, format_progress, progress_bar
from utils import dates
from utils.validators import parse_int

router = Router(name="planner")

LIMITS = {"minutes": 1440}
DEFAULT_LIMIT = 20


async def show_planner(target: Target, session: AsyncSession) -> None:
    settings = await get_settings(session)
    goals = get_goals(settings)
    today = dates.today()
    progress = compute_progress(goals, await results_between(session, today, today))
    lines = ["🎯 <b>STUDY PLANNER — Kunlik maqsad</b>", "📅 %s" % dates.fmt_long(today), ""]
    if progress.items:
        lines += format_progress(progress)
        lines.append(progress_bar(progress.percent))
    else:
        lines.append("Hali maqsad belgilanmagan.")
    lines += ["", "<i>Har bir skill uchun kuniga nechta mock va jami necha daqiqa shug‘ullanishni belgilang. "
                  "0 — maqsad yo‘q.</i>"]
    await render(target, "\n".join(lines), planner_kb(goals))


@router.callback_query(F.data == "pl:open")
async def planner_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_planner(callback, session)


@router.callback_query(F.data.startswith("pl:set:"))
async def planner_set(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.rsplit(":", 1)[1]
    if key not in GOAL_FIELDS:
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(PlannerForm.value)
    await state.update_data(goal_key=key)
    limit = LIMITS.get(key, DEFAULT_LIMIT)
    unit = "daqiqa" if key == "minutes" else "ta mock"
    await reply_target(callback).answer(
        "%s uchun kunlik maqsadni yozing (0–%d %s):" % (GOAL_LABELS[key], limit, unit),
        reply_markup=cancel_ikb(),
    )


@router.message(PlannerForm.value)
async def planner_value(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    key = data.get("goal_key")
    if key not in GOAL_FIELDS:
        await state.clear()
        return
    value = parse_int(message.text, 0, LIMITS.get(key, DEFAULT_LIMIT))
    if value is None:
        await message.answer("❗ 0 dan %d gacha butun son kiriting." % LIMITS.get(key, DEFAULT_LIMIT))
        return
    settings = await get_settings(session)
    setattr(settings, GOAL_FIELDS[key], value)
    await session.commit()
    await state.clear()
    await message.answer("✅ %s: <b>%d</b>" % (GOAL_LABELS[key], value))
    await show_planner(message, session)
