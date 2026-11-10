"""🎙 Speaking hisobot: Part → mavzu → band → vaqt → rasm → post."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.common import drop_keyboard, reply_target
from handlers.states import SpeakingForm
from handlers.writing import TOPIC_LIMIT, accept_band, accept_topic, ask_topic, clean_topic
from keyboards.skills import speaking_part_kb, topic_kb

router = Router(name="speaking")


@router.callback_query(F.data == "sk:speaking")
async def start_speaking(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.update_data(skill="speaking")
    await state.set_state(SpeakingForm.part)
    await reply_target(callback).answer(
        "🎙 <b>SPEAKING REPORT</b>\n\n<b>1-qadam</b>\nQaysi part?",
        reply_markup=speaking_part_kb(),
    )


@router.callback_query(SpeakingForm.part, F.data.startswith("sp:"))
async def speaking_part(callback: CallbackQuery, state: FSMContext) -> None:
    part = "Part " + callback.data.split(":", 1)[1]
    await callback.answer(part)
    await drop_keyboard(callback)
    await state.update_data(task=part)
    await ask_topic(
        reply_target(callback), state, SpeakingForm.topic,
        "Tanlandi: <b>%s</b>\n\n<b>2-qadam</b>\n💬 Mavzuni yuboring:" % part,
    )


@router.message(SpeakingForm.part)
async def speaking_part_text(message: Message) -> None:
    await message.answer("Iltimos, partni tugma orqali tanlang:", reply_markup=speaking_part_kb())


@router.callback_query(SpeakingForm.topic, F.data == "topic:skip")
async def speaking_topic_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await drop_keyboard(callback)
    await accept_topic(reply_target(callback), state, None, SpeakingForm.band)


@router.message(SpeakingForm.topic)
async def speaking_topic(message: Message, state: FSMContext) -> None:
    topic = clean_topic(message.text)
    if not topic:
        await message.answer("❗ Mavzuni matn ko‘rinishida yuboring yoki o‘tkazib yuboring.", reply_markup=topic_kb())
        return
    if len(topic) > TOPIC_LIMIT:
        await message.answer("❗ Mavzu juda uzun (maksimum %d belgi). Qisqartirib yuboring." % TOPIC_LIMIT)
        return
    await accept_topic(message, state, topic, SpeakingForm.band)


@router.callback_query(SpeakingForm.band, F.data.startswith("band:"))
async def speaking_band_button(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await drop_keyboard(callback)
    await accept_band(reply_target(callback), state, callback.data.split(":", 1)[1])


@router.message(SpeakingForm.band)
async def speaking_band_text(message: Message, state: FSMContext) -> None:
    await accept_band(message, state, message.text or "")
