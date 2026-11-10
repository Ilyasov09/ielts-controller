"""Barcha skill hisobotlari uchun umumiy qadamlar: vaqt, rasm, saqlash va kanalga post."""
from __future__ import annotations

import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Result
from database.repository import (
    SKILLS,
    active_dates,
    count_skill_on,
    get_goals,
    get_rest_weekdays,
    get_settings,
    rest_dates,
    results_between,
)
from handlers.common import drop_keyboard, reply_target
from handlers.states import ReportFlow
from keyboards.main import cancel_ikb
from keyboards.skills import SKILL_NAMES, after_result_kb, minutes_kb, photo_kb
from services.band_calculator import calculate_band, fmt_band, is_estimated
from services.channel import publish_result, result_score, result_subtype
from services.planner import compute_progress
from services.streak import MILESTONES, compute_streak
from utils import dates
from utils.validators import parse_int, parse_minutes

log = logging.getLogger(__name__)
router = Router(name="report_flow")


# ---------------------------------------------------------------- savollar / to‘g‘ri javoblar
async def ask_total(message: Message, state: FSMContext, total_state: State, step: int) -> None:
    from keyboards.skills import total_kb

    await state.set_state(total_state)
    await state.update_data(step=step)
    await message.answer("<b>%d-qadam</b>\nNechta savol ishladingiz?" % step, reply_markup=total_kb())


async def accept_total(message: Message, state: FSMContext, raw: str, correct_state: State) -> None:
    total = parse_int(raw, 1, 200)
    if total is None:
        await message.answer("❗ 1 dan 200 gacha butun son kiriting. Masalan: <b>40</b>")
        return
    data = await state.get_data()
    step = int(data.get("step", 1)) + 1
    await state.update_data(total=total, step=step)
    await state.set_state(correct_state)
    await message.answer(
        "<b>%d-qadam</b>\nNechtasiga to‘g‘ri javob berdingiz? (0–%d)" % (step, total),
        reply_markup=cancel_ikb(),
    )


async def accept_correct(message: Message, state: FSMContext, raw: str) -> None:
    data = await state.get_data()
    total = int(data["total"])
    correct = parse_int(raw, 0, total)
    if correct is None:
        await message.answer("❗ 0 dan %d gacha butun son kiriting." % total)
        return
    await state.update_data(correct=correct)
    await ask_minutes(message, state, int(data.get("step", 2)) + 1)


# ---------------------------------------------------------------- vaqt
async def ask_minutes(message: Message, state: FSMContext, step: int) -> None:
    await state.set_state(ReportFlow.minutes)
    await state.update_data(step=step)
    await message.answer(
        "<b>%d-qadam</b>\n⏱ Bu mashg‘ulotga necha daqiqa sarfladingiz?\n"
        "<i>Tugmani bosing yoki yozing: 45, 1:20, 2 soat</i>" % step,
        reply_markup=minutes_kb(),
    )


@router.callback_query(ReportFlow.minutes, F.data.startswith("min:"))
async def minutes_callback(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]
    minutes = None if value == "skip" else int(value)
    await callback.answer()
    await drop_keyboard(callback)
    await _after_minutes(reply_target(callback), state, minutes)


@router.message(ReportFlow.minutes)
async def minutes_message(message: Message, state: FSMContext) -> None:
    minutes = parse_minutes(message.text)
    if minutes is None:
        await message.answer("❗ Daqiqani raqam bilan yozing (1–720). Masalan: <b>40</b> yoki <b>1:30</b>")
        return
    await _after_minutes(message, state, minutes)


async def _after_minutes(message: Message, state: FSMContext, minutes) -> None:
    data = await state.get_data()
    step = int(data.get("step", 3)) + 1
    await state.update_data(minutes=minutes, step=step)
    await state.set_state(ReportFlow.photo)
    await message.answer(
        "<b>%d-qadam</b>\n📸 Natijaga rasm biriktirmoqchimisiz?\n\n"
        "Rasm yuboring yoki «O‘tkazib yuborish» ni bosing." % step,
        reply_markup=photo_kb(),
    )


# ---------------------------------------------------------------- rasm
@router.callback_query(ReportFlow.photo, F.data == "photo:skip")
async def photo_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await callback.answer()
    await drop_keyboard(callback)
    await finalize_report(reply_target(callback), state, session, bot)


@router.message(ReportFlow.photo, F.photo)
async def photo_received(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await finalize_report(message, state, session, bot)


@router.message(ReportFlow.photo)
async def photo_invalid(message: Message) -> None:
    await message.answer(
        "❗ Iltimos, rasmni <b>photo</b> sifatida yuboring (fayl/hujjat emas) "
        "yoki «O‘tkazib yuborish» ni bosing.",
        reply_markup=photo_kb(),
    )


# ---------------------------------------------------------------- yakunlash
async def finalize_report(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    skill = data.get("skill")
    if skill not in SKILLS:
        await message.answer("⚠️ Sessiya eskirgan. Daily Report menyusidan qaytadan boshlang.")
        return

    today = dates.today()
    previous_active = await active_dates(session)

    reading_type = data.get("reading_type") if skill == "reading" else None
    if skill in ("listening", "reading"):
        total, correct = int(data["total"]), int(data["correct"])
        band = calculate_band(skill, correct, total, reading_type)
    else:
        total = correct = None
        band = float(data["band"])

    result = Result(
        skill=skill,
        local_date=today,
        created_at=dates.utcnow(),
        reading_type=reading_type,
        total=total,
        correct=correct,
        band=band,
        task=data.get("task"),
        topic=data.get("topic"),
        minutes=data.get("minutes"),
        photo_file_id=data.get("photo_file_id"),
    )
    session.add(result)
    await session.commit()

    settings = await get_settings(session)
    if settings.channel_id:
        try:
            result.channel_message_id = await publish_result(bot, settings.channel_id, result)
            result.channel_id = settings.channel_id
            await session.commit()
            post_status = "📢 Kanalga yuborildi."
        except TelegramAPIError as exc:
            log.warning("Natija kanalga yuborilmadi: %s", exc)
            post_status = "⚠️ Kanalga yuborilmadi: %s\nNatija bazada saqlandi." % html.escape(str(exc))
    else:
        post_status = "⚠️ Kanal ulanmagan — natija faqat bazada saqlandi (⚙️ Settings → Kanal)."

    attempt = await count_skill_on(session, skill, today)
    rest = await rest_dates(session)
    weekdays = get_rest_weekdays(settings)
    streak = compute_streak(previous_active | {today}, rest, weekdays, today)

    title = SKILL_NAMES[skill]
    sub = result_subtype(result)
    if sub:
        title += " · " + sub
    lines = ["✅ <b>Natija saqlandi</b>", "", "%s: <b>%s</b>" % (title, html.escape(result_score(result)))]
    if result.total is not None:
        band_line = "IELTS Band: <b>%s</b>" % fmt_band(band)
        if is_estimated(result.total):
            band_line += " <i>(taxminiy — 40 savolga moslab hisoblandi)</i>"
        lines.append(band_line)
    if result.topic:
        lines.append("📝 %s" % html.escape(result.topic))
    if result.minutes:
        lines.append("⏱ %s" % dates.fmt_minutes(result.minutes))
    if result.photo_file_id:
        lines.append("📸 Rasm biriktirildi")
    lines += ["", "📊 Bugun %s bo‘yicha %d-natija" % (SKILL_NAMES[skill].split(" ", 1)[1], attempt), post_status]

    progress = compute_progress(get_goals(settings), await results_between(session, today, today))
    if progress.percent is not None:
        lines.append("🎯 Kunlik maqsad: %.0f%%" % progress.percent)
    lines.append("🔥 Streak: <b>%d kun</b>" % streak.current)

    if today not in previous_active:
        old = compute_streak(previous_active, rest, weekdays, today)
        if streak.current in MILESTONES:
            lines += ["", "🏆 <b>Tabriklaymiz! %d kunlik streak!</b>" % streak.current]
        elif streak.current > old.longest and streak.current > 1:
            lines += ["", "🆕 <b>Yangi rekord: %d kun!</b>" % streak.current]

    await message.answer("\n".join(lines), reply_markup=after_result_kb(skill))
