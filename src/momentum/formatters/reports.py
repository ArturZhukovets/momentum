"""Rendering of the weekly/monthly report text (HTML parse mode)."""

from __future__ import annotations

from momentum.services.stats import MonthlyStats, WeeklyStats
from momentum.texts import common as texts_common
from momentum.texts import reports as texts_reports
from momentum.texts import workout as texts_workout


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def _diff_line(diff: int, pct: int | None) -> str:
    if diff == 0:
        suffix = texts_reports.DIFF_NO_CHANGE
    elif pct is None:
        suffix = texts_reports.DIFF_FROM_ZERO
    else:
        suffix = f"{_signed(pct)}%"
    return f"{texts_reports.LABEL_DIFF}: {_signed(diff)} ({suffix})"


def _by_type_block(by_type: tuple[tuple[str, int], ...]) -> str:
    return "\n".join(f"{texts_workout.type_label(t)}: {n}" for t, n in by_type)


def weekly_report(stats: WeeklyStats) -> str:
    period = (
        f"{texts_common.fmt_date_short(stats.week_start)} – "
        f"{texts_common.fmt_date_short(stats.week_end)}"
    )
    head = f"{texts_reports.WEEKLY_TITLE}\n{period}"

    if stats.total == 0:
        return f"{head}\n\n{texts_reports.WEEKLY_EMPTY}"

    blocks = [
        head,
        f"{texts_reports.LABEL_TOTAL}: <b>{stats.total}</b>",
        _by_type_block(stats.by_type),
        (
            f"{texts_reports.LABEL_PREV_WEEK}: {stats.prev_total}\n"
            f"{_diff_line(stats.diff, stats.pct)}"
        ),
    ]

    if stats.streak > 0:
        blocks.append(texts_reports.streak_line(stats.streak))

    blocks.append(
        f"{texts_reports.LABEL_MONTH_TO_DATE}: {stats.month_to_date} "
        f"{texts_common.workouts_word(stats.month_to_date)}"
    )
    return "\n\n".join(blocks)


def monthly_report(stats: MonthlyStats) -> str:
    head = f"{texts_reports.MONTHLY_TITLE}\n{texts_common.fmt_month_year(stats.month_start)}"

    if stats.total == 0:
        return f"{head}\n\n{texts_reports.MONTHLY_EMPTY}"

    blocks = [
        head,
        (
            f"{texts_reports.LABEL_TOTAL}: <b>{stats.total}</b>\n"
            f"{texts_reports.LABEL_WEEKLY_AVG}: {stats.weekly_avg}"
        ),
        _by_type_block(stats.by_type),
    ]

    if stats.body_parts:
        rows = "\n".join(
            f"{texts_workout.body_part_label(part)} — {count}" for part, count in stats.body_parts
        )
        blocks.append(f"<b>{texts_reports.LABEL_BODY_PARTS}:</b>\n{rows}")

    blocks.append(
        f"{texts_reports.LABEL_PREV_MONTH}: {stats.prev_total}\n{_diff_line(stats.diff, stats.pct)}"
    )
    return "\n\n".join(blocks)
