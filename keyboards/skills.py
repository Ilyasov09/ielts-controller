"""Daily Report va skill hisobotlari klaviaturalari."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from keyboards.main import BTN_CANCEL, BTN_SKIP, chunk, ikb

BAND_CHOICES = ("4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0", "7.5", "8.0", "8.5", "9.0")
SKILL_NAMES = {
    "listening": "🎧 Listening",
    "reading": "📖 Reading",
    "writing": "✍️ Writing",
    "speaking": "🎙 Speaking",
}


def daily_report_kb() -> InlineKeyboardMarkup:
    return ikb([
        [("📖 Reading", "sk:reading"), ("🎧 Listening", "sk:listening")],
        [("✍️ Writing", "sk:writing"), ("🎙 Speaking", "sk:speaking")],
    ])


def total_kb() -> InlineKeyboardMarkup:
    return ikb([[("40", "tot:40")], [(BTN_CANCEL, "cancel")]])


def writing_task_kb() -> InlineKeyboardMarkup:
    return ikb([[("Task 1", "wt:1"), ("Task 2", "wt:2")], [(BTN_CANCEL, "cancel")]])


def speaking_part_kb() -> InlineKeyboardMarkup:
    return ikb([[("Part 1", "sp:1"), ("Part 2", "sp:2"), ("Part 3", "sp:3")], [(BTN_CANCEL, "cancel")]])


def topic_kb() -> InlineKeyboardMarkup:
    return ikb([[(BTN_SKIP, "topic:skip")], [(BTN_CANCEL, "cancel")]])


def band_kb() -> InlineKeyboardMarkup:
    rows = chunk([(value, "band:" + value) for value in BAND_CHOICES], 4)
    rows.append([(BTN_CANCEL, "cancel")])
    return ikb(rows)


def minutes_kb() -> InlineKeyboardMarkup:
    return ikb([
        [("20", "min:20"), ("30", "min:30"), ("40", "min:40"), ("60", "min:60")],
        [("90", "min:90"), ("120", "min:120")],
        [(BTN_SKIP, "min:skip")],
        [(BTN_CANCEL, "cancel")],
    ])


def photo_kb() -> InlineKeyboardMarkup:
    return ikb([[(BTN_SKIP, "photo:skip")], [(BTN_CANCEL, "cancel")]])


def after_result_kb(skill: str) -> InlineKeyboardMarkup:
    return ikb([
        [("🔁 Yana " + SKILL_NAMES[skill].split(" ", 1)[1], "sk:" + skill)],
        [("📚 Daily Report", "daily:open")],
    ])
