"""⏳ Exam Countdown boshqaruvi."""
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import get_settings
from handlers.common import Target, render
from keyboards.admin import countdown_kb
from services.scheduler import BotScheduler
from utils import dates

router = Router(name="countdown")


async def show_countdown(target: Target, session: AsyncSession) -> None:
    settings = await get_settings(session)
    today = dates.today()
    lines = ["⏳ <b>EXAM COUNTDOWN</b>", ""]
    if settings.exam_date is None:
        lines += [
            "Imtihon sanasi kiritilmagan.",
            "«📅 Sanani o‘zgartirish» tugmasi orqali <b>DD.MM.YYYY</b> formatida kiriting.",
        ]
    else:
        left = dates.days_left(settings.exam_date, today)
        lines.append("📅 Imtihon sanasi: <b>%s</b>" % dates.fmt_long(settings.exam_date))
        if left > 0:
            lines.append("⌛ Qoldi: <b>%d kun</b>" % left)
        elif left == 0:
            lines.append("🎯 <b>Imtihon bugun!</b> Omad!")
        else:
            lines.append("✅ Imtihon %d kun oldin bo‘lib o‘tgan. Yangi sana kiriting." % -left)
    lines += [
        "",
        "🕘 Kanalga post vaqti: <b>%s</b> (har kuni)" % settings.countdown_time,
        "📢 Bugun yuborilgan: %s" % ("✅ ha" if settings.last_countdown_date == today else "— yo‘q"),
    ]
    if not settings.channel_id:
        lines += ["", "⚠️ Kanal ulanmagan — ⚙️ Settings → Kanal."]
    await render(target, "\n".join(lines), countdown_kb(settings.exam_date is not None))


@router.callback_query(F.data == "cd:open")
async def countdown_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_countdown(callback, session)


@router.callback_query(F.data == "cd:send")
async def countdown_send(callback: CallbackQuery, session: AsyncSession, scheduler: BotScheduler) -> None:
    settings = await get_settings(session)
    if not settings.channel_id:
        await callback.answer("Avval kanalni ulang (Settings → Kanal).", show_alert=True)
        return
    if not settings.exam_date or settings.exam_date < dates.today():
        await callback.answer("Imtihon sanasi kiritilmagan yoki o‘tib ketgan.", show_alert=True)
        return
    try:
        sent = await scheduler.countdown_job(force=True)
    except TelegramAPIError as exc:
        await callback.answer()
        await callback.bot.send_message(callback.from_user.id, "❌ Yuborilmadi: %s" % html.escape(str(exc)))
        return
    await callback.answer("✅ Countdown kanalga yuborildi" if sent else "Yuborilmadi", show_alert=not sent)
    await session.refresh(settings)
    await show_countdown(callback, session)
