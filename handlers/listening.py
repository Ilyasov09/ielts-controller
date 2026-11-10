"""🎧 Listening hisobot: savollar soni → to‘g‘ri javoblar → vaqt → rasm → post."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.common import drop_keyboard, reply_target
from handlers.report_flow import accept_correct, accept_total, ask_total
from handlers.states import ListeningForm

router = Router(name="listening")


@router.callback_query(F.data == "sk:listening")
async def start_listening(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.update_data(skill="listening")
    message = reply_target(callback)
    await message.answer("🎧 <b>LISTENING REPORT</b>")
    await ask_total(message, state, ListeningForm.total, step=1)


@router.callback_query(ListeningForm.total, F.data.startswith("tot:"))
async def total_button(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await drop_keyboard(callback)
    await accept_total(reply_target(callback), state, callback.data.split(":", 1)[1], ListeningForm.correct)


@router.message(ListeningForm.total)
async def total_message(message: Message, state: FSMContext) -> None:
    await accept_total(message, state, message.text or "", ListeningForm.correct)


@router.message(ListeningForm.correct)
async def correct_message(message: Message, state: FSMContext) -> None:
    await accept_correct(message, state, message.text or "")
