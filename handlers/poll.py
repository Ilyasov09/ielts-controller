"""🗳 Poll Creator — o‘zgaruvchan ovozli inline tugmalar."""
from __future__ import annotations

import asyncio
import html
import logging
from typing import List, Set

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import SessionLocal
from database.models import Poll
from database.repository import (
    cast_vote,
    create_poll,
    get_poll,
    get_settings,
    poll_counts,
    poll_options,
    poll_voter_count,
    recent_polls,
)
from handlers.common import Target, drop_keyboard, render, reply_target
from handlers.states import PollForm
from keyboards.main import cancel_ikb, main_menu_kb
from keyboards.poll import (
    builder_kb,
    confirm_kb,
    poll_close_confirm_kb,
    poll_manage_kb,
    poll_menu_kb,
    preview_kb,
    vote_kb,
)
from utils import dates

log = logging.getLogger(__name__)
router = Router(name="poll")

MAX_OPTIONS = 30
MAX_OPTION_LEN = 64
MAX_TEXT_LEN = 3500
MIN_OPTIONS = 2


# ---------------------------------------------------------------- yaratish
async def start_poll(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PollForm.text)
    await message.answer(
        "🗳 <b>POLL CREATOR</b>\nStep-by-step creation\n\n"
        "<b>1-qadam:</b> Post matnini yuboring.\n"
        "<i>Masalan: Bugun IELTS uchun qancha vaqt tayyorlandingiz?</i>",
        reply_markup=cancel_ikb(),
    )


def _builder_text(text: str, options: List[str]) -> str:
    lines = ["🗳 <b>POLL CREATOR</b>", "", text, "", "<b>2-qadam: Tugmalar</b>"]
    if options:
        for index, option in enumerate(options, start=1):
            lines.append("Tugma %d ✅ Added — %s" % (index, html.escape(option)))
    else:
        lines.append("Hali tugma yo‘q.")
    lines += [
        "",
        "Keyingi tugma matnini yuboring yoki «✅ Tayyor» ni bosing." if options else "1-tugma matnini yuboring.",
    ]
    return "\n".join(lines)


@router.message(PollForm.text)
async def poll_text(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("❗ Post matnini oddiy matn ko‘rinishida yuboring.")
        return
    if len(message.text) > MAX_TEXT_LEN:
        await message.answer("❗ Matn juda uzun (maksimum %d belgi)." % MAX_TEXT_LEN)
        return
    await state.update_data(text=message.html_text, options=[])
    await state.set_state(PollForm.option)
    await message.answer(
        "<b>2-qadam:</b> 1-tugma matnini yuboring.\n<i>Masalan: 1 soat</i>",
        reply_markup=cancel_ikb(),
    )


@router.message(PollForm.option)
async def poll_option(message: Message, state: FSMContext) -> None:
    option = " ".join((message.text or "").split())
    data = await state.get_data()
    options: List[str] = list(data.get("options", []))
    if not option:
        await message.answer("❗ Tugma matnini oddiy matn ko‘rinishida yuboring.")
        return
    if len(option) > MAX_OPTION_LEN:
        await message.answer("❗ Tugma matni juda uzun (maksimum %d belgi)." % MAX_OPTION_LEN)
        return
    if option in options:
        await message.answer("❗ Bunday tugma allaqachon bor.")
        return
    if len(options) >= MAX_OPTIONS:
        await message.answer("❗ Maksimum %d ta tugma. «✅ Tayyor» ni bosing." % MAX_OPTIONS)
        return
    options.append(option)
    await state.update_data(options=options)
    await message.answer(_builder_text(data["text"], options), reply_markup=builder_kb(len(options)))


@router.callback_query(PollForm.option, F.data == "poll:add")
async def poll_add(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.answer()
    await drop_keyboard(callback)
    await reply_target(callback).answer(
        "%d-tugma matnini yuboring:" % (len(data.get("options", [])) + 1), reply_markup=cancel_ikb()
    )


@router.callback_query(PollForm.option, F.data == "poll:undo")
async def poll_undo(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    options = list(data.get("options", []))
    if options:
        options.pop()
    await state.update_data(options=options)
    await callback.answer("Oxirgi tugma o‘chirildi")
    await reply_target(callback).edit_text(_builder_text(data["text"], options), reply_markup=builder_kb(len(options)))


@router.callback_query(PollForm.option, F.data == "poll:done")
async def poll_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    options = list(data.get("options", []))
    if len(options) < MIN_OPTIONS:
        await callback.answer("Kamida %d ta tugma qo‘shing." % MIN_OPTIONS, show_alert=True)
        return
    await callback.answer()
    await drop_keyboard(callback)
    await state.set_state(PollForm.preview)
    message = reply_target(callback)
    await message.answer("<b>3-qadam: Yakuniy ko‘rinish</b> 👇")
    await message.answer(data["text"], reply_markup=preview_kb(options))
    await message.answer(
        "Kanalda har bir tugmada ovozlar soni ko‘rinadi. Bir foydalanuvchi bitta variantga ovoz beradi "
        "va xohlasa boshqasiga ko‘chira oladi.\n\nKanalga yuboraymi?",
        reply_markup=confirm_kb(),
    )


@router.callback_query(PollForm.preview, F.data == "poll:edit")
async def poll_edit(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.answer()
    await drop_keyboard(callback)
    await state.set_state(PollForm.option)
    options = list(data.get("options", []))
    await reply_target(callback).answer(_builder_text(data["text"], options), reply_markup=builder_kb(len(options)))


@router.message(PollForm.preview)
async def poll_preview_text(message: Message) -> None:
    await message.answer("Yuqoridagi tugmalardan birini tanlang 👆", reply_markup=confirm_kb())


@router.callback_query(PollForm.preview, F.data == "poll:send")
async def poll_send(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    settings = await get_settings(session)
    if not settings.channel_id:
        await callback.answer("Avval kanalni ulang (Settings → Kanal).", show_alert=True)
        return
    data = await state.get_data()
    options = list(data.get("options", []))
    if len(options) < MIN_OPTIONS:
        await callback.answer("Sessiya eskirgan.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    await drop_keyboard(callback)
    await state.clear()

    poll = await create_poll(session, data["text"], options)
    db_options = await poll_options(session, poll.id)
    try:
        sent = await bot.send_message(settings.channel_id, data["text"], reply_markup=vote_kb(poll.id, db_options, {}))
    except TelegramAPIError as exc:
        await reply_target(callback).answer("❌ Kanalga yuborilmadi: %s" % html.escape(str(exc)), reply_markup=main_menu_kb())
        return
    poll.channel_id = settings.channel_id
    poll.message_id = sent.message_id
    await session.commit()
    link = ""
    if settings.channel_username:
        link = "\n🔗 https://t.me/%s/%d" % (settings.channel_username, sent.message_id)
    await reply_target(callback).answer("✅ Poll kanalga yuborildi!" + link, reply_markup=main_menu_kb())


# ---------------------------------------------------------------- ovoz berish (hamma uchun ochiq)
_pending_refresh: Set[int] = set()
_background: Set["asyncio.Task"] = set()


@router.callback_query(F.data.startswith("pv:"))
async def poll_vote(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    try:
        _, raw_poll, raw_option = callback.data.split(":")
        poll_id, option_id = int(raw_poll), int(raw_option)
    except ValueError:
        await callback.answer()
        return
    status, option = await cast_vote(session, poll_id, option_id, callback.from_user.id)
    if status == "invalid" or option is None:
        await callback.answer("Bu variant topilmadi.")
        return
    if status == "closed":
        await callback.answer("🔒 Bu poll yopilgan, ovoz berib bo‘lmaydi.")
        return
    if status == "same":
        await callback.answer("Siz allaqachon «%s» variantiga ovoz bergansiz ✅" % option.text)
        return
    if status == "new":
        await callback.answer("✅ Ovozingiz qabul qilindi: %s" % option.text)
    else:
        await callback.answer("🔄 Ovozingiz «%s» variantiga ko‘chirildi" % option.text)

    message = callback.message
    if message is not None:
        _schedule_refresh(bot, poll_id, message.chat.id, message.message_id)


def _schedule_refresh(bot: Bot, poll_id: int, chat_id: int, message_id: int) -> None:
    """Ko‘p ovozda Telegram limitiga tushmaslik uchun yangilashni 1 soniyaga jamlaymiz."""
    if poll_id in _pending_refresh:
        return
    _pending_refresh.add(poll_id)
    task = asyncio.ensure_future(_refresh(bot, poll_id, chat_id, message_id))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _refresh(bot: Bot, poll_id: int, chat_id: int, message_id: int) -> None:
    try:
        await asyncio.sleep(1.0)
        _pending_refresh.discard(poll_id)
        async with SessionLocal() as session:
            poll = await get_poll(session, poll_id)
            if poll is None or poll.closed:  # yopilgan pollga tugmalarni qaytarmaymiz
                return
            options = await poll_options(session, poll_id)
            counts = await poll_counts(session, poll_id)
        markup = vote_kb(poll_id, options, counts)
        for _attempt in range(3):
            try:
                await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
                return
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after + 0.5)
            except TelegramBadRequest as exc:
                if "not modified" not in str(exc).lower():
                    log.warning("Poll %s yangilanmadi: %s", poll_id, exc)
                return
    except Exception:
        log.exception("Poll %s yangilashda xato", poll_id)
    finally:
        _pending_refresh.discard(poll_id)


# ---------------------------------------------------------------- boshqarish: ro‘yxat, natija, yopish
TEXT_LIMIT = 4096


def results_block(options, counts) -> str:
    total = sum(counts.get(o.id, 0) for o in options)
    lines = []
    for option in options:
        count = counts.get(option.id, 0)
        percent = count * 100.0 / total if total else 0.0
        filled = int(round(percent / 10))
        lines.append("%s %3.0f%% — %s (%d)" % ("▓" * filled + "░" * (10 - filled), percent,
                                              html.escape(option.text), count))
    lines.append("👥 Jami: <b>%d</b> ovoz" % total)
    return "\n".join(lines)


def _post_link(poll: Poll, username) -> str:
    if username and poll.message_id:
        return "https://t.me/%s/%d" % (username, poll.message_id)
    return ""


async def show_poll_menu(target: Target, session: AsyncSession) -> None:
    polls = await recent_polls(session)
    voters = {poll.id: await poll_voter_count(session, poll.id) for poll in polls}
    text = "🗳 <b>POLL CREATOR</b>\n\n"
    text += ("Yangi poll yarating yoki mavjudini tanlang: natijalarni foizda ko‘rish va yopish mumkin.\n"
             "🟢 — ochiq, 🔒 — yopilgan, (son) — ovozlar."
             if polls else "Hali poll yo‘q. «➕ Yangi poll» ni bosing.")
    await render(target, text, poll_menu_kb(polls, voters))


async def show_poll(target: Target, session: AsyncSession, poll_id: int) -> None:
    poll = await get_poll(session, poll_id)
    if poll is None:
        await show_poll_menu(target, session)
        return
    options = await poll_options(session, poll_id)
    counts = await poll_counts(session, poll_id)
    created = dates.to_local(poll.created_at).strftime("%d.%m.%Y %H:%M")
    status = "🔒 Yopilgan" if poll.closed else "🟢 Ochiq"
    if poll.closed and poll.closed_at:
        status += " (%s)" % dates.to_local(poll.closed_at).strftime("%d.%m.%Y %H:%M")
    text = "%s\n\n📊 <b>Natija</b>\n%s\n\n%s · yaratilgan: %s" % (
        poll.text, results_block(options, counts), status, created)
    settings = await get_settings(session)
    await render(target, text[:TEXT_LIMIT], poll_manage_kb(poll, _post_link(poll, settings.channel_username)))


@router.callback_query(F.data == "poll:new")
async def poll_new(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await start_poll(reply_target(callback), state)


@router.callback_query(F.data == "pm:list")
async def poll_list(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_poll_menu(callback, session)


@router.callback_query(F.data.startswith("pm:view:"))
async def poll_view(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_poll(callback, session, int(callback.data.rsplit(":", 1)[1]))


@router.callback_query(F.data.startswith("pm:close:"))
async def poll_close_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    poll_id = int(callback.data.rsplit(":", 1)[1])
    await callback.answer()
    await render(
        callback,
        "🔒 Pollni yopasizmi?\n\nKanaldagi postdan tugmalar olib tashlanadi va o‘rniga yakuniy natija "
        "foizlarda yoziladi. Shundan keyin ovoz berib bo‘lmaydi. Bu amalni qaytarib bo‘lmaydi.",
        poll_close_confirm_kb(poll_id),
    )


@router.callback_query(F.data.startswith("pm:closec:"))
async def poll_close(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    poll_id = int(callback.data.rsplit(":", 1)[1])
    poll = await get_poll(session, poll_id)
    if poll is None:
        await callback.answer("Poll topilmadi")
        await show_poll_menu(callback, session)
        return
    if poll.closed:
        await callback.answer("Allaqachon yopilgan")
        await show_poll(callback, session, poll_id)
        return
    poll.closed = True
    poll.closed_at = dates.utcnow()
    await session.commit()

    options = await poll_options(session, poll_id)
    counts = await poll_counts(session, poll_id)
    final = "%s\n\n🔒 <b>Poll yopildi — yakuniy natija</b>\n%s" % (poll.text, results_block(options, counts))
    note = "✅ Poll yopildi, kanaldagi post yangilandi."
    if poll.channel_id and poll.message_id:
        try:
            await bot.edit_message_text(final[:TEXT_LIMIT], chat_id=poll.channel_id, message_id=poll.message_id,
                                        reply_markup=None)
        except TelegramAPIError as exc:
            note = "⚠️ Poll yopildi (ovozlar qabul qilinmaydi), lekin kanaldagi postni tahrirlab bo‘lmadi: %s" \
                   % html.escape(str(exc))
    await callback.answer("Yopildi")
    await bot.send_message(callback.from_user.id, note)
    await show_poll(callback, session, poll_id)
