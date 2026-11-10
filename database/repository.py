"""Bazaga so‘rovlar (CRUD)."""
from __future__ import annotations

import datetime as dt
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import BotSettings, Poll, PollOption, PollVote, RestDay, Result

SKILLS = ("listening", "reading", "writing", "speaking")


# ---------------------------------------------------------------- settings
async def get_settings(session: AsyncSession) -> BotSettings:
    settings = await session.get(BotSettings, 1)
    if settings is None:
        settings = BotSettings(
            id=1,
            report_time=config.default_report_time,
            countdown_time=config.default_countdown_time,
            rest_weekdays="",
            goal_listening=0,
            goal_reading=0,
            goal_writing=0,
            goal_speaking=0,
            goal_minutes=0,
            reminder_time="22:00",
            weekly_enabled=True,
            weekly_day=6,
            weekly_time="20:00",
            onboarded=False,
        )
        session.add(settings)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            settings = await session.get(BotSettings, 1)
    return settings


def get_rest_weekdays(settings: BotSettings) -> Set[int]:
    result = set()
    for part in (settings.rest_weekdays or "").split(","):
        part = part.strip()
        if part.isdigit() and 0 <= int(part) <= 6:
            result.add(int(part))
    return result


def set_rest_weekdays(settings: BotSettings, days: Iterable[int]) -> None:
    settings.rest_weekdays = ",".join(str(d) for d in sorted(set(days)))


def get_goals(settings: BotSettings) -> Dict[str, int]:
    return {
        "listening": settings.goal_listening or 0,
        "reading": settings.goal_reading or 0,
        "writing": settings.goal_writing or 0,
        "speaking": settings.goal_speaking or 0,
        "minutes": settings.goal_minutes or 0,
    }


# ---------------------------------------------------------------- results
async def results_between(session: AsyncSession, start: dt.date, end: dt.date) -> List[Result]:
    stmt = (
        select(Result)
        .where(Result.local_date >= start, Result.local_date <= end)
        .order_by(Result.created_at, Result.id)
    )
    return list((await session.scalars(stmt)).all())


async def results_page(session: AsyncSession, offset: int, limit: int) -> Tuple[List[Result], int]:
    total = await session.scalar(select(func.count(Result.id))) or 0
    stmt = select(Result).order_by(Result.created_at.desc(), Result.id.desc()).offset(offset).limit(limit)
    return list((await session.scalars(stmt)).all()), int(total)


async def get_result(session: AsyncSession, result_id: int) -> Optional[Result]:
    return await session.get(Result, result_id)


async def delete_result(session: AsyncSession, result: Result) -> None:
    await session.delete(result)
    await session.commit()


async def active_dates(session: AsyncSession) -> Set[dt.date]:
    rows = await session.scalars(select(Result.local_date).distinct())
    return set(rows.all())


async def first_result_date(session: AsyncSession) -> Optional[dt.date]:
    return await session.scalar(select(func.min(Result.local_date)))


async def count_skill_on(session: AsyncSession, skill: str, day: dt.date) -> int:
    stmt = select(func.count(Result.id)).where(Result.skill == skill, Result.local_date == day)
    return int(await session.scalar(stmt) or 0)


# ---------------------------------------------------------------- rest days
async def rest_dates(session: AsyncSession) -> Set[dt.date]:
    rows = await session.scalars(select(RestDay.day))
    return set(rows.all())


async def upcoming_rest_dates(session: AsyncSession, from_day: dt.date, limit: int = 12) -> List[dt.date]:
    stmt = select(RestDay.day).where(RestDay.day >= from_day).order_by(RestDay.day).limit(limit)
    return list((await session.scalars(stmt)).all())


async def add_rest_date(session: AsyncSession, day: dt.date) -> bool:
    exists = await session.scalar(select(RestDay.id).where(RestDay.day == day))
    if exists:
        return False
    session.add(RestDay(day=day))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def remove_rest_date(session: AsyncSession, day: dt.date) -> None:
    await session.execute(delete(RestDay).where(RestDay.day == day))
    await session.commit()


# ---------------------------------------------------------------- polls
async def create_poll(session: AsyncSession, text: str, options: List[str]) -> Poll:
    poll = Poll(text=text)
    session.add(poll)
    await session.flush()
    for position, option_text in enumerate(options):
        session.add(PollOption(poll_id=poll.id, text=option_text, position=position))
    await session.commit()
    return poll


async def get_poll(session: AsyncSession, poll_id: int) -> Optional[Poll]:
    return await session.get(Poll, poll_id)


async def recent_polls(session: AsyncSession, limit: int = 10) -> List[Poll]:
    stmt = (
        select(Poll)
        .where(Poll.message_id.is_not(None))
        .order_by(Poll.closed, Poll.created_at.desc(), Poll.id.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def poll_voter_count(session: AsyncSession, poll_id: int) -> int:
    return int(await session.scalar(select(func.count(PollVote.id)).where(PollVote.poll_id == poll_id)) or 0)


async def poll_options(session: AsyncSession, poll_id: int) -> List[PollOption]:
    stmt = select(PollOption).where(PollOption.poll_id == poll_id).order_by(PollOption.position, PollOption.id)
    return list((await session.scalars(stmt)).all())


async def poll_counts(session: AsyncSession, poll_id: int) -> Dict[int, int]:
    stmt = (
        select(PollVote.option_id, func.count(PollVote.id))
        .where(PollVote.poll_id == poll_id)
        .group_by(PollVote.option_id)
    )
    return {option_id: int(count) for option_id, count in (await session.execute(stmt)).all()}


async def cast_vote(session: AsyncSession, poll_id: int, option_id: int, user_id: int) -> Tuple[str, Optional[PollOption]]:
    """Ovoz berish. Natija: 'new', 'changed', 'same' yoki 'invalid'."""
    option = await session.get(PollOption, option_id)
    if option is None or option.poll_id != poll_id:
        return "invalid", None
    poll = await session.get(Poll, poll_id)
    if poll is not None and poll.closed:
        return "closed", option
    for _attempt in range(3):
        vote = await session.scalar(
            select(PollVote).where(PollVote.poll_id == poll_id, PollVote.user_id == user_id)
        )
        if vote is None:
            session.add(PollVote(poll_id=poll_id, option_id=option_id, user_id=user_id))
            try:
                await session.commit()
                return "new", option
            except IntegrityError:  # parallel bosilgan — qayta urinamiz
                await session.rollback()
                continue
        if vote.option_id == option_id:
            return "same", option
        vote.option_id = option_id
        vote.voted_at = dt.datetime.now(dt.timezone.utc)
        await session.commit()
        return "changed", option
    return "same", option
