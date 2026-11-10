"""✍️ Writing hisobot: Task → mavzu → band → vaqt → rasm → post."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

from handlers.common import drop_keyboard, reply_target
from handlers.report_flow import ask_minutes
from handlers.states import WritingForm
from keyboards.skills import band_kb, topic_kb, writing_task_kb
from utils.validators import parse_band

router = Router(name="writing")

TOPIC_LIMIT = 500


async def ask_topic(message: Message, state: FSMContext, topic_state: State, prompt: str) -> None:
    await state.set_state(topic_state)
    await message.answer(prompt, reply_markup=topic_kb())


async def accept_topic(message: Message, state: FSMContext, topic, band_state: State) -> None:
    await state.update_data(topic=topic)
    await state.set_state(band_state)
    await message.answer(
        "<b>3-qadam</b>\n🏅 Olingan IELTS band?\n<i>Tugmani bosing yoki yozing (0–9, masalan 6.5)</i>",
        reply_markup=band_kb(),
    )


async def accept_band(message: Message, state: FSMContext, raw: str) -> None:
    band = parse_band(raw)
    if band is None:
        await message.answer("❗ Band 0 dan 9 gacha, 0.5 qadamda bo‘lishi kerak. Masalan: <b>6.5</b>", reply_markup=band_kb())
        return
    await state.update_data(band=band)
    await ask_minutes(message, state, step=4)


def clean_topic(text) -> str:
    return " ".join((text or "").split())


@router.callback_query(F.data == "sk:writing")
async def start_writing(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.update_data(skill="writing")
    await state.set_state(WritingForm.task)
    await reply_target(callback).answer(
        "✍️ <b>WRITING REPORT</b>\n\n<b>1-qadam</b>\nQaysi task?",
        reply_markup=writing_task_kb(),
    )


@router.callback_query(WritingForm.task, F.data.startswith("wt:"))
async def writing_task(callback: CallbackQuery, state: FSMContext) -> None:
    task = "Task " + callback.data.split(":", 1)[1]
    await callback.answer(task)
    await drop_keyboard(callback)
    await state.update_data(task=task)
    await ask_topic(
        reply_target(callback), state, WritingForm.topic,
        "Tanlandi: <b>%s</b>\n\n<b>2-qadam</b>\n📝 Essay mavzusini yuboring:" % task,
    )


@router.message(WritingForm.task)
async def writing_task_text(message: Message) -> None:
    await message.answer("Iltimos, taskni tugma orqali tanlang:", reply_markup=writing_task_kb())


@router.callback_query(WritingForm.topic, F.data == "topic:skip")
async def writing_topic_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await drop_keyboard(callback)
    await accept_topic(reply_target(callback), state, None, WritingForm.band)


@router.message(WritingForm.topic)
async def writing_topic(message: Message, state: FSMContext) -> None:
    topic = clean_topic(message.text)
    if not topic:
        await message.answer("❗ Mavzuni matn ko‘rinishida yuboring yoki o‘tkazib yuboring.", reply_markup=topic_kb())
        return
    if len(topic) > TOPIC_LIMIT:
        await message.answer("❗ Mavzu juda uzun (maksimum %d belgi). Qisqartirib yuboring." % TOPIC_LIMIT)
        return
    await accept_topic(message, state, topic, WritingForm.band)


@router.callback_query(WritingForm.band, F.data.startswith("band:"))
async def writing_band_button(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await drop_keyboard(callback)
    await accept_band(reply_target(callback), state, callback.data.split(":", 1)[1])


@router.message(WritingForm.band)
async def writing_band_text(message: Message, state: FSMContext) -> None:
    await accept_band(message, state, message.text or "")
