"""IELTS raw score -> band konversiyasi.

Jadvallar rasmiy (Cambridge / British Council / IDP) e'lon qilgan 40 savollik
konversiya jadvallariga asoslangan. Har bir qator: (minimal to‘g‘ri javob, band).
Savollar soni 40 bo‘lmasa, natija 40 ga proporsional moslab hisoblanadi (taxminiy).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional, Sequence, Tuple

Table = Sequence[Tuple[int, float]]

LISTENING_TABLE: Table = (
    (39, 9.0), (37, 8.5), (35, 8.0), (32, 7.5), (30, 7.0), (26, 6.5), (23, 6.0),
    (18, 5.5), (16, 5.0), (13, 4.5), (10, 4.0), (8, 3.5), (6, 3.0), (4, 2.5),
    (3, 2.0), (2, 1.5), (1, 1.0), (0, 0.0),
)

ACADEMIC_READING_TABLE: Table = (
    (39, 9.0), (37, 8.5), (35, 8.0), (33, 7.5), (30, 7.0), (27, 6.5), (23, 6.0),
    (19, 5.5), (15, 5.0), (13, 4.5), (10, 4.0), (8, 3.5), (6, 3.0), (4, 2.5),
    (3, 2.0), (2, 1.5), (1, 1.0), (0, 0.0),
)

GENERAL_READING_TABLE: Table = (
    (40, 9.0), (39, 8.5), (37, 8.0), (36, 7.5), (34, 7.0), (32, 6.5), (30, 6.0),
    (27, 5.5), (23, 5.0), (19, 4.5), (15, 4.0), (12, 3.5), (9, 3.0), (6, 2.5),
    (4, 2.0), (2, 1.5), (1, 1.0), (0, 0.0),
)

# Botda Reading faqat Academic. General jadval eski yozuvlar/kelajak uchun saqlab qolingan.
READING_TYPES = {"academic": "Academic", "general": "General Training"}


def scale_to_40(correct: int, total: int) -> int:
    if total <= 0:
        raise ValueError("total must be positive")
    if total == 40:
        return correct
    scaled = (Decimal(correct) * 40 / Decimal(total)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(0, min(40, int(scaled)))


def _lookup(table: Table, score: int) -> float:
    for minimum, band in table:
        if score >= minimum:
            return band
    return 0.0


def table_for(skill: str, reading_type: Optional[str] = None) -> Table:
    if skill == "listening":
        return LISTENING_TABLE
    if skill == "reading":
        return GENERAL_READING_TABLE if reading_type == "general" else ACADEMIC_READING_TABLE
    raise ValueError("Band jadvali faqat listening/reading uchun: %r" % skill)


def calculate_band(skill: str, correct: int, total: int, reading_type: Optional[str] = None) -> float:
    if correct < 0 or correct > total:
        raise ValueError("correct must be between 0 and total")
    return _lookup(table_for(skill, reading_type), scale_to_40(correct, total))


def is_estimated(total: Optional[int]) -> bool:
    return total is not None and total != 40


def round_overall(bands: Iterable[float]) -> Optional[float]:
    """IELTS overall yaxlitlash: .25 -> .5, .75 -> keyingi butun."""
    values = list(bands)
    if not values:
        return None
    avg = Decimal(str(sum(values))) / Decimal(len(values))
    return float((avg * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2)


def fmt_band(value: Optional[float]) -> str:
    return "—" if value is None else "%.1f" % value
