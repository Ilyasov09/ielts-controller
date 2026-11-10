"""Asosiy menyu va umumiy klaviaturalar."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
    ReplyKeyboardMarkup,
)

BTN_DAILY = "📚 Daily Report"
BTN_STATS = "📊 Statistics"
BTN_COUNTDOWN = "⏳ Exam Countdown"
BTN_STREAK = "🔥 Streak System"
BTN_HISTORY = "🗂 History"
BTN_PLANNER = "🎯 Study Planner"
BTN_POLL = "🗳 Poll Creator"
BTN_BROADCAST = "📢 Broadcast"
BTN_EXPORT = "📤 Export Reports"
BTN_SETTINGS = "⚙️ Settings"

BTN_CANCEL = "❌ Bekor qilish"
BTN_SKIP = "⏭ O‘tkazib yuborish"
BTN_PICK_CHANNEL = "📢 Kanalni tanlash"

MENU_LAYOUT = (
    (BTN_DAILY,),
    (BTN_STATS, BTN_COUNTDOWN),
    (BTN_STREAK, BTN_HISTORY),
    (BTN_PLANNER, BTN_POLL),
    (BTN_BROADCAST, BTN_EXPORT),
    (BTN_SETTINGS,),
)

Row = Sequence[Tuple[str, str]]


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in MENU_LAYOUT],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="IELTS CONTROLLER",
    )


def reply_kb(rows: Sequence[Sequence[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def channel_pick_kb(allow_skip: bool) -> ReplyKeyboardMarkup:
    rows: List[List[KeyboardButton]] = [[
        KeyboardButton(
            text=BTN_PICK_CHANNEL,
            request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True),
        )
    ]]
    if allow_skip:
        rows.append([KeyboardButton(text=BTN_SKIP)])
    rows.append([KeyboardButton(text=BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def ikb(rows: Sequence[Row]) -> InlineKeyboardMarkup:
    """[(matn, callback_data), ...] qatorlaridan inline klaviatura yasaydi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row] for row in rows if row
        ]
    )


def chunk(items: Sequence[Tuple[str, str]], size: int) -> List[List[Tuple[str, str]]]:
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


def cancel_ikb(extra: Optional[Sequence[Row]] = None) -> InlineKeyboardMarkup:
    rows = list(extra or [])
    rows.append([(BTN_CANCEL, "cancel")])
    return ikb(rows)
