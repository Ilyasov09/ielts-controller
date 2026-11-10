"""📊 Statistics va 📤 Export Reports."""
from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import first_result_date
from handlers.common import Target, render, reply_target
from handlers.states import RangeForm
from keyboards.admin import export_format_kb, export_menu_kb, stats_menu_kb, stats_result_kb
from keyboards.main import cancel_ikb
from services.reports import build_excel, build_pdf
from services.statistics import PERIOD_TITLES, format_stats, period_bounds, period_stats, previous_period
from utils import dates

log = logging.getLogger(__name__)
router = Router(name="statistics")

MAX_RANGE_DAYS = 3660


# ---------------------------------------------------------------- statistics
async def show_statistics_menu(target: Target) -> None:
    await render(
        target,
        "📊 <b>STATISTICS</b>\n\n"
        "• <b>Daily</b> — bugungi natijalar\n"
        "• <b>Weekly</b> — oxirgi 7 kun\n"
        "• <b>Monthly</b> — oxirgi 30 kun\n"
        "• <b>Custom</b> — istalgan ikki sana oralig‘i\n\n"
        "Har bir hisobot oldingi xuddi shunday davr bilan solishtiriladi.",
        stats_menu_kb(),
    )


async def show_period(target: Target, session: AsyncSession, title: str, start: dt.date, end: dt.date) -> None:
    current = await period_stats(session, start, end)
    prev_start, prev_end = previous_period(start, end)
    previous = await period_stats(session, prev_start, prev_end)
    await render(target, format_stats(title, current, previous), stats_result_kb(start, end))


@router.callback_query(F.data == "st:menu")
async def stats_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show_statistics_menu(callback)


@router.callback_query(F.data.in_({"st:daily", "st:weekly", "st:monthly"}))
async def stats_period(callback: CallbackQuery, session: AsyncSession) -> None:
    kind = callback.data.split(":", 1)[1]
    await callback.answer()
    start, end = period_bounds(kind, dates.today())
    await show_period(callback, session, PERIOD_TITLES[kind], start, end)


# ---------------------------------------------------------------- custom range (stats va export uchun)
async def ask_range(callback: CallbackQuery, state: FSMContext, purpose: str) -> None:
    await callback.answer()
    await state.set_state(RangeForm.start)
    await state.update_data(purpose=purpose)
    await reply_target(callback).answer(
        "🔎 <b>Custom davr</b>\n\nBoshlanish sanasini yozing (<b>DD.MM.YYYY</b>):",
        reply_markup=cancel_ikb(),
    )


@router.callback_query(F.data == "st:custom")
async def stats_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await ask_range(callback, state, "stats")


@router.callback_query(F.data == "ex:custom")
async def export_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await ask_range(callback, state, "export")


@router.message(RangeForm.start)
async def range_start(message: Message, state: FSMContext) -> None:
    start = dates.parse_date(message.text or "")
    if start is None:
        await message.answer("❗ Sana formati noto‘g‘ri. Masalan: <code>01.11.2026</code>")
        return
    await state.update_data(start=dates.fmt_compact(start))
    await state.set_state(RangeForm.end)
    await message.answer("Tugash sanasini yozing (<b>DD.MM.YYYY</b>):", reply_markup=cancel_ikb())


@router.message(RangeForm.end)
async def range_end(message: Message, state: FSMContext, session: AsyncSession) -> None:
    end = dates.parse_date(message.text or "")
    if end is None:
        await message.answer("❗ Sana formati noto‘g‘ri. Masalan: <code>30.11.2026</code>")
        return
    data = await state.get_data()
    start = dates.parse_compact(data.get("start", ""))
    if start is None:
        await state.clear()
        await message.answer("⚠️ Sessiya eskirgan, qaytadan boshlang.")
        return
    if end < start:
        await message.answer("❗ Tugash sanasi boshlanish sanasidan oldin bo‘lishi mumkin emas.")
        return
    if (end - start).days > MAX_RANGE_DAYS:
        await message.answer("❗ Davr juda uzun (maksimum 10 yil).")
        return
    await state.clear()
    if data.get("purpose") == "export":
        await message.answer(
            "📤 Davr: <b>%s — %s</b>\nFormatni tanlang:" % (dates.fmt_short(start), dates.fmt_short(end)),
            reply_markup=export_format_kb(start, end),
        )
    else:
        await show_period(message, session, PERIOD_TITLES["custom"], start, end)


# ---------------------------------------------------------------- export
async def show_export_menu(target: Target) -> None:
    await render(target, "📤 <b>EXPORT REPORTS</b>\n\nQaysi davr uchun hisobot kerak?", export_menu_kb())


@router.callback_query(F.data == "ex:menu")
async def export_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show_export_menu(callback)


@router.callback_query(F.data.in_({"ex:daily", "ex:weekly", "ex:monthly", "ex:all"}))
async def export_period(callback: CallbackQuery, session: AsyncSession) -> None:
    kind = callback.data.split(":", 1)[1]
    today = dates.today()
    if kind == "all":
        start, end = (await first_result_date(session)) or today, today
    else:
        start, end = period_bounds(kind, today)
    await callback.answer()
    await render(
        callback,
        "📤 Davr: <b>%s — %s</b>\nFormatni tanlang:" % (dates.fmt_short(start), dates.fmt_short(end)),
        export_format_kb(start, end),
    )


@router.callback_query(F.data.startswith("xp:"))
async def export_file(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        _, fmt, raw_start, raw_end = callback.data.split(":")
    except ValueError:
        await callback.answer()
        return
    start, end = dates.parse_compact(raw_start), dates.parse_compact(raw_end)
    if start is None or end is None or fmt not in ("pdf", "xlsx"):
        await callback.answer("Noto‘g‘ri so‘rov")
        return
    await callback.answer("⏳ Tayyorlanmoqda...")
    stats = await period_stats(session, start, end)
    title = "%s - %s" % (dates.fmt_short(start), dates.fmt_short(end))
    try:
        data = build_pdf(stats, title) if fmt == "pdf" else build_excel(stats, title)
    except Exception:
        log.exception("Eksport xatosi")
        await callback.bot.send_message(callback.from_user.id, "❌ Faylni yaratishda xatolik yuz berdi.")
        return
    filename = "ielts_report_%s_%s.%s" % (raw_start, raw_end, fmt)
    await callback.bot.send_document(
        callback.from_user.id,
        BufferedInputFile(data, filename=filename),
        caption="📤 IELTS hisobot: %s\nJami mocklar: %d" % (title, stats.total_mocks),
    )


# ---------------------------------------------------------------- grafik
@router.callback_query(F.data.startswith("gr:"))
async def stats_chart(callback: CallbackQuery, session: AsyncSession) -> None:
    from services.charts import INSTALL_HINT, build_progress_chart

    try:
        _, raw_start, raw_end = callback.data.split(":")
    except ValueError:
        await callback.answer()
        return
    start, end = dates.parse_compact(raw_start), dates.parse_compact(raw_end)
    if start is None or end is None:
        await callback.answer("Noto‘g‘ri so‘rov")
        return
    await callback.answer("⏳ Grafik chizilmoqda...")
    stats = await period_stats(session, start, end)
    try:
        image = build_progress_chart(stats.results, start, end)
    except ImportError:
        await callback.bot.send_message(callback.from_user.id, "ℹ️ " + INSTALL_HINT)
        return
    except Exception:
        log.exception("Grafik xatosi")
        await callback.bot.send_message(callback.from_user.id, "❌ Grafikni chizishda xatolik yuz berdi.")
        return
    if image is None:
        await callback.bot.send_message(callback.from_user.id, "ℹ️ Bu davrda natija yo‘q — grafik bo‘sh.")
        return
    await callback.bot.send_photo(
        callback.from_user.id,
        BufferedInputFile(image, filename="ielts_progress_%s_%s.png" % (raw_start, raw_end)),
        caption="📈 Progress: %s — %s\nYuqorida — skill bandlari (kunlik o‘rtacha), pastda — tayyorgarlik vaqti."
        % (dates.fmt_short(start), dates.fmt_short(end)),
    )
