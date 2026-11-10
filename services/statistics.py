"""Statistika hisoblash va formatlash."""
from __future__ import annotations

import datetime as dt
import html
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Result
from database.repository import SKILLS, get_goals, get_settings, results_between
from services.band_calculator import fmt_band, round_overall, scale_to_40
from services.channel import SKILL_INFO, result_score, result_subtype, skill_label
from services.planner import compute_progress
from utils import dates

PERIOD_TITLES = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "custom": "Custom",
    "all": "All time",
}


@dataclass
class SkillStats:
    skill: str
    count: int = 0
    bands: List[float] = field(default_factory=list)
    percents: List[float] = field(default_factory=list)
    scaled: List[int] = field(default_factory=list)
    minutes: int = 0
    breakdown: Dict[str, int] = field(default_factory=dict)
    best: Optional[Result] = None

    @property
    def avg_band(self) -> Optional[float]:
        return sum(self.bands) / len(self.bands) if self.bands else None

    @property
    def best_band(self) -> Optional[float]:
        return max(self.bands) if self.bands else None

    @property
    def avg_percent(self) -> Optional[float]:
        return sum(self.percents) / len(self.percents) if self.percents else None

    @property
    def avg_scaled(self) -> Optional[float]:
        return sum(self.scaled) / len(self.scaled) if self.scaled else None


@dataclass
class PeriodStats:
    start: dt.date
    end: dt.date
    results: List[Result]
    skills: Dict[str, SkillStats]
    days: int
    active_days: int
    total_minutes: int
    goal_completion: Optional[float] = None

    @property
    def total_mocks(self) -> int:
        return len(self.results)

    @property
    def avg_daily_minutes(self) -> float:
        return self.total_minutes / self.days if self.days else 0.0

    @property
    def overall_estimate(self) -> Optional[float]:
        bands = [s.avg_band for s in self.skills.values()]
        if any(b is None for b in bands):
            return None
        return round_overall(bands)  # type: ignore[arg-type]


def build_period_stats(
    results: Sequence[Result],
    start: dt.date,
    end: dt.date,
    today: dt.date,
    goals: Optional[Dict[str, int]] = None,
) -> PeriodStats:
    skills = {skill: SkillStats(skill) for skill in SKILLS}
    total_minutes = 0
    per_day: Dict[dt.date, List[Result]] = {}
    for result in results:
        stats = skills[result.skill]
        stats.count += 1
        stats.bands.append(float(result.band))
        stats.minutes += int(result.minutes or 0)
        total_minutes += int(result.minutes or 0)
        if result.total:
            stats.percents.append(result.correct * 100.0 / result.total)
            stats.scaled.append(scale_to_40(result.correct, result.total))
        sub = result_subtype(result)
        if sub:
            stats.breakdown[sub] = stats.breakdown.get(sub, 0) + 1
        if stats.best is None or result.band >= stats.best.band:
            stats.best = result
        per_day.setdefault(result.local_date, []).append(result)

    last = min(end, today)
    days = max(1, (last - start).days + 1) if last >= start else 1

    completion = None
    if goals and any(v > 0 for v in goals.values()) and last >= start:
        values = []
        for day in dates.iter_days(start, last):
            progress = compute_progress(goals, per_day.get(day, []))
            if progress.percent is not None:
                values.append(progress.percent)
        if values:
            completion = sum(values) / len(values)

    return PeriodStats(
        start=start,
        end=end,
        results=list(results),
        skills=skills,
        days=days,
        active_days=len(per_day),
        total_minutes=total_minutes,
        goal_completion=completion,
    )


async def period_stats(session: AsyncSession, start: dt.date, end: dt.date) -> PeriodStats:
    settings = await get_settings(session)
    results = await results_between(session, start, end)
    return build_period_stats(results, start, end, dates.today(), get_goals(settings))


def period_bounds(kind: str, today: dt.date) -> Tuple[dt.date, dt.date]:
    if kind == "daily":
        return today, today
    if kind == "weekly":
        return today - dt.timedelta(days=6), today
    if kind == "monthly":
        return today - dt.timedelta(days=29), today
    raise ValueError(kind)


def previous_period(start: dt.date, end: dt.date) -> Tuple[dt.date, dt.date]:
    length = (end - start).days + 1
    prev_end = start - dt.timedelta(days=1)
    return prev_end - dt.timedelta(days=length - 1), prev_end


# ---------------------------------------------------------------- formatting
def _delta(current: Optional[float], previous: Optional[float], fmt: str = "%.1f") -> str:
    if current is None or previous is None:
        return ""
    diff = current - previous
    if abs(diff) < 1e-9:
        return " (= 0)"
    arrow = "▲ +" if diff > 0 else "▼ −"
    return " (%s%s)" % (arrow, fmt % abs(diff))


def _period_line(stats: PeriodStats) -> str:
    if stats.start == stats.end:
        return "📅 %s" % dates.fmt_short(stats.start)
    return "📅 %s — %s" % (dates.fmt_short(stats.start), dates.fmt_short(stats.end))


def format_stats(title: str, cur: PeriodStats, prev: Optional[PeriodStats]) -> str:
    lines = ["📊 <b>STATISTICS — %s</b>" % html.escape(title), _period_line(cur), ""]

    if not cur.results:
        lines.append("Bu davrda natija kiritilmagan.")
        if prev is not None and prev.results:
            lines.append("Oldingi davrda: %d ta mock." % prev.total_mocks)
        return "\n".join(lines)

    prev_mocks = float(prev.total_mocks) if prev is not None else None
    lines.append("📝 Jami mocklar: <b>%d</b>%s" % (cur.total_mocks, _delta(float(cur.total_mocks), prev_mocks, "%.0f")))
    lines.append("📆 Faol kunlar: <b>%d / %d</b>" % (cur.active_days, cur.days))
    time_line = "⏱ Jami vaqt: <b>%s</b>" % dates.fmt_minutes(cur.total_minutes)
    if cur.days > 1:
        time_line += " · kunlik o‘rtacha: %s" % dates.fmt_minutes(int(round(cur.avg_daily_minutes)))
    lines.append(time_line)
    if cur.goal_completion is not None:
        lines.append("🎯 Kunlik maqsad bajarilishi: <b>%.0f%%</b>" % cur.goal_completion)
    if cur.overall_estimate is not None:
        lines.append("📈 Taxminiy overall band: <b>%s</b>" % fmt_band(cur.overall_estimate))
    lines.append("")

    for skill in SKILLS:
        stats = cur.skills[skill]
        if not stats.count:
            continue
        previous = prev.skills[skill] if prev is not None else None
        header = "<b>%s</b> — %d ta" % (skill_label(skill), stats.count)
        if stats.breakdown and skill != "reading":
            header += " (%s)" % ", ".join("%s: %d" % (k, v) for k, v in sorted(stats.breakdown.items()))
        lines.append(header)
        if skill in ("listening", "reading"):
            lines.append(
                "   O‘rtacha: %.1f/40 (%.0f%%) · Band <b>%s</b>%s"
                % (
                    stats.avg_scaled or 0,
                    stats.avg_percent or 0,
                    fmt_band(stats.avg_band),
                    _delta(stats.avg_band, previous.avg_band if previous else None),
                )
            )
        else:
            lines.append(
                "   O‘rtacha band: <b>%s</b>%s"
                % (fmt_band(stats.avg_band), _delta(stats.avg_band, previous.avg_band if previous else None))
            )
        if stats.best is not None:
            lines.append(
                "   🏆 Eng yaxshi: %s → %s (%s)"
                % (result_score(stats.best), fmt_band(stats.best.band), dates.fmt_short(stats.best.local_date))
            )
        if stats.minutes:
            lines.append("   ⏱ %s" % dates.fmt_minutes(stats.minutes))
        lines.append("")

    if prev is not None:
        lines.append(
            "↔️ Oldingi davr (%s — %s): %d ta mock, %s"
            % (dates.fmt_short(prev.start), dates.fmt_short(prev.end), prev.total_mocks, dates.fmt_minutes(prev.total_minutes))
        )
    return "\n".join(lines).rstrip()
