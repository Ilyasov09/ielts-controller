"""Umumiy yordamchilar va bekor qilish."""
from __future__ import annotations

import logging
from typing import Optional, Union

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from handlers.states import BroadcastForm
from keyboards.main import BTN_CANCEL, main_menu_kb

log = logging.getLogger(__name__)
router = Router(name="common")

Target = Union[Message, CallbackQuery]


async def render(target: Target, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    """Callback bo‘lsa xabarni tahrirlaydi, aks holda yangi xabar yuboradi."""
    if isinstance(target, CallbackQuery):
        message = target.message
        if isinstance(message, Message) and message.text is not None:
            try:
                await message.edit_text(text, reply_markup=reply_markup)
                return
            except TelegramBadRequest as exc:
                if "not modified" in str(exc).lower():
                    return
        await target.bot.send_message(target.from_user.id, text, reply_markup=reply_markup)
        return
    await target.answer(text, reply_markup=reply_markup)


async def drop_keyboard(callback: CallbackQuery) -> None:
    """Bosilgan inline tugmalarni olib tashlaydi (qayta bosilmasligi uchun)."""
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass


def reply_target(callback: CallbackQuery) -> Message:
    message = callback.message
    if isinstance(message, Message):
        return message
    raise RuntimeError("Callback message is not accessible")


@router.message(Command("cancel"))
@router.message(F.text == BTN_CANCEL)
async def cancel_message(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await state.clear()
    if current is None:
        text = "Bekor qilinadigan amal yo‘q."
    elif current == BroadcastForm.active.state:
        text = "📢 Broadcast rejimi yopildi."
    else:
        text = "❌ Amal bekor qilindi."
    await message.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Bekor qilindi")
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        await callback.message.answer("❌ Amal bekor qilindi.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()
