"""Routerlar — tartib muhim: bekor qilish va menyu birinchi, fallback oxirida."""
from __future__ import annotations

from typing import List

from aiogram import Router


def get_routers() -> List[Router]:
    from handlers import (
        broadcast,
        common,
        countdown,
        daily,
        fallback,
        history,
        listening,
        menu,
        planner,
        poll,
        reading,
        report_flow,
        settings,
        speaking,
        start,
        statistics,
        streak,
        writing,
    )

    return [
        common.router,
        start.router,
        menu.router,
        daily.router,
        listening.router,
        reading.router,
        writing.router,
        speaking.router,
        report_flow.router,
        countdown.router,
        statistics.router,
        streak.router,
        history.router,
        planner.router,
        poll.router,
        broadcast.router,
        settings.router,
        fallback.router,
    ]
