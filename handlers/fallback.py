"""Hech bir handlerga tushmagan xabar va eskirgan tugmalar."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from keyboards.main import main_menu_kb

router = Router(name="fallback")


@router.message(StateFilter(None))
async def unknown_message(message: Message) -> None:
    await message.answer("Quyidagi menyudan bo‘lim tanlang 👇", reply_markup=main_menu_kb())


@router.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    await callback.answer("Bu tugma eskirgan. Menyudan qaytadan boshlang.")
