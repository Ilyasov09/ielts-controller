"""🔥 Streak System va dam olish kunlari."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import (
    add_rest_date,
    get_rest_weekdays,
    get_settings,
    remove_rest_date,
    set_rest_weekdays,
    upcoming_rest_dates,
)
from handlers.common import Target, render, reply_target
from handlers.states import SettingsForm
from keyboards.admin import rest_kb, streak_kb
from keyboards.main import cancel_ikb
from services.streak import MILESTONES, get_streak
from utils import dates

router = Router(name="streak")


async def show_streak(target: Target, session: AsyncSession) -> None:
    info = await get_streak(session)
    if info.today_done:
        today_line = "✅ Bugun hisobot topshirildi"
    elif info.today_rest:
        today_line = "🛌 Bugun dam olish kuni"
    else:
        today_line = "⏳ Bugun hali hisobot yo‘q"
    records = "  ".join(("✅" if info.milestones.get(m) else "⬜") + " %d" % m for m in MILESTONES)
    lines = [
        "🔥 <b>STREAK SYSTEM</b>",
        "",
        "🔥 Joriy streak: <b>%d kun</b>" % info.current,
        "🏆 Eng uzun streak: <b>%d kun</b>" % info.longest,
        "📆 Jami faol kunlar: <b>%d</b>" % info.total_active,
        "📈 Hisobot topshirish foizi: <b>%s</b>"
        % ("%.0f%%" % info.submission_rate if info.submission_rate is not None else "—"),
        today_line,
        "",
        "🏅 Rekordlar: %s" % records,
    ]
    if info.next_milestone:
        lines.append("🎯 Keyingi marra: %d kun (yana %d kun)" % (info.next_milestone, info.next_milestone - info.current))
    else:
        lines.append("👑 Barcha marralar zabt etildi!")
    lines += ["", "<i>Kunda kamida 1 ta skill natijasi kiritilsa streak davom etadi. "
                  "Dam olish kunlari streakni uzmaydi.</i>"]
    await render(target, "\n".join(lines), streak_kb())


async def show_rest_menu(target: Target, session: AsyncSession) -> None:
    settings = await get_settings(session)
    weekdays = get_rest_weekdays(settings)
    upcoming = await upcoming_rest_dates(session, dates.today())
    text = (
        "🛌 <b>DAM OLISH KUNLARI</b>\n\n"
        "Haftalik dam olish kunlarini belgilang (✅ — tanlangan).\n"
        "Aniq sanani oldindan qo‘shish uchun «➕ Sana qo‘shish».\n"
        "Kelgusi sanani o‘chirish uchun ustiga bosing."
    )
    if upcoming:
        text += "\n\nBelgilangan sanalar: " + ", ".join(dates.fmt_short(d) for d in upcoming)
    await render(target, text, rest_kb(weekdays, upcoming))


@router.callback_query(F.data == "streak:open")
async def streak_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_streak(callback, session)


@router.callback_query(F.data == "rest:menu")
async def rest_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await callback.answer()
    await show_rest_menu(callback, session)


@router.callback_query(F.data.startswith("rest:wd:"))
async def rest_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    day = int(callback.data.rsplit(":", 1)[1])
    settings = await get_settings(session)
    weekdays = get_rest_weekdays(settings)
    if day in weekdays:
        weekdays.discard(day)
    elif len(weekdays) >= 6:
        await callback.answer("Kamida bitta ish kuni qolishi kerak.", show_alert=True)
        return
    else:
        weekdays.add(day)
    set_rest_weekdays(settings, weekdays)
    await session.commit()
    await callback.answer()
    await show_rest_menu(callback, session)


@router.callback_query(F.data.startswith("rest:del:"))
async def rest_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    day = dates.parse_compact(callback.data.rsplit(":", 1)[1])
    if day:
        await remove_rest_date(session, day)
    await callback.answer("O‘chirildi")
    await show_rest_menu(callback, session)


@router.callback_query(F.data == "rest:add")
async def rest_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsForm.rest_date)
    await reply_target(callback).answer(
        "🛌 Dam olish sanasini <b>DD.MM.YYYY</b> formatida yozing.\nMasalan: <code>%s</code>"
        % dates.fmt_short(dates.today()),
        reply_markup=cancel_ikb(),
    )


@router.message(SettingsForm.rest_date)
async def rest_add_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    day = dates.parse_date(message.text or "")
    if day is None:
        await message.answer("❗ Sana formati noto‘g‘ri. Masalan: <code>25.12.2026</code>")
        return
    if day < dates.today():
        await message.answer("❗ O‘tgan sanani dam olish kuni qilib bo‘lmaydi. Bugungi yoki kelgusi sanani kiriting.")
        return
    added = await add_rest_date(session, day)
    await state.clear()
    await message.answer(
        ("✅ %s dam olish kuni sifatida belgilandi." if added else "ℹ️ %s allaqachon belgilangan.")
        % dates.fmt_short(day)
    )
    await show_rest_menu(message, session)
