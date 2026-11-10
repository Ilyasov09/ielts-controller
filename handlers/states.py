"""FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    channel = State()
    exam_date = State()
    report_time = State()


class ListeningForm(StatesGroup):
    total = State()
    correct = State()


class ReadingForm(StatesGroup):
    total = State()
    correct = State()


class WritingForm(StatesGroup):
    task = State()
    topic = State()
    band = State()


class SpeakingForm(StatesGroup):
    part = State()
    topic = State()
    band = State()


class ReportFlow(StatesGroup):
    minutes = State()
    photo = State()


class SettingsForm(StatesGroup):
    channel = State()
    exam_date = State()
    report_time = State()
    countdown_time = State()
    reminder_time = State()
    weekly_time = State()
    rest_date = State()


class PlannerForm(StatesGroup):
    value = State()


class RangeForm(StatesGroup):
    start = State()
    end = State()


class PollForm(StatesGroup):
    text = State()
    option = State()
    preview = State()


class BroadcastForm(StatesGroup):
    active = State()
