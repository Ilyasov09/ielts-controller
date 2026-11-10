"""Rejalashtirilgan vazifalar: Daily Report menyusi, countdown, kechki eslatma, haftalik hisobot."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database.database import SessionLocal
from database.models import BotSettings
from database.repository import get_rest_weekdays, get_settings, rest_dates
from services.access import get_admin_ids
from services.channel import publish_countdown
from services.streak import get_streak, is_rest_day
from utils import dates

log = logging.getLogger(__name__)


class BotScheduler:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=dates.TZ)

    async def start(self) -> None:
        async with SessionLocal() as session:
            settings = await get_settings(session)
            self.reschedule(settings)
        self.scheduler.start()
        await self.catch_up()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    # ------------------------------------------------------------ jadval
    def _set_job(self, job_id: str, func, value: Optional[str], day_of_week: Optional[int] = None) -> None:
        try:
            self.scheduler.remove_job(job_id)
        except JobLookupError:
            pass
        if not value:
            return
        hour, minute = dates.split_time(value)
        trigger = CronTrigger(
            hour=hour, minute=minute, timezone=dates.TZ,
            day_of_week=day_of_week if day_of_week is not None else "*",
        )
        self.scheduler.add_job(
            func, trigger, id=job_id, replace_existing=True,
            misfire_grace_time=3600, coalesce=True, max_instances=1,
        )

    def reschedule(self, settings: BotSettings) -> None:
        self._set_job("daily_report", self.daily_report_job, settings.report_time)
        self._set_job("countdown", self.countdown_job, settings.countdown_time)
        self._set_job("reminder", self.reminder_job, settings.reminder_time)
        self._set_job("weekly", self.weekly_job, settings.weekly_time if settings.weekly_enabled else None,
                      day_of_week=settings.weekly_day)
        log.info(
            "Jadval: report %s, countdown %s, eslatma %s, haftalik %s",
            settings.report_time, settings.countdown_time, settings.reminder_time or "o‘chiq",
            ("%s %s" % (dates.WEEKDAYS_SHORT[settings.weekly_day], settings.weekly_time))
            if settings.weekly_enabled else "o‘chiq",
        )

    async def catch_up(self) -> None:
        """Bot belgilangan vaqtda o‘chiq bo‘lgan bo‘lsa — bugungi postlarni yuboradi."""
        now = dates.now_local()
        current = "%02d:%02d" % (now.hour, now.minute)
        today = now.date()
        async with SessionLocal() as session:
            s = await get_settings(session)
            need_countdown = s.countdown_time <= current and s.last_countdown_date != today
            need_report = s.report_time <= current and s.last_report_date != today
            need_weekly = (s.weekly_enabled and today.weekday() == s.weekly_day
                           and s.weekly_time <= current and s.last_weekly_date != today)
        if need_countdown:
            await self.countdown_job()
        if need_report:
            await self.daily_report_job()
        if need_weekly:
            await self.weekly_job()

    async def _send_admins(self, session, text: str, keyboard=None) -> int:
        sent = 0
        for admin_id in await get_admin_ids(session):
            try:
                await self.bot.send_message(admin_id, text, reply_markup=keyboard)
                sent += 1
            except TelegramAPIError as exc:
                log.warning("%s ga yuborilmadi: %s", admin_id, exc)
        return sent

    # ------------------------------------------------------------ vazifalar
    async def daily_report_job(self) -> None:
        from handlers.daily import build_daily_report

        try:
            async with SessionLocal() as session:
                settings = await get_settings(session)
                today = dates.today()
                if settings.last_report_date == today:
                    return
                text, keyboard = await build_daily_report(session)
                if await self._send_admins(session, text, keyboard):
                    settings.last_report_date = today
                    await session.commit()
        except Exception:
            log.exception("daily_report_job xatosi")

    async def reminder_job(self) -> None:
        """Kechki eslatma: bugun hisobot yo‘q bo‘lsa (va dam olish kuni bo‘lmasa)."""
        from keyboards.skills import daily_report_kb

        try:
            async with SessionLocal() as session:
                settings = await get_settings(session)
                today = dates.today()
                if not settings.reminder_time or settings.last_reminder_date == today:
                    return
                if is_rest_day(today, await rest_dates(session), get_rest_weekdays(settings)):
                    return
                streak = await get_streak(session, today)
                if streak.today_done:
                    return
                if streak.current > 0:
                    text = ("🔔 <b>Bugun hali hisobot yo‘q!</b>\n\n"
                            "🔥 <b>%d kunlik</b> streakingiz uzilmasin — kun tugashidan oldin "
                            "kamida bitta natija kiriting." % streak.current)
                else:
                    text = ("🔔 <b>Bugun hali hisobot yo‘q!</b>\n\n"
                            "Kamida bitta natija kiriting va yangi streakni boshlang 🔥")
                if await self._send_admins(session, text, daily_report_kb()):
                    settings.last_reminder_date = today
                    await session.commit()
        except Exception:
            log.exception("reminder_job xatosi")

    async def countdown_job(self, force: bool = False) -> bool:
        try:
            async with SessionLocal() as session:
                settings = await get_settings(session)
                today = dates.today()
                if not settings.channel_id or not settings.exam_date:
                    return False
                if not force and settings.last_countdown_date == today:
                    return False
                message_id = await publish_countdown(self.bot, settings.channel_id, settings.exam_date, today)
                if message_id is None:
                    return False
                settings.last_countdown_date = today
                await session.commit()
                return True
        except TelegramAPIError as exc:
            log.warning("Countdown yuborilmadi: %s", exc)
            if force:
                raise
        except Exception:
            log.exception("countdown_job xatosi")
        return False

    async def weekly_job(self, force: bool = False) -> str:
        """Natija: 'sent', 'empty', 'skipped'. force=True da Telegram xatosi tashqariga chiqadi."""
        from services.weekly import build_weekly, send_weekly

        try:
            async with SessionLocal() as session:
                settings = await get_settings(session)
                today = dates.today()
                if not settings.channel_id or (not force and (
                        not settings.weekly_enabled or settings.last_weekly_date == today)):
                    return "skipped"
                built = await build_weekly(session, today)
                if built is None:
                    log.info("Haftalik hisobot: bu hafta natija yo‘q — post yuborilmadi")
                    return "empty"
                await send_weekly(self.bot, settings.channel_id, *built)
                settings.last_weekly_date = today
                await session.commit()
                return "sent"
        except TelegramAPIError as exc:
            log.warning("Haftalik hisobot yuborilmadi: %s", exc)
            if force:
                raise
        except Exception:
            log.exception("weekly_job xatosi")
            if force:
                raise
        return "skipped"
