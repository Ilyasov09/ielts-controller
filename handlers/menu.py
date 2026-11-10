"""Asosiy menyu tugmalari va buyruqlar.

Bu router boshqa holat (FSM) handlerlaridan OLDIN ulanadi — shuning uchun istalgan
bosqichda menyu tugmasini bossangiz, joriy amal to‘xtaydi va yangi bo‘lim ochiladi.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.broadcast import start_broadcast
from handlers.countdown import show_countdown
from handlers.daily import show_daily_report
from handlers.history import show_history
from handlers.planner import show_planner
from handlers.poll import show_poll_menu, start_poll
from handlers.settings import show_settings
from handlers.start import status_text
from handlers.states import BroadcastForm
from handlers.statistics import show_export_menu, show_statistics_menu
from handlers.streak import show_streak
from keyboards.main import (
    BTN_BROADCAST,
    BTN_COUNTDOWN,
    BTN_DAILY,
    BTN_EXPORT,
    BTN_HISTORY,
    BTN_PLANNER,
    BTN_POLL,
    BTN_SETTINGS,
    BTN_STATS,
    BTN_STREAK,
    main_menu_kb,
)

router = Router(name="menu")


async def _reset(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await state.clear()
    if current == BroadcastForm.active.state:
        await message.answer("📢 Broadcast rejimi yopildi.", reply_markup=main_menu_kb())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await message.answer(await status_text(session), reply_markup=main_menu_kb())


@router.message(Command("daily", "report"))
@router.message(F.text == BTN_DAILY)
async def menu_daily(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _reset(message, state)
    await show_daily_report(message, session)


@router.message(Command("stats"))
@router.message(F.text == BTN_STATS)
async def menu_stats(message: Message, state: FSMContext) -> None:
    await _reset(message, state)
    await show_statistics_menu(message)


@router.message(Command("countdown"))
@router.message(F.text == BTN_COUNTDOWN)
async def menu_countdown(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _reset(message, state)
    await show_countdown(message, session)


@router.message(Command("streak"))
@router.message(F.text == BTN_STREAK)
async def menu_streak(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _reset(message, state)
    await show_streak(message, session)


@router.message(Command("history"))
@router.message(F.text == BTN_HISTORY)
async def menu_history(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _reset(message, state)
    await show_history(message, session)


@router.message(Command("planner"))
@router.message(F.text == BTN_PLANNER)
async def menu_planner(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _reset(message, state)
    await show_planner(message, session)


@router.message(Command("poll"))
async def menu_poll_new(message: Message, state: FSMContext) -> None:
    await _reset(message, state)
    await start_poll(message, state)


@router.message(Command("polls"))
@router.message(F.text == BTN_POLL)
async def menu_poll(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _reset(message, state)
    await show_poll_menu(message, session)


@router.message(Command("broadcast"))
@router.message(F.text == BTN_BROADCAST)
async def menu_broadcast(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _reset(message, state)
    await start_broadcast(message, state, session)


@router.message(Command("export"))
@router.message(F.text == BTN_EXPORT)
async def menu_export(message: Message, state: FSMContext) -> None:
    await _reset(message, state)
    await show_export_menu(message)


@router.message(Command("settings"))
@router.message(F.text == BTN_SETTINGS)
async def menu_settings(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _reset(message, state)
    await show_settings(message, session)
