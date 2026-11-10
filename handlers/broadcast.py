"""📢 Broadcast Manager — botga yuborilgan har qanday xabar kanalga xuddi o‘zidek ko‘chiriladi."""
from __future__ import annotations

import asyncio
import html
import logging
from typing import Dict, List, Set, Tuple

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import get_settings
from handlers.states import BroadcastForm
from services.channel import channel_display

log = logging.getLogger(__name__)
router = Router(name="broadcast")

ALBUM_WAIT = 1.5  # album qismlarini yig‘ish uchun kutish (soniya)

_albums: Dict[Tuple[int, str], List[int]] = {}
_background: Set["asyncio.Task"] = set()


async def start_broadcast(message: Message, state: FSMContext, session: AsyncSession) -> None:
    settings = await get_settings(session)
    if not settings.channel_id:
        await message.answer("⚠️ Avval kanalni ulang: ⚙️ Settings → 📢 Kanal.")
        return
    await state.clear()
    await state.set_state(BroadcastForm.active)
    await message.answer(
        "📢 <b>BROADCAST REJIMI YOQILDI</b>\n"
        "Kanal: %s\n\n"
        "Endi menga nima yuborsangiz — kanalga <b>xuddi o‘sha ko‘rinishda</b> darhol ko‘chiriladi:\n"
        "matn, rasm, video, audio, ovozli xabar, hujjat, sticker, GIF, album — caption va formatlash saqlanadi.\n\n"
        "🚪 Chiqish: /cancel"
        % channel_display(settings.channel_title, settings.channel_username, settings.channel_id),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(BroadcastForm.active)
async def broadcast_relay(message: Message, session: AsyncSession, bot: Bot) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer("ℹ️ Broadcast rejimida buyruqlar kanalga yuborilmaydi. Chiqish uchun /cancel.")
        return
    settings = await get_settings(session)
    if not settings.channel_id:
        await message.answer("⚠️ Kanal ulanmagan. /cancel bosib, Settings orqali ulang.")
        return

    if message.media_group_id:
        _collect_album(bot, message, settings.channel_id)
        return

    for attempt in range(2):
        try:
            await bot.copy_message(
                chat_id=settings.channel_id, from_chat_id=message.chat.id, message_id=message.message_id
            )
            break
        except TelegramRetryAfter as exc:
            if attempt:
                await message.reply("❌ Telegram limiti: %d soniyadan keyin qayta yuboring." % exc.retry_after)
                return
            await asyncio.sleep(exc.retry_after + 0.5)
        except TelegramAPIError as exc:
            await message.reply("❌ Yuborilmadi: %s" % html.escape(str(exc)))
            return
    await message.reply("✅ Kanalga yuborildi")


def _collect_album(bot: Bot, message: Message, channel_id: int) -> None:
    key = (message.chat.id, str(message.media_group_id))
    if key in _albums:
        _albums[key].append(message.message_id)
        return
    _albums[key] = [message.message_id]
    task = asyncio.ensure_future(_flush_album(bot, key, channel_id))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _flush_album(bot: Bot, key: Tuple[int, str], channel_id: int) -> None:
    await asyncio.sleep(ALBUM_WAIT)
    message_ids = sorted(_albums.pop(key, []))
    chat_id = key[0]
    if not message_ids:
        return
    try:
        await bot.copy_messages(chat_id=channel_id, from_chat_id=chat_id, message_ids=message_ids)
        await bot.send_message(chat_id, "✅ Album (%d ta media) kanalga yuborildi" % len(message_ids))
    except TelegramAPIError as exc:
        log.warning("Album yuborilmadi: %s", exc)
        await bot.send_message(chat_id, "❌ Album yuborilmadi: %s" % html.escape(str(exc)))
