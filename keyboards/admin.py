"""Settings, Statistics, Countdown, Streak, History, Planner klaviaturalari."""
from __future__ import annotations

import datetime as dt
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from aiogram.types import InlineKeyboardMarkup

from database.models import Result
from keyboards.main import BTN_CANCEL, ikb
from services.channel import result_short
from services.planner import GOAL_KEYS, GOAL_LABELS
from utils import dates


# ---------------------------------------------------------------- settings
def settings_kb() -> InlineKeyboardMarkup:
    return ikb([
        [("📢 Kanal", "set:channel"), ("📅 Imtihon sanasi", "set:exam")],
        [("🕘 Report vaqti", "set:report"), ("⏳ Countdown vaqti", "set:countdown")],
        [("🔔 Kechki eslatma", "set:reminder"), ("📊 Haftalik hisobot", "wk:menu")],
        [("🛌 Dam olish kunlari", "rest:menu")],
    ])


def exam_date_kb(has_date: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_date:
        rows.append([("🗑 Sanani o‘chirish", "set:exam_clear")])
    rows.append([(BTN_CANCEL, "cancel")])
    return ikb(rows)


def time_kb(prefix: str, choices: Sequence[str],
            extra: Sequence[Sequence[Tuple[str, str]]] = ()) -> InlineKeyboardMarkup:
    rows = [[(c, "%s:%s" % (prefix, c.replace(":", ""))) for c in choices]]
    rows += [list(row) for row in extra]
    rows.append([(BTN_CANCEL, "cancel")])
    return ikb(rows)


def weekly_kb(enabled: bool, day: int, time_value: str) -> InlineKeyboardMarkup:
    days = [(("✅ " if i == day else "") + dates.WEEKDAYS_SHORT[i], "wk:day:%d" % i) for i in range(7)]
    return ikb([
        [("🟢 Yoqilgan — o‘chirish" if enabled else "⚪️ O‘chirilgan — yoqish", "wk:toggle")],
        days[:4],
        days[4:],
        [("⏰ Vaqt: %s" % time_value, "wk:time")],
        [("👁 Ko‘rish (menga)", "wk:preview"), ("📤 Hozir kanalga", "wk:send")],
        [("⬅️ Settings", "set:open")],
    ])


# ---------------------------------------------------------------- countdown
def countdown_kb(has_date: bool) -> InlineKeyboardMarkup:
    rows = [[("📅 Sanani o‘zgartirish", "set:exam"), ("⏰ Post vaqti", "set:countdown")]]
    if has_date:
        rows.append([("📤 Hozir kanalga yuborish", "cd:send")])
    return ikb(rows)


# ---------------------------------------------------------------- statistics / export
def stats_menu_kb() -> InlineKeyboardMarkup:
    return ikb([
        [("📅 Daily", "st:daily"), ("🗓 Weekly", "st:weekly")],
        [("📆 Monthly", "st:monthly"), ("🔎 Custom", "st:custom")],
    ])


def stats_result_kb(start: dt.date, end: dt.date) -> InlineKeyboardMarkup:
    span = "%s:%s" % (dates.fmt_compact(start), dates.fmt_compact(end))
    return ikb([
        [("📈 Grafik", "gr:" + span)],
        [("📄 PDF", "xp:pdf:" + span), ("📊 Excel", "xp:xlsx:" + span)],
        [("⬅️ Statistics", "st:menu")],
    ])


def export_menu_kb() -> InlineKeyboardMarkup:
    return ikb([
        [("Bugun", "ex:daily"), ("7 kun", "ex:weekly"), ("30 kun", "ex:monthly")],
        [("Barchasi", "ex:all"), ("🔎 Custom", "ex:custom")],
    ])


def export_format_kb(start: dt.date, end: dt.date) -> InlineKeyboardMarkup:
    span = "%s:%s" % (dates.fmt_compact(start), dates.fmt_compact(end))
    return ikb([
        [("📄 PDF", "xp:pdf:" + span), ("📊 Excel", "xp:xlsx:" + span)],
        [("⬅️ Orqaga", "ex:menu")],
    ])


# ---------------------------------------------------------------- streak / rest days
def streak_kb() -> InlineKeyboardMarkup:
    return ikb([[("🛌 Dam olish kunlari", "rest:menu")], [("🔄 Yangilash", "streak:open")]])


def rest_kb(weekdays: Set[int], upcoming: Iterable[dt.date]) -> InlineKeyboardMarkup:
    toggles = [
        (("✅ " if i in weekdays else "") + dates.WEEKDAYS_SHORT[i], "rest:wd:%d" % i) for i in range(7)
    ]
    rows: List[List[Tuple[str, str]]] = [toggles[:4], toggles[4:], [("➕ Sana qo‘shish", "rest:add")]]
    for day in upcoming:
        rows.append([("🗑 %s (%s)" % (dates.fmt_short(day), dates.WEEKDAYS_SHORT[day.weekday()]),
                      "rest:del:" + dates.fmt_compact(day))])
    rows.append([("⬅️ Streak", "streak:open")])
    return ikb(rows)


# ---------------------------------------------------------------- history
def history_kb(results: Sequence[Result], page: int, pages: int) -> InlineKeyboardMarkup:
    rows: List[List[Tuple[str, str]]] = [[(result_short(r), "hist:view:%d:%d" % (r.id, page))] for r in results]
    nav = []
    if page > 0:
        nav.append(("⬅️", "hist:page:%d" % (page - 1)))
    if pages > 1:
        nav.append(("%d / %d" % (page + 1, pages), "noop"))
    if page < pages - 1:
        nav.append(("➡️", "hist:page:%d" % (page + 1)))
    rows.append(nav)
    return ikb(rows)


def history_item_kb(result_id: int, page: int) -> InlineKeyboardMarkup:
    return ikb([
        [("🗑 O‘chirish", "hist:del:%d:%d" % (result_id, page))],
        [("⬅️ Orqaga", "hist:page:%d" % page)],
    ])


def history_delete_kb(result_id: int, page: int, has_post: bool) -> InlineKeyboardMarkup:
    rows = [[("🗄 Faqat bazadan", "hist:delc:%d:%d:db" % (result_id, page))]]
    if has_post:
        rows.append([("🗄+📢 Bazadan va kanaldan", "hist:delc:%d:%d:all" % (result_id, page))])
    rows.append([("⬅️ Yo‘q, qaytish", "hist:view:%d:%d" % (result_id, page))])
    return ikb(rows)


# ---------------------------------------------------------------- planner
def planner_kb(goals: Dict[str, int]) -> InlineKeyboardMarkup:
    rows = [[("%s: %d" % (GOAL_LABELS[key], goals.get(key, 0)), "pl:set:" + key)] for key in GOAL_KEYS]
    return ikb(rows)
