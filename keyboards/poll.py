"""Poll Creator klaviaturalari."""
from __future__ import annotations

import re
from typing import Dict, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Poll, PollOption
from keyboards.main import BTN_CANCEL, ikb

COLUMNS = 3


def _label(text: str, count: int) -> str:
    return "%s (%d)" % (text, count)


def vote_kb(poll_id: int, options: Sequence[PollOption], counts: Dict[int, int]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=_label(o.text, counts.get(o.id, 0)), callback_data="pv:%d:%d" % (poll_id, o.id))
        for o in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i:i + COLUMNS] for i in range(0, len(buttons), COLUMNS)])


def preview_kb(options: Sequence[str]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=_label(text, 0), callback_data="noop") for text in options]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i:i + COLUMNS] for i in range(0, len(buttons), COLUMNS)])


def builder_kb(option_count: int) -> InlineKeyboardMarkup:
    rows = [[("➕ Tugma qo‘shish", "poll:add"), ("✅ Tayyor", "poll:done")]]
    if option_count:
        rows.append([("↩️ Oxirgisini o‘chirish", "poll:undo")])
    rows.append([(BTN_CANCEL, "cancel")])
    return ikb(rows)


def poll_menu_kb(polls: Sequence[Poll], voters: Dict[int, int]) -> InlineKeyboardMarkup:
    rows = [[("➕ Yangi poll", "poll:new")]]
    for poll in polls:
        title = re.sub(r"<[^>]+>", "", poll.text).replace("\n", " ").strip()
        if len(title) > 32:
            title = title[:31].rstrip() + "…"
        rows.append([("%s %s (%d)" % ("🔒" if poll.closed else "🟢", title, voters.get(poll.id, 0)),
                      "pm:view:%d" % poll.id)])
    return ikb(rows)


def poll_manage_kb(poll: Poll, link: str = "") -> InlineKeyboardMarkup:
    rows = []
    if not poll.closed:
        rows.append([("🔒 Pollni yopish", "pm:close:%d" % poll.id)])
    rows.append([("🔄 Yangilash", "pm:view:%d" % poll.id), ("⬅️ Ro‘yxat", "pm:list")])
    markup = ikb(rows)
    if link:
        markup.inline_keyboard.insert(0, [InlineKeyboardButton(text="🔗 Kanalda ochish", url=link)])
    return markup


def poll_close_confirm_kb(poll_id: int) -> InlineKeyboardMarkup:
    return ikb([
        [("✅ Ha, yopish", "pm:closec:%d" % poll_id)],
        [("⬅️ Yo‘q", "pm:view:%d" % poll_id)],
    ])


def confirm_kb() -> InlineKeyboardMarkup:
    return ikb([
        [("📤 Kanalga yuborish", "poll:send")],
        [("✏️ Tugmalarni tahrirlash", "poll:edit")],
        [(BTN_CANCEL, "cancel")],
    ])
