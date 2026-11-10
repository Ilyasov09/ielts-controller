"""Streak hisoblash.

Qoidalar:
* Kun ichida kamida bitta skill natijasi kiritilsa — kun "faol".
* Faol bo‘lmagan oddiy kun streakni uzadi.
* Dam olish kuni (haftalik yoki oldindan belgilangan sana) streakni uzmaydi va oshirmaydi;
  agar dam olish kunida ham natija kiritilsa — u faol kun sifatida hisoblanadi.
* Bugun hali tugamagan — bugun hisobot bo‘lmasa streak uzilgan hisoblanmaydi.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from database.repository import active_dates, get_rest_weekdays, get_settings, rest_dates
from utils import dates

MILESTONES = (7, 30, 60, 100)
ONE_DAY = dt.timedelta(days=1)


@dataclass
class StreakInfo:
    current: int = 0
    longest: int = 0
    total_active: int = 0
    submission_rate: Optional[float] = None
    today_done: bool = False
    today_rest: bool = False
    milestones: Dict[int, bool] = field(default_factory=dict)

    @property
    def next_milestone(self) -> Optional[int]:
        for value in MILESTONES:
            if self.current < value:
                return value
        return None


def is_rest_day(day: dt.date, rest: Set[dt.date], rest_weekdays: Set[int]) -> bool:
    return day in rest or day.weekday() in rest_weekdays


def compute_streak(
    active: Set[dt.date],
    rest: Set[dt.date],
    rest_weekdays: Set[int],
    today: dt.date,
) -> StreakInfo:
    active = {d for d in active if d <= today}
    info = StreakInfo(
        today_done=today in active,
        today_rest=is_rest_day(today, rest, rest_weekdays),
    )
    if not active:
        info.milestones = {m: False for m in MILESTONES}
        return info

    first = min(active)
    info.total_active = len(active)

    # Joriy streak — orqaga qarab sanaymiz
    day = today if today in active else today - ONE_DAY
    current = 0
    while day >= first:
        if day in active:
            current += 1
        elif not is_rest_day(day, rest, rest_weekdays):
            break
        day -= ONE_DAY
    info.current = current

    # Eng uzun streak va topshirish foizi
    longest = run = 0
    expected = 0
    for day in dates.iter_days(first, today):
        if day in active:
            run += 1
            expected += 1
            longest = max(longest, run)
        elif is_rest_day(day, rest, rest_weekdays) or day == today:
            continue
        else:
            run = 0
            expected += 1
    info.longest = longest
    info.submission_rate = (info.total_active / expected * 100.0) if expected else None
    info.milestones = {m: longest >= m for m in MILESTONES}
    return info


async def get_streak(session: AsyncSession, today: Optional[dt.date] = None) -> StreakInfo:
    settings = await get_settings(session)
    return compute_streak(
        await active_dates(session),
        await rest_dates(session),
        get_rest_weekdays(settings),
        today or dates.today(),
    )
