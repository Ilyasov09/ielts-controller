"""Progress grafigi (PNG): yuqorida skill bandlari, pastda kunlik tayyorgarlik vaqti.

Dizayn qoidalari: bitta o‘q (dual-axis yo‘q — vaqt alohida panelda), ranglar skillga
bog‘langan (tartib o‘zgarmaydi), 2px chiziq, har skillga alohida marker shakli
(rangsiz ham ajraladi), legend + chiziq oxirida qiymat yozuvi.
"""
from __future__ import annotations

import datetime as dt
import io
import math
from typing import Dict, List, Optional, Sequence

from database.models import Result
from database.repository import SKILLS
from utils import dates

# Tekshirilgan kategorik palitra (light surface #fcfcfb), skill -> rang, tartibi qat'iy
SKILL_STYLE = {
    "listening": ("Listening", "#2a78d6", "o"),
    "reading": ("Reading", "#eb6834", "s"),
    "writing": ("Writing", "#1baf7a", "^"),
    "speaking": ("Speaking", "#eda100", "D"),
}
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BAR = "#86b6ef"


INSTALL_HINT = "Grafik uchun matplotlib kerak. Termux: pkg install matplotlib · boshqa joyda: pip install matplotlib"


def charts_available() -> bool:
    try:
        import matplotlib  # noqa: F401

        return True
    except ImportError:
        return False


def build_progress_chart(results: Sequence[Result], start: dt.date, end: dt.date,
                         title: str = "IELTS progress") -> Optional[bytes]:
    """PNG baytlari yoki None (natija yo‘q). matplotlib o‘rnatilmagan bo‘lsa — ImportError."""
    if not results:
        return None

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    days = list(dates.iter_days(start, end))
    bands: Dict[str, Dict[dt.date, List[float]]] = {skill: {} for skill in SKILLS}
    minutes: Dict[dt.date, int] = {day: 0 for day in days}
    for result in results:
        bands[result.skill].setdefault(result.local_date, []).append(float(result.band))
        if result.local_date in minutes:
            minutes[result.local_date] += int(result.minutes or 0)

    fig, (ax_band, ax_time) = plt.subplots(
        2, 1, figsize=(10, 6.6), dpi=150, sharex=True,
        gridspec_kw={"height_ratios": [3, 1.25], "hspace": 0.12},
    )
    fig.patch.set_facecolor(SURFACE)

    all_bands: List[float] = []
    labelled = set()  # bir nuqtada tugagan chiziqlar uchun yozuv bir marta
    for skill in SKILLS:
        series = bands[skill]
        if not series:
            continue
        label, color, marker = SKILL_STYLE[skill]
        xs = sorted(series)
        ys = [sum(series[x]) / len(series[x]) for x in xs]
        all_bands += ys
        ax_band.plot(
            xs, ys, color=color, linewidth=2, marker=marker, markersize=8,
            markeredgecolor=SURFACE, markeredgewidth=2, label=label, zorder=3, clip_on=False,
        )
        if (xs[-1], ys[-1]) in labelled:
            continue
        labelled.add((xs[-1], ys[-1]))
        ax_band.annotate(
            "%.1f" % ys[-1], (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
            va="center", ha="left", fontsize=9, color=INK_2, fontweight="bold",
        )

    low = max(0.0, math.floor(min(all_bands) * 2) / 2 - 0.5)
    ax_band.set_ylim(low, 9.25)
    step = 0.5 if 9 - low <= 4 else 1.0
    ticks = []
    value = low
    while value <= 9.0001:
        ticks.append(value)
        value += step
    ax_band.set_yticks(ticks)
    ax_band.set_ylabel("Band", color=INK_2, fontsize=10)
    ax_band.legend(
        loc="upper left", bbox_to_anchor=(0, 1.13), ncol=4, frameon=False,
        fontsize=9, labelcolor=INK_2, handlelength=1.6,
    )

    width = 0.7 if len(days) <= 60 else 0.9
    ax_time.bar(days, [minutes[d] for d in days], width=width, color=BAR, zorder=3)
    ax_time.set_ylabel("Minutes", color=INK_2, fontsize=10)
    peak = max(minutes.values()) if minutes else 0
    ax_time.set_ylim(0, max(30, peak * 1.15))

    for ax in (ax_band, ax_time):
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.tick_params(colors=MUTED, labelsize=9, length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(AXIS)

    # date - timedelta(0.8) kasrni tashlab yuboradi, shuning uchun datetime bilan hisoblaymiz
    pad = dt.timedelta(hours=18)
    ax_time.set_xlim(dt.datetime.combine(start, dt.time()) - pad, dt.datetime.combine(end, dt.time()) + pad)
    locator = mdates.AutoDateLocator(minticks=3, maxticks=10)
    ax_time.xaxis.set_major_locator(locator)
    ax_time.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

    period = dates.fmt_short(start) if start == end else "%s – %s" % (dates.fmt_short(start), dates.fmt_short(end))
    fig.suptitle("%s · %s" % (title, period), x=0.06, ha="left", y=0.99, fontsize=13, color=INK,
                 fontweight="bold")

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor=SURFACE, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return buffer.getvalue()
