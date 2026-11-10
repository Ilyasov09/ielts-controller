"""📖 Reading hisobot (faqat Academic): savollar → to‘g‘ri → vaqt → rasm → post."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.common import drop_keyboard, reply_target
from handlers.report_flow import accept_correct, accept_total, ask_total
from handlers.states import ReadingForm

router = Router(name="reading")


@router.callback_query(F.data == "sk:reading")
async def start_reading(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.update_data(skill="reading", reading_type="academic")
    message = reply_target(callback)
    await message.answer("📖 <b>READING REPORT</b> · Academic")
    await ask_total(message, state, ReadingForm.total, step=1)


@router.callback_query(ReadingForm.total, F.data.startswith("tot:"))
async def total_button(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await drop_keyboard(callback)
    await accept_total(reply_target(callback), state, callback.data.split(":", 1)[1], ReadingForm.correct)


@router.message(ReadingForm.total)
async def total_message(message: Message, state: FSMContext) -> None:
    await accept_total(message, state, message.text or "", ReadingForm.correct)


@router.message(ReadingForm.correct)
async def correct_message(message: Message, state: FSMContext) -> None:
    await accept_correct(message, state, message.text or "")
