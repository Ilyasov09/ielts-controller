"""🗂 History — barcha natijalar, ko‘rish va o‘chirish."""
from __future__ import annotations

import html
import math

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import delete_result, get_result, get_settings, results_page
from handlers.common import Target, render
from keyboards.admin import history_delete_kb, history_item_kb, history_kb
from keyboards.skills import SKILL_NAMES
from services.band_calculator import fmt_band
from services.channel import result_score, result_subtype
from utils import dates

router = Router(name="history")

PAGE_SIZE = 8


async def show_history(target: Target, session: AsyncSession, page: int = 0) -> None:
    results, total = await results_page(session, page * PAGE_SIZE, PAGE_SIZE)
    pages = max(1, math.ceil(total / PAGE_SIZE))
    if page >= pages and page > 0:
        page = pages - 1
        results, total = await results_page(session, page * PAGE_SIZE, PAGE_SIZE)
    if not total:
        await render(target, "🗂 <b>HISTORY</b>\n\nHali birorta natija kiritilmagan. 📚 Daily Report dan boshlang!")
        return
    text = "🗂 <b>HISTORY</b>\nJami natijalar: <b>%d</b>\n\nBatafsil ko‘rish uchun natijani tanlang:" % total
    await render(target, text, history_kb(results, page, pages))


@router.callback_query(F.data.startswith("hist:page:"))
async def history_page(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_history(callback, session, max(0, int(callback.data.rsplit(":", 1)[1])))


@router.callback_query(F.data.startswith("hist:view:"))
async def history_view(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, rid, page = callback.data.split(":")
    result = await get_result(session, int(rid))
    await callback.answer()
    if result is None:
        await show_history(callback, session, int(page))
        return
    local = dates.to_local(result.created_at)
    title = SKILL_NAMES[result.skill]
    sub = result_subtype(result)
    lines = [
        "%s%s" % (title, " · " + sub if sub else ""),
        "",
        "📅 %s, %s" % (dates.fmt_long(result.local_date), local.strftime("%H:%M")),
        "🎯 Natija: <b>%s</b>" % html.escape(result_score(result)),
        "🏅 Band: <b>%s</b>" % fmt_band(result.band),
    ]
    if result.topic:
        lines.append("📝 %s" % html.escape(result.topic))
    if result.minutes:
        lines.append("⏱ %s" % dates.fmt_minutes(result.minutes))
    lines.append("📸 Rasm: %s" % ("bor" if result.photo_file_id else "yo‘q"))
    lines.append("📢 Kanal posti: %s" % ("bor" if result.channel_message_id else "yo‘q"))
    await render(callback, "\n".join(lines), history_item_kb(result.id, int(page)))


@router.callback_query(F.data.startswith("hist:del:"))
async def history_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, rid, page = callback.data.split(":")
    result = await get_result(session, int(rid))
    await callback.answer()
    if result is None:
        await show_history(callback, session, int(page))
        return
    await render(
        callback,
        "🗑 Bu natijani o‘chirasizmi?\n<b>%s</b> — %s\n\n"
        "<i>Statistika va streak qayta hisoblanadi. Bu amalni qaytarib bo‘lmaydi.</i>"
        % (SKILL_NAMES[result.skill], html.escape(result_score(result))),
        history_delete_kb(result.id, int(page), bool(result.channel_message_id)),
    )


@router.callback_query(F.data.startswith("hist:delc:"))
async def history_delete_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, rid, page, mode = callback.data.split(":")
    result = await get_result(session, int(rid))
    if result is None:
        await callback.answer("Allaqachon o‘chirilgan")
        await show_history(callback, session, int(page))
        return
    note = ""
    if mode == "all" and result.channel_message_id:
        channel_id = result.channel_id or (await get_settings(session)).channel_id
        try:
            await callback.bot.delete_message(channel_id, result.channel_message_id)
            note = " Kanal posti ham o‘chirildi."
        except TelegramAPIError as exc:
            note = " Kanal postini o‘chirib bo‘lmadi (%s)." % html.escape(str(exc))
    await delete_result(session, result)
    await callback.answer("O‘chirildi")
    await callback.bot.send_message(callback.from_user.id, "✅ Natija o‘chirildi." + note)
    await show_history(callback, session, int(page))
