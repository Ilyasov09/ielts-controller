"""Ma'lumotlar bazasi modellari (SQLAlchemy 2.0)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class BotSettings(Base):
    """Bot sozlamalari — doim bitta qator (id=1)."""

    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    channel_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    exam_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True)
    report_time: Mapped[str] = mapped_column(String(5), default="21:00", nullable=False)
    countdown_time: Mapped[str] = mapped_column(String(5), default="09:00", nullable=False)

    # Haftalik dam olish kunlari: "5,6" (0=Dushanba ... 6=Yakshanba)
    rest_weekdays: Mapped[str] = mapped_column(String(20), default="", nullable=False)

    # Study Planner — kunlik maqsadlar
    goal_listening: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    goal_reading: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    goal_writing: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    goal_speaking: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    goal_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Kechki eslatma (None — o‘chirilgan)
    reminder_time: Mapped[Optional[str]] = mapped_column(String(5), default="22:00", nullable=True)

    # Haftalik kanal hisoboti
    weekly_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weekly_day: Mapped[int] = mapped_column(Integer, default=6, nullable=False)  # 0=Du ... 6=Ya
    weekly_time: Mapped[str] = mapped_column(String(5), default="20:00", nullable=False)

    onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_countdown_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True)
    last_report_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True)
    last_reminder_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True)
    last_weekly_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Result(Base):
    """Har bir skill natijasi — har biri alohida yozuv, hech qachon ustidan yozilmaydi."""

    __tablename__ = "results"
    __table_args__ = (
        Index("ix_results_local_date", "local_date"),
        Index("ix_results_skill_date", "skill", "local_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill: Mapped[str] = mapped_column(String(16), nullable=False)  # listening/reading/writing/speaking
    local_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    reading_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # academic/general
    total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    correct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    band: Mapped[float] = mapped_column(Float, nullable=False)

    task: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # "Task 1", "Part 2"
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    channel_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class RestDay(Base):
    """Oldindan belgilangan dam olish sanalari (streak uzilmaydi)."""

    __tablename__ = "rest_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[dt.date] = mapped_column(Date, unique=True, nullable=False)


class Poll(Base):
    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    closed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PollOption(Base):
    __tablename__ = "poll_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PollVote(Base):
    """Bir foydalanuvchi bir pollda faqat bitta ovozga ega (UNIQUE)."""

    __tablename__ = "poll_votes"
    __table_args__ = (UniqueConstraint("poll_id", "user_id", name="uq_poll_votes_poll_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id: Mapped[int] = mapped_column(ForeignKey("poll_options.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    voted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
