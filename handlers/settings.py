"""⚙️ Settings: kanal, imtihon sanasi, report va countdown vaqtlari."""
from __future__ import annotations

import html
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.repository import get_rest_weekdays, get_settings
from handlers.common import Target, drop_keyboard, render, reply_target
from handlers.countdown import show_countdown
from handlers.states import SettingsForm
from keyboards.admin import exam_date_kb, settings_kb, time_kb, weekly_kb
from keyboards.main import channel_pick_kb, main_menu_kb
from services.channel import channel_display, extract_channel_ref, verify_channel
from services.scheduler import BotScheduler
from utils import dates

router = Router(name="settings")

REPORT_TIME_CHOICES = ("20:00", "21:00", "22:00")
COUNTDOWN_TIME_CHOICES = ("07:00", "08:00", "09:00")
REMINDER_TIME_CHOICES = ("21:00", "22:00", "23:00")
WEEKLY_TIME_CHOICES = ("18:00", "20:00", "21:00")
TIME_LABELS = {
    "report_time": "Daily report",
    "countdown_time": "Countdown",
    "reminder_time": "Kechki eslatma",
    "weekly_time": "Haftalik hisobot",
}

CHANNEL_HELP = (
    "1) Botni kanalingizga <b>admin</b> qilib qo‘shing (<b>Post messages</b> va "
    "<b>Edit messages</b> huquqlari bilan).\n"
    "2) Pastdagi «📢 Kanalni tanlash» tugmasini bosing — yoki kanaldan istalgan postni "
    "forward qiling, yoki kanal <b>@username</b> / <b>-100…</b> ID sini yuboring."
)
EXAM_PROMPT = "📅 Imtihon sanasini <b>DD.MM.YYYY</b> formatida yozing.\nMasalan: <code>09.03.2027</code>"


async def settings_text(session: AsyncSession) -> str:
    settings = await get_settings(session)
    weekdays = get_rest_weekdays(settings)
    rest = ", ".join(dates.WEEKDAYS_UZ[d] for d in sorted(weekdays)) or "yo‘q"
    exam = dates.fmt_short(settings.exam_date) if settings.exam_date else "kiritilmagan"
    return "\n".join([
        "⚙️ <b>SETTINGS</b>",
        "",
        "📢 Kanal: %s" % channel_display(settings.channel_title, settings.channel_username, settings.channel_id),
        "📅 Imtihon sanasi: <b>%s</b>" % exam,
        "🕘 Daily report vaqti: <b>%s</b>" % settings.report_time,
        "⏳ Countdown vaqti: <b>%s</b>" % settings.countdown_time,
        "🔔 Kechki eslatma: %s" % ("<b>%s</b>" % settings.reminder_time if settings.reminder_time else "o‘chirilgan"),
        "📊 Haftalik hisobot: %s" % (
            "<b>%s %s</b>" % (dates.WEEKDAYS_UZ[settings.weekly_day], settings.weekly_time)
            if settings.weekly_enabled else "o‘chirilgan"),
        "🛌 Haftalik dam olish: %s" % rest,
        "🌍 Vaqt zonasi: %s" % config.timezone,
    ])


async def show_settings(target: Target, session: AsyncSession) -> None:
    await render(target, await settings_text(session), settings_kb())


async def handle_channel_input(message: Message, session: AsyncSession, bot: Bot) -> Optional[str]:
    """Kanalni aniqlaydi, tekshiradi va saqlaydi. Muvaffaqiyatli bo‘lsa kanal nomini qaytaradi."""
    ref = extract_channel_ref(message)
    if ref is None:
        await message.answer("❗ Kanalni aniqlay olmadim.\n\n" + CHANNEL_HELP)
        return None
    chat, error = await verify_channel(bot, ref)
    if chat is None:
        await message.answer("❌ " + (error or "Kanal tekshiruvdan o‘tmadi."))
        return None
    settings = await get_settings(session)
    settings.channel_id = chat.id
    settings.channel_title = chat.title
    settings.channel_username = chat.username
    await session.commit()
    return channel_display(chat.title, chat.username, chat.id)


def validate_exam_date(raw: Optional[str]):
    day = dates.parse_date(raw or "")
    if day is None:
        return None, "❗ Sana formati noto‘g‘ri. <b>DD.MM.YYYY</b> ko‘rinishida yozing, masalan <code>09.03.2027</code>"
    if day < dates.today():
        return None, "❗ Bu sana o‘tib ketgan. Bugungi yoki kelgusi sanani kiriting."
    return day, None


@router.callback_query(F.data == "set:open")
async def settings_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_settings(callback, session)


# ---------------------------------------------------------------- kanal
@router.callback_query(F.data == "set:channel")
async def channel_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsForm.channel)
    await reply_target(callback).answer("📢 <b>Kanalni ulash</b>\n\n" + CHANNEL_HELP, reply_markup=channel_pick_kb(False))


@router.message(SettingsForm.channel)
async def channel_input(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    display = await handle_channel_input(message, session, bot)
    if display is None:
        return
    await state.clear()
    await message.answer("✅ Kanal ulandi: %s" % display, reply_markup=main_menu_kb())
    await show_settings(message, session)


# ---------------------------------------------------------------- imtihon sanasi
@router.callback_query(F.data == "set:exam")
async def exam_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    settings = await get_settings(session)
    await state.set_state(SettingsForm.exam_date)
    current = "\nHozirgi sana: <b>%s</b>" % dates.fmt_short(settings.exam_date) if settings.exam_date else ""
    await reply_target(callback).answer(EXAM_PROMPT + current, reply_markup=exam_date_kb(settings.exam_date is not None))


@router.callback_query(F.data == "set:exam_clear")
async def exam_clear(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    settings = await get_settings(session)
    settings.exam_date = None
    await session.commit()
    await callback.answer("Imtihon sanasi o‘chirildi")
    await drop_keyboard(callback)
    await show_countdown(reply_target(callback), session)


@router.message(SettingsForm.exam_date)
async def exam_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    day, error = validate_exam_date(message.text)
    if day is None:
        await message.answer(error)
        return
    settings = await get_settings(session)
    settings.exam_date = day
    await session.commit()
    await state.clear()
    await message.answer("✅ Imtihon sanasi saqlandi: <b>%s</b>" % dates.fmt_long(day))
    await show_countdown(message, session)


# ---------------------------------------------------------------- vaqtlar
async def _save_time(target: Message, state: FSMContext, session: AsyncSession, scheduler: BotScheduler,
                     field: str, value: str) -> None:
    settings = await get_settings(session)
    setattr(settings, field, value)
    await session.commit()
    await state.clear()
    scheduler.reschedule(settings)
    await target.answer("✅ %s vaqti: <b>%s</b>" % (TIME_LABELS[field], value))
    if field == "weekly_time":
        await show_weekly(target, session)
    else:
        await show_settings(target, session)


@router.callback_query(F.data == "set:report")
async def report_time_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    settings = await get_settings(session)
    await state.set_state(SettingsForm.report_time)
    await reply_target(callback).answer(
        "🕘 Daily Report menyusi har kuni qaysi vaqtda yuborilsin?\nHozir: <b>%s</b>\n"
        "Tugmani bosing yoki <b>HH:MM</b> formatida yozing." % settings.report_time,
        reply_markup=time_kb("rtime", REPORT_TIME_CHOICES),
    )


@router.callback_query(F.data == "set:countdown")
async def countdown_time_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    settings = await get_settings(session)
    await state.set_state(SettingsForm.countdown_time)
    await reply_target(callback).answer(
        "⏳ Countdown posti kanalga har kuni qaysi vaqtda chiqsin?\nHozir: <b>%s</b>\n"
        "Tugmani bosing yoki <b>HH:MM</b> formatida yozing." % settings.countdown_time,
        reply_markup=time_kb("ctime", COUNTDOWN_TIME_CHOICES),
    )


def _time_from_callback(data: str) -> Optional[str]:
    raw = data.split(":", 1)[1]
    return dates.parse_time(raw[:2] + ":" + raw[2:]) if len(raw) == 4 else None


@router.callback_query(SettingsForm.report_time, F.data.startswith("rtime:"))
async def report_time_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession,
                             scheduler: BotScheduler) -> None:
    value = _time_from_callback(callback.data)
    await callback.answer()
    await drop_keyboard(callback)
    if value:
        await _save_time(reply_target(callback), state, session, scheduler, "report_time", value)


@router.callback_query(SettingsForm.countdown_time, F.data.startswith("ctime:"))
async def countdown_time_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession,
                                scheduler: BotScheduler) -> None:
    value = _time_from_callback(callback.data)
    await callback.answer()
    await drop_keyboard(callback)
    if value:
        await _save_time(reply_target(callback), state, session, scheduler, "countdown_time", value)


@router.message(SettingsForm.report_time)
async def report_time_input(message: Message, state: FSMContext, session: AsyncSession, scheduler: BotScheduler) -> None:
    value = dates.parse_time(message.text or "")
    if value is None:
        await message.answer("❗ Vaqt formati noto‘g‘ri. Masalan: <b>21:00</b>")
        return
    await _save_time(message, state, session, scheduler, "report_time", value)


@router.message(SettingsForm.countdown_time)
async def countdown_time_input(message: Message, state: FSMContext, session: AsyncSession,
                               scheduler: BotScheduler) -> None:
    value = dates.parse_time(message.text or "")
    if value is None:
        await message.answer("❗ Vaqt formati noto‘g‘ri. Masalan: <b>09:00</b>")
        return
    await _save_time(message, state, session, scheduler, "countdown_time", value)


# ---------------------------------------------------------------- kechki eslatma
@router.callback_query(F.data == "set:reminder")
async def reminder_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    settings = await get_settings(session)
    await state.set_state(SettingsForm.reminder_time)
    current = settings.reminder_time or "o‘chirilgan"
    await reply_target(callback).answer(
        "🔔 <b>Kechki eslatma</b>\n\n"
        "Bugun hali hisobot kiritilmagan bo‘lsa, shu vaqtda bot streak uzilmasligi haqida eslatadi "
        "(dam olish kunlari eslatma yuborilmaydi).\n\nHozir: <b>%s</b>\n"
        "Tugmani bosing yoki <b>HH:MM</b> formatida yozing." % current,
        reply_markup=time_kb("mtime", REMINDER_TIME_CHOICES, [[("🔕 O‘chirish", "set:reminder_off")]]),
    )


@router.callback_query(F.data == "set:reminder_off")
async def reminder_off(callback: CallbackQuery, state: FSMContext, session: AsyncSession,
                       scheduler: BotScheduler) -> None:
    settings = await get_settings(session)
    settings.reminder_time = None
    await session.commit()
    await state.clear()
    scheduler.reschedule(settings)
    await callback.answer("Eslatma o‘chirildi")
    await drop_keyboard(callback)
    await show_settings(reply_target(callback), session)


@router.callback_query(SettingsForm.reminder_time, F.data.startswith("mtime:"))
async def reminder_time_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession,
                               scheduler: BotScheduler) -> None:
    value = _time_from_callback(callback.data)
    await callback.answer()
    await drop_keyboard(callback)
    if value:
        await _save_time(reply_target(callback), state, session, scheduler, "reminder_time", value)


@router.message(SettingsForm.reminder_time)
async def reminder_time_input(message: Message, state: FSMContext, session: AsyncSession,
                              scheduler: BotScheduler) -> None:
    value = dates.parse_time(message.text or "")
    if value is None:
        await message.answer("❗ Vaqt formati noto‘g‘ri. Masalan: <b>22:00</b>")
        return
    await _save_time(message, state, session, scheduler, "reminder_time", value)


# ---------------------------------------------------------------- haftalik hisobot
async def show_weekly(target: Target, session: AsyncSession) -> None:
    settings = await get_settings(session)
    status = ("🟢 Yoqilgan — har <b>%s</b> kuni soat <b>%s</b> da"
              % (dates.WEEKDAYS_UZ[settings.weekly_day], settings.weekly_time)) if settings.weekly_enabled \
        else "⚪️ O‘chirilgan"
    last = dates.fmt_short(settings.last_weekly_date) if settings.last_weekly_date else "—"
    text = (
        "📊 <b>HAFTALIK KANAL HISOBOTI</b>\n\n"
        "Kanalga oxirgi 7 kun natijalari (mocklar, vaqt, o‘rtacha bandlar, o‘tgan hafta bilan farq) "
        "va progress grafigi bitta post bo‘lib chiqadi. Hafta davomida natija bo‘lmasa, post yuborilmaydi.\n\n"
        "%s\nOxirgi yuborilgan: %s" % (status, last)
    )
    await render(target, text, weekly_kb(settings.weekly_enabled, settings.weekly_day, settings.weekly_time))


@router.callback_query(F.data == "wk:menu")
async def weekly_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await callback.answer()
    await show_weekly(callback, session)


@router.callback_query(F.data == "wk:toggle")
async def weekly_toggle(callback: CallbackQuery, session: AsyncSession, scheduler: BotScheduler) -> None:
    settings = await get_settings(session)
    settings.weekly_enabled = not settings.weekly_enabled
    await session.commit()
    scheduler.reschedule(settings)
    await callback.answer("Yoqildi" if settings.weekly_enabled else "O‘chirildi")
    await show_weekly(callback, session)


@router.callback_query(F.data.startswith("wk:day:"))
async def weekly_day(callback: CallbackQuery, session: AsyncSession, scheduler: BotScheduler) -> None:
    day = int(callback.data.rsplit(":", 1)[1])
    settings = await get_settings(session)
    if 0 <= day <= 6 and day != settings.weekly_day:
        settings.weekly_day = day
        await session.commit()
        scheduler.reschedule(settings)
    await callback.answer(dates.WEEKDAYS_UZ[settings.weekly_day])
    await show_weekly(callback, session)


@router.callback_query(F.data == "wk:time")
async def weekly_time_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    settings = await get_settings(session)
    await state.set_state(SettingsForm.weekly_time)
    await reply_target(callback).answer(
        "⏰ Haftalik hisobot vaqti?\nHozir: <b>%s</b>\nTugmani bosing yoki <b>HH:MM</b> formatida yozing."
        % settings.weekly_time,
        reply_markup=time_kb("wtime", WEEKLY_TIME_CHOICES),
    )


@router.callback_query(SettingsForm.weekly_time, F.data.startswith("wtime:"))
async def weekly_time_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession,
                             scheduler: BotScheduler) -> None:
    value = _time_from_callback(callback.data)
    await callback.answer()
    await drop_keyboard(callback)
    if value:
        await _save_time(reply_target(callback), state, session, scheduler, "weekly_time", value)


@router.message(SettingsForm.weekly_time)
async def weekly_time_input(message: Message, state: FSMContext, session: AsyncSession,
                            scheduler: BotScheduler) -> None:
    value = dates.parse_time(message.text or "")
    if value is None:
        await message.answer("❗ Vaqt formati noto‘g‘ri. Masalan: <b>20:00</b>")
        return
    await _save_time(message, state, session, scheduler, "weekly_time", value)


@router.callback_query(F.data == "wk:preview")
async def weekly_preview(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    from services.weekly import build_weekly, send_weekly

    await callback.answer("⏳ Tayyorlanmoqda...")
    built = await build_weekly(session, dates.today())
    if built is None:
        await bot.send_message(callback.from_user.id, "ℹ️ Oxirgi 7 kunda natija yo‘q — hisobot bo‘sh.")
        return
    await send_weekly(bot, callback.from_user.id, *built)


@router.callback_query(F.data == "wk:send")
async def weekly_send(callback: CallbackQuery, session: AsyncSession, scheduler: BotScheduler) -> None:
    settings = await get_settings(session)
    if not settings.channel_id:
        await callback.answer("Avval kanalni ulang (Settings → Kanal).", show_alert=True)
        return
    await callback.answer("⏳ Yuborilmoqda...")
    try:
        status = await scheduler.weekly_job(force=True)
    except TelegramAPIError as exc:
        await callback.bot.send_message(callback.from_user.id, "❌ Yuborilmadi: %s" % html.escape(str(exc)))
        return
    text = {"sent": "✅ Haftalik hisobot kanalga yuborildi.",
            "empty": "ℹ️ Oxirgi 7 kunda natija yo‘q — post yuborilmadi."}.get(status, "❌ Yuborilmadi.")
    await callback.bot.send_message(callback.from_user.id, text)
    await session.refresh(settings)
    await show_weekly(callback, session)
