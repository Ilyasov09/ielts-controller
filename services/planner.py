"""Study Planner — kunlik maqsadlar va bajarilish foizi."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from database.models import Result

GOAL_KEYS = ("listening", "reading", "writing", "speaking", "minutes")
GOAL_LABELS = {
    "listening": "🎧 Listening",
    "reading": "📖 Reading",
    "writing": "✍️ Writing",
    "speaking": "🎙 Speaking",
    "minutes": "⏱ Vaqt (daqiqa)",
}
GOAL_FIELDS = {
    "listening": "goal_listening",
    "reading": "goal_reading",
    "writing": "goal_writing",
    "speaking": "goal_speaking",
    "minutes": "goal_minutes",
}


@dataclass
class GoalProgress:
    items: List[Tuple[str, int, int]] = field(default_factory=list)  # (key, done, goal)
    percent: Optional[float] = None


def done_values(results: Sequence[Result]) -> Dict[str, int]:
    done = {key: 0 for key in GOAL_KEYS}
    for result in results:
        done[result.skill] = done.get(result.skill, 0) + 1
        done["minutes"] += int(result.minutes or 0)
    return done


def compute_progress(goals: Dict[str, int], results: Sequence[Result]) -> GoalProgress:
    done = done_values(results)
    progress = GoalProgress()
    ratios = []
    for key in GOAL_KEYS:
        goal = int(goals.get(key) or 0)
        if goal <= 0:
            continue
        progress.items.append((key, done[key], goal))
        ratios.append(min(1.0, done[key] / goal))
    if ratios:
        progress.percent = sum(ratios) / len(ratios) * 100.0
    return progress


def format_progress(progress: GoalProgress) -> List[str]:
    lines = []
    for key, done, goal in progress.items:
        mark = "✅" if done >= goal else "⏳"
        lines.append("%s %s: %d / %d" % (mark, GOAL_LABELS[key], done, goal))
    if progress.percent is not None:
        lines.append("📈 Bajarilish: <b>%.0f%%</b>" % progress.percent)
    return lines


def progress_bar(percent: Optional[float], width: int = 10) -> str:
    if percent is None:
        return ""
    filled = int(round(percent / 100.0 * width))
    return "▓" * filled + "░" * (width - filled)
