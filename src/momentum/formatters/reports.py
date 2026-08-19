"""Rendering of the weekly/monthly report text (HTML parse mode)."""

from __future__ import annotations

from momentum.db.models import GoalType
from momentum.formatters.profile import fmt_number
from momentum.services.measurements import FieldSnapshot, ReportBody, delta_is_good
from momentum.services.stats import MonthlyStats, WeeklyStats
from momentum.texts import common as texts_common
from momentum.texts import measurements as texts_measurements
from momentum.texts import reports as texts_reports
from momentum.texts import workout as texts_workout


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def _signed_delta(value: float) -> str:
    formatted = fmt_number(abs(value))
    if value > 0:
        return f"+{formatted}"
    if value < 0:
        return f"−{formatted}"
    return formatted


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


def weekly_report(stats: WeeklyStats, body: ReportBody) -> str:
    """Workout stats for the week, then the goal/measurements block for the same dates.

    An empty gym week still gets the body block (reminder or facts) instead of
    returning only ``WEEKLY_EMPTY``.
    """
    period = (
        f"{texts_common.fmt_date_short(stats.week_start)} – "
        f"{texts_common.fmt_date_short(stats.week_end)}"
    )
    head = f"{texts_reports.WEEKLY_TITLE}\n{period}"
    return "\n\n".join((head, _weekly_workout_block(stats), _body_block(body, "week")))


def monthly_report(stats: MonthlyStats, body: ReportBody) -> str:
    """Workout stats for the month, then the goal/measurements block for the same dates.

    An empty gym month still gets the body block (reminder or facts) instead of
    returning only ``MONTHLY_EMPTY``.
    """
    head = f"{texts_reports.MONTHLY_TITLE}\n{texts_common.fmt_month_year(stats.month_start)}"
    return "\n\n".join((head, _monthly_workout_block(stats), _body_block(body, "month")))


def _weekly_workout_block(stats: WeeklyStats) -> str:
    if stats.total == 0:
        return texts_reports.WEEKLY_EMPTY

    blocks = [
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


def _monthly_workout_block(stats: MonthlyStats) -> str:
    if stats.total == 0:
        return texts_reports.MONTHLY_EMPTY

    blocks = [
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


def _body_block(body: ReportBody, kind: texts_reports.ReportKind) -> str:
    """Goal line (if any), then either in-period facts and tone or the weekly-rhythm reminder."""
    parts: list[str] = []
    if body.goal is not None:
        target = (
            fmt_number(body.goal.target_weight_kg)
            if body.goal.target_weight_kg is not None
            else None
        )
        line = texts_reports.goal_line(body.goal.goal_type, target)
        if line:
            parts.append(line)

    facts = _facts_line(body, kind)
    if facts is None:
        parts.append(texts_reports.no_measurements(kind))
        return "\n\n".join(parts)

    parts.append(facts)
    tone = _tone_line(body, kind)
    if tone:
        parts.append(tone)
    return "\n\n".join(parts)


def _facts_line(body: ReportBody, kind: texts_reports.ReportKind) -> str | None:
    if not body.change.had_measurement:
        return None
    phrases = []
    for field in texts_reports.FACT_FIELDS:
        snap: FieldSnapshot | None = getattr(body.change, field)
        if snap is not None:
            phrases.append(_field_phrase(field, snap, body.goal.goal_type if body.goal else None))
    if not phrases:
        return None
    return texts_reports.facts_line(kind, "\n".join(phrases))


def _field_phrase(field: str, snap: FieldSnapshot, goal_type: GoalType | None) -> str:
    label = texts_measurements.FIELD_LABELS[field]
    unit = texts_measurements.FIELD_UNITS[field]
    delta = None
    if snap.delta is not None and snap.previous_on is not None:
        signed = texts_reports.marked_delta(
            signed=_signed_delta(snap.delta),
            good=delta_is_good(snap.delta, goal_type),
        )
        delta = texts_measurements.delta_suffix(
            signed,
            unit,
            texts_common.fmt_date_short(snap.previous_on),
        )
    return texts_reports.field_phrase(label, fmt_number(snap.value), unit, delta)


def _tone_line(body: ReportBody, kind: texts_reports.ReportKind) -> str | None:
    if body.tone == "progress":
        left = fmt_number(body.kg_left) if body.kg_left is not None else None
        return texts_reports.tone_progress(kind, left)
    if body.tone == "setback":
        return texts_reports.tone_setback(kind)
    if body.tone == "reached":
        return texts_reports.TONE_REACHED
    return None
