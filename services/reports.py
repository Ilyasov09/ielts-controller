"""PDF va Excel eksport."""
from __future__ import annotations

import io
from typing import List, Sequence

from database.repository import SKILLS
from services.band_calculator import READING_TYPES, fmt_band
from services.channel import SKILL_INFO, result_subtype
from services.statistics import PeriodStats
from utils import dates

RESULT_HEADERS = ("#", "Date", "Time", "Skill", "Type", "Correct", "Total", "Band", "Minutes", "Topic", "Photo")


def _rows(stats: PeriodStats) -> List[list]:
    rows = []
    for index, result in enumerate(stats.results, start=1):
        local = dates.to_local(result.created_at)
        rows.append([
            index,
            dates.fmt_short(result.local_date),
            local.strftime("%H:%M"),
            SKILL_INFO[result.skill][2],
            result_subtype(result),
            result.correct if result.correct is not None else "",
            result.total if result.total is not None else "",
            float(result.band),
            result.minutes if result.minutes is not None else "",
            result.topic or "",
            "yes" if result.photo_file_id else "",
        ])
    return rows


def _summary(stats: PeriodStats) -> List[list]:
    rows = [
        ["Period", "%s - %s" % (dates.fmt_short(stats.start), dates.fmt_short(stats.end))],
        ["Total mocks", stats.total_mocks],
        ["Active days", "%d / %d" % (stats.active_days, stats.days)],
        ["Total study time", dates.fmt_minutes(stats.total_minutes)],
        ["Average daily time", dates.fmt_minutes(int(round(stats.avg_daily_minutes)))],
    ]
    if stats.goal_completion is not None:
        rows.append(["Daily goal completion", "%.0f%%" % stats.goal_completion])
    if stats.overall_estimate is not None:
        rows.append(["Estimated overall band", fmt_band(stats.overall_estimate)])
    return rows


def _skill_rows(stats: PeriodStats) -> List[list]:
    rows = []
    for skill in SKILLS:
        s = stats.skills[skill]
        rows.append([
            SKILL_INFO[skill][2],
            s.count,
            fmt_band(s.avg_band),
            fmt_band(s.best_band),
            ("%.1f/40" % s.avg_scaled) if s.avg_scaled is not None else "-",
            ("%.0f%%" % s.avg_percent) if s.avg_percent is not None else "-",
            dates.fmt_minutes(s.minutes),
        ])
    return rows


SKILL_HEADERS = ("Skill", "Mocks", "Avg band", "Best band", "Avg raw", "Avg %", "Time")


# ---------------------------------------------------------------- Excel
def build_excel(stats: PeriodStats, title: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1F4E78")

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["IELTS Controller — %s report" % title])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    for row in _summary(stats):
        ws.append(row)
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([])
    ws.append(list(SKILL_HEADERS))
    for cell in ws[ws.max_row]:
        cell.font = head_font
        cell.fill = head_fill
    for row in _skill_rows(stats):
        ws.append(row)

    rs = wb.create_sheet("Results")
    rs.append(list(RESULT_HEADERS))
    for cell in rs[1]:
        cell.font = head_font
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center")
    for row in _rows(stats):
        rs.append(row)
    rs.freeze_panes = "A2"

    for sheet in (ws, rs):
        for column_cells in sheet.columns:
            length = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells)
            sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(60, max(8, length + 2))

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------- PDF
_REPLACEMENTS = {
    "‘": "'", "’": "'", "ʻ": "'", "ʼ": "'", "“": '"', "”": '"',
    "—": "-", "–": "-", "…": "...", "•": "*", "·": "-", "−": "-",
}


def _latin(text: object) -> str:
    value = str(text)
    for src, dst in _REPLACEMENTS.items():
        value = value.replace(src, dst)
    return value.encode("latin-1", "replace").decode("latin-1")


def build_pdf(stats: PeriodStats, title: str) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    def line(text: str, size: int = 11, bold: bool = False, height: float = 7) -> None:
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.cell(0, height, _latin(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def fit(text: str, width: float) -> str:
        text = _latin(text)
        if pdf.get_string_width(text) <= width - 2:
            return text
        while text and pdf.get_string_width(text + "...") > width - 2:
            text = text[:-1]
        return text + "..."

    def table(headers: Sequence[str], rows: Sequence[Sequence[object]], widths: Sequence[float]) -> None:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(31, 78, 120)
        pdf.set_text_color(255, 255, 255)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, fit(header, width), border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        for index, row in enumerate(rows):
            if pdf.get_y() > pdf.h - 20:
                pdf.add_page()
            fill = index % 2 == 1
            pdf.set_fill_color(235, 241, 248)
            for value, width in zip(row, widths):
                if isinstance(value, float):
                    value = "%.1f" % value
                pdf.cell(width, 6, fit(str(value), width), border=1, fill=fill)
            pdf.ln()

    line("IELTS Controller - %s report" % title, size=18, bold=True, height=10)
    line("Generated: %s" % dates.now_local().strftime("%d.%m.%Y %H:%M"), size=9)
    pdf.ln(3)

    line("Summary", size=13, bold=True)
    for key, value in _summary(stats):
        line("%s: %s" % (key, value), size=10, height=6)
    pdf.ln(3)

    line("Skills", size=13, bold=True)
    table(SKILL_HEADERS, _skill_rows(stats), (40, 22, 28, 28, 30, 25, 40))
    pdf.ln(4)

    line("Results", size=13, bold=True)
    if stats.results:
        widths = (10, 24, 15, 24, 34, 18, 15, 15, 18, 91, 13)
        table(RESULT_HEADERS, _rows(stats), widths)
    else:
        line("No results in this period.", size=10)

    data = pdf.output()
    return bytes(data)
