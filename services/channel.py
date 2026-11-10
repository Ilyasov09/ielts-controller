"""Kanalga post yuborish va kanalni tekshirish."""
from __future__ import annotations

import datetime as dt
import html
from typing import Optional, Tuple, Union

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Chat, Message

from database.models import Result
from services.band_calculator import READING_TYPES, fmt_band
from utils import dates
from utils.validators import clean_text, parse_channel_ref

SKILL_INFO = {
    "listening": ("🎧", "LISTENING", "Listening"),
    "reading": ("📖", "READING", "Reading"),
    "writing": ("✍️", "WRITING", "Writing"),
    "speaking": ("🎙", "SPEAKING", "Speaking"),
}


def skill_label(skill: str) -> str:
    emoji, _upper, name = SKILL_INFO[skill]
    return "%s %s" % (emoji, name)


def result_subtype(result: Result) -> str:
    if result.skill == "reading":
        return READING_TYPES.get(result.reading_type or "", "")
    if result.skill in ("writing", "speaking"):
        return result.task or ""
    return ""


def result_score(result: Result) -> str:
    if result.total is not None and result.correct is not None:
        return "%d/%d" % (result.correct, result.total)
    return "Band %s" % fmt_band(result.band)


def result_short(result: Result) -> str:
    """09.11 14:05 · 🎧 32/40 · 7.5"""
    local = dates.to_local(result.created_at)
    emoji = SKILL_INFO[result.skill][0]
    if result.total is not None:
        score = "%s · %s" % (result_score(result), fmt_band(result.band))
    else:
        score = fmt_band(result.band)
    sub = result_subtype(result)
    sub = " " + sub.replace("General Training", "GT").replace("Academic", "AC") if sub else ""
    return "%s %s%s · %s" % (local.strftime("%d.%m %H:%M"), emoji, sub, score)


def _header(result: Result, suffix: str = "") -> str:
    emoji, upper, _name = SKILL_INFO[result.skill]
    title = "%s <b>%s%s</b>" % (emoji, upper, suffix)
    sub = result_subtype(result)
    if sub:
        title += " · <b>%s</b>" % html.escape(sub.upper())
    return title


def _topic_lines(result: Result, limit: int) -> list:
    if not result.topic:
        return []
    return ["📝 <i>%s</i>" % html.escape(clean_text(result.topic, limit)), ""]


def build_result_caption(result: Result) -> str:
    """Rasm bilan yuboriladigan post (caption ≤ 1024 belgi)."""
    _emoji, _upper, name = SKILL_INFO[result.skill]
    lines = [_header(result), ""]
    if result.total is not None:
        lines += ["<b>%d / %d</b>" % (result.correct, result.total), ""]
    else:
        lines += _topic_lines(result, 500)
    lines += [
        "IELTS BAND: <b>%s</b>" % fmt_band(result.band),
        "",
        "📅 %s" % dates.fmt_long(result.local_date),
        "#IELTS #%s" % name,
    ]
    return "\n".join(lines)


def build_result_text(result: Result) -> str:
    """Rasmsiz yuboriladigan matnli post."""
    _emoji, _upper, name = SKILL_INFO[result.skill]
    lines = [_header(result, " RESULT"), ""]
    if result.total is not None:
        lines += ["<b>%d / %d</b>" % (result.correct, result.total), ""]
    else:
        lines += _topic_lines(result, 1500)
    lines += [
        "IELTS Band: <b>%s</b>" % fmt_band(result.band),
        "",
        "📅 %s" % dates.fmt_long(result.local_date),
        "📚 IELTS Daily Practice",
        "✅ %s completed" % name,
        "#IELTS #%s" % name,
    ]
    return "\n".join(lines)


async def publish_result(bot: Bot, channel_id: int, result: Result) -> int:
    if result.photo_file_id:
        message = await bot.send_photo(channel_id, photo=result.photo_file_id, caption=build_result_caption(result))
    else:
        message = await bot.send_message(channel_id, build_result_text(result))
    return message.message_id


# ---------------------------------------------------------------- countdown
def countdown_text(exam_date: dt.date, today: dt.date) -> Optional[str]:
    left = (exam_date - today).days
    if left < 0:
        return None
    if left == 0:
        headline = "🎯 <b>EXAM DAY IS TODAY!</b>"
        motto = "Good luck! You've got this. 💪"
        closing = "Trust your preparation."
    else:
        headline = "<b>%d %s LEFT</b>" % (left, "DAY" if left == 1 else "DAYS")
        motto = "Your IELTS journey continues!"
        closing = "One day closer to your exam."
    return "\n".join([
        "⏳ <b>IELTS EXAM COUNTDOWN</b>",
        "",
        headline,
        "",
        motto,
        "",
        "📅 <b>Exam date</b>",
        dates.fmt_long(exam_date),
        "",
        "🗓 <b>Today's date</b>",
        dates.fmt_long(today),
        "",
        closing,
        "#IELTS #Countdown",
    ])


async def publish_countdown(bot: Bot, channel_id: int, exam_date: dt.date, today: dt.date) -> Optional[int]:
    text = countdown_text(exam_date, today)
    if text is None:
        return None
    message = await bot.send_message(channel_id, text)
    return message.message_id


# ---------------------------------------------------------------- channel connect
def extract_channel_ref(message: Message) -> Optional[Union[int, str]]:
    """Kanal tanlash tugmasi, forward qilingan post, @username yoki ID dan kanalni aniqlaydi."""
    shared = getattr(message, "chat_shared", None)
    if shared is not None:
        return shared.chat_id
    origin = getattr(message, "forward_origin", None)
    if origin is not None and getattr(origin, "chat", None) is not None:
        return origin.chat.id
    forward_chat = getattr(message, "forward_from_chat", None)
    if forward_chat is not None:
        return forward_chat.id
    return parse_channel_ref(message.text)


async def verify_channel(bot: Bot, ref: Union[int, str]) -> Tuple[Optional[Chat], Optional[str]]:
    try:
        chat = await bot.get_chat(ref)
    except TelegramAPIError:
        return None, (
            "Kanal topilmadi yoki bot unga qo‘shilmagan.\n"
            "Botni kanalga <b>admin</b> qilib qo‘shing va qayta urinib ko‘ring."
        )
    if chat.type != "channel":
        return None, "Bu kanal emas. Iltimos, Telegram <b>kanal</b>ini ulang."
    try:
        member = await bot.get_chat_member(chat.id, bot.id)
    except TelegramAPIError:
        return None, "Bot kanal a'zolari ro‘yxatida yo‘q. Uni kanalga admin qilib qo‘shing."
    status = getattr(member.status, "value", member.status)
    if status == "creator":
        return chat, None
    if status == "administrator":
        if getattr(member, "can_post_messages", True) is False:
            return None, "Botda <b>Post messages</b> huquqi yo‘q. Kanal sozlamalarida yoqing."
        return chat, None
    return None, "Bot kanalda admin emas. Uni admin qilib, <b>Post messages</b> huquqini bering."


def channel_display(title: Optional[str], username: Optional[str], channel_id: Optional[int]) -> str:
    if not channel_id:
        return "ulanmagan"
    name = html.escape(title or "Kanal")
    if username:
        return "%s (@%s)" % (name, html.escape(username))
    return "%s (<code>%s</code>)" % (name, channel_id)
