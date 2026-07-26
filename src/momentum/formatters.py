"""Rendering of workout cards and report texts (HTML parse mode).

All literal copy comes from texts.py — this module only assembles it.
"""

from __future__ import annotations

from html import escape

from momentum import texts
from momentum.db.repo import Workout
from momentum.services.stats import MonthlyStats, WeeklyStats


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def _diff_line(diff: int, pct: int | None) -> str:
    if diff == 0:
        suffix = texts.DIFF_NO_CHANGE
    elif pct is None:
        suffix = texts.DIFF_FROM_ZERO
    else:
        suffix = f"{_signed(pct)}%"
    return f"{texts.LABEL_DIFF}: {_signed(diff)} ({suffix})"


# --------------------------------------------------------------------------
# Workout card
# --------------------------------------------------------------------------


def workout_card(workout: Workout) -> str:
    lines = [
        f"<b>{texts.KIND_TITLES[workout.kind]}</b>",
        f"📅 {texts.fmt_date(workout.performed_on)}, {texts.fmt_weekday(workout.performed_on)}",
    ]
    if workout.body_parts:
        lines.append(f"🎯 {texts.body_parts_line(workout.body_parts)}")

    description = workout.description.strip()
    lines.append(f"📝 {escape(description)}" if description else texts.CARD_NO_DESCRIPTION)
    return "\n".join(lines)


def history_row_label(workout: Workout) -> str:
    """Short one-line label for a history list button."""
    icon = "🏃" if workout.kind == "cardio" else "💪"
    parts = [f"{texts.fmt_date(workout.performed_on)} {icon}"]

    if workout.body_parts:
        # Strip the emoji prefix — the row is already narrow.
        names = [
            texts.body_part_label(p).split(" ", 1)[-1]
            for p in texts.BODY_PARTS
            if p in workout.body_parts
        ]
        parts.append(", ".join(names))
    elif workout.description.strip():
        parts.append(workout.description.strip())

    label = " · ".join(parts)
    return label[:60] + "…" if len(label) > 61 else label


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


def weekly_report(stats: WeeklyStats) -> str:
    period = f"{texts.fmt_date_short(stats.week_start)} – {texts.fmt_date_short(stats.week_end)}"
    head = f"{texts.WEEKLY_TITLE}\n{period}"

    if stats.total == 0:
        return f"{head}\n\n{texts.WEEKLY_EMPTY}"

    blocks = [
        head,
        f"{texts.LABEL_TOTAL}: <b>{stats.total}</b>",
        (f"{texts.LABEL_STRENGTH}: {stats.strength}\n{texts.LABEL_CARDIO}: {stats.cardio}"),
        (f"{texts.LABEL_PREV_WEEK}: {stats.prev_total}\n{_diff_line(stats.diff, stats.pct)}"),
    ]

    if stats.streak > 0:
        blocks.append(texts.streak_line(stats.streak))

    blocks.append(
        f"{texts.LABEL_MONTH_TO_DATE}: {stats.month_to_date} "
        f"{texts.workouts_word(stats.month_to_date)}"
    )
    return "\n\n".join(blocks)


def monthly_report(stats: MonthlyStats) -> str:
    head = f"{texts.MONTHLY_TITLE}\n{texts.fmt_month_year(stats.month_start)}"

    if stats.total == 0:
        return f"{head}\n\n{texts.MONTHLY_EMPTY}"

    blocks = [
        head,
        (
            f"{texts.LABEL_TOTAL}: <b>{stats.total}</b>\n"
            f"{texts.LABEL_WEEKLY_AVG}: {stats.weekly_avg}"
        ),
        (
            f"{texts.LABEL_STRENGTH}: {stats.strength} ({stats.strength_pct}%)\n"
            f"{texts.LABEL_CARDIO}: {stats.cardio} ({stats.cardio_pct}%)"
        ),
    ]

    if stats.body_parts:
        rows = "\n".join(
            f"{texts.body_part_label(part)} — {count}" for part, count in stats.body_parts
        )
        blocks.append(f"<b>{texts.LABEL_BODY_PARTS}:</b>\n{rows}")

    blocks.append(
        f"{texts.LABEL_PREV_MONTH}: {stats.prev_total}\n{_diff_line(stats.diff, stats.pct)}"
    )
    return "\n\n".join(blocks)
