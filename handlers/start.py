"""/start — admin aniqlash va dastlabki sozlamalar (kanal → imtihon sanasi → report vaqti)."""
from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import get_settings
from handlers.settings import CHANNEL_HELP, EXAM_PROMPT, handle_channel_input, validate_exam_date
from handlers.states import Onboarding
from keyboards.main import BTN_CANCEL, BTN_SKIP, channel_pick_kb, main_menu_kb, reply_kb
from services.channel import channel_display
from services.scheduler import BotScheduler
from utils import dates

router = Router(name="start")


async def status_text(session: AsyncSession) -> str:
    settings = await get_settings(session)
    lines = [
        "🎓 <b>IELTS CONTROLLER</b>",
        "",
        "📢 Kanal: %s" % channel_display(settings.channel_title, settings.channel_username, settings.channel_id),
    ]
    if settings.exam_date:
        left = dates.days_left(settings.exam_date)
        lines.append("📅 Imtihon: <b>%s</b>%s" % (
            dates.fmt_short(settings.exam_date), " (%d kun qoldi)" % left if left >= 0 else " (o‘tgan)"))
    else:
        lines.append("📅 Imtihon sanasi: kiritilmagan")
    lines += [
        "🕘 Daily report: <b>%s</b> · ⏳ Countdown: <b>%s</b>" % (settings.report_time, settings.countdown_time),
        "",
        "Quyidagi menyudan bo‘lim tanlang 👇",
    ]
    return "\n".join(lines)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    settings = await get_settings(session)
    if settings.onboarded:
        await message.answer(await status_text(session), reply_markup=main_menu_kb())
        return
    await message.answer(
        "👋 <b>IELTS CONTROLLER</b> ga xush kelibsiz, %s!\n\n"
        "✅ Siz admin sifatida aniqlandingiz (ID: <code>%d</code>).\n"
        "Keling, botni 3 qadamda sozlaymiz."
        % (html.escape(message.from_user.first_name or ""), message.from_user.id)
    )
    await state.set_state(Onboarding.channel)
    await message.answer("<b>1/3 · Kanalni ulash</b>\n\n" + CHANNEL_HELP, reply_markup=channel_pick_kb(allow_skip=True))


@router.message(Onboarding.channel)
async def onboarding_channel(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    if message.text != BTN_SKIP:
        display = await handle_channel_input(message, session, bot)
        if display is None:
            return
        await message.answer("✅ Kanal ulandi: %s" % display)
    await state.set_state(Onboarding.exam_date)
    await message.answer(
        "<b>2/3 · Imtihon sanasi</b>\n\n" + EXAM_PROMPT + "\n\nKeyinchalik istalgan payt o‘zgartirishingiz mumkin.",
        reply_markup=reply_kb([[BTN_SKIP], [BTN_CANCEL]]),
    )


@router.message(Onboarding.exam_date)
async def onboarding_exam(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text != BTN_SKIP:
        day, error = validate_exam_date(message.text)
        if day is None:
            await message.answer(error)
            return
        settings = await get_settings(session)
        settings.exam_date = day
        await session.commit()
        await message.answer("✅ Imtihon sanasi: <b>%s</b> (%d kun qoldi)" % (dates.fmt_long(day), dates.days_left(day)))
    settings = await get_settings(session)
    await state.set_state(Onboarding.report_time)
    await message.answer(
        "<b>3/3 · Kunlik hisobot vaqti</b>\n\n"
        "Har kuni qaysi vaqtda sizga 📚 Daily Report menyusini yuboray?\n"
        "Tugmani bosing yoki <b>HH:MM</b> formatida yozing.",
        reply_markup=reply_kb([["20:00", "21:00", "22:00"], [settings.report_time + " (standart)"], [BTN_CANCEL]]),
    )


@router.message(Onboarding.report_time)
async def onboarding_report_time(message: Message, state: FSMContext, session: AsyncSession,
                                 scheduler: BotScheduler) -> None:
    value = dates.parse_time((message.text or "").replace("(standart)", ""))
    if value is None:
        await message.answer("❗ Vaqt formati noto‘g‘ri. Masalan: <b>21:00</b>")
        return
    settings = await get_settings(session)
    settings.report_time = value
    settings.onboarded = True
    await session.commit()
    await state.clear()
    scheduler.reschedule(settings)
    await message.answer(
        "🎉 <b>Sozlash yakunlandi!</b>\n\n"
        "• Har kuni <b>%s</b> da Daily Report menyusi keladi.\n"
        "• Countdown posti kanalga har kuni <b>%s</b> da chiqadi (⚙️ Settings da o‘zgartiriladi).\n"
        "• Har bir skill natijasi kanalga alohida post bo‘lib chiqadi." % (value, settings.countdown_time),
        reply_markup=main_menu_kb(),
    )
    await message.answer(await status_text(session), reply_markup=main_menu_kb())
