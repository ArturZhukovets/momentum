"""Rendering of the weekly/monthly report text (HTML parse mode)."""

from __future__ import annotations

from html import escape

from momentum.db.models import GoalType, ReportKind
from momentum.formatters.profile import fmt_number
from momentum.services.energy import EnergyStats
from momentum.services.measurements import FieldSnapshot, ReportBody, delta_is_good
from momentum.services.pace import WEEKS_PER_MONTH
from momentum.services.stats import MonthlyStats, WeeklyStats
from momentum.texts import common as texts_common
from momentum.texts import measurements as texts_measurements
from momentum.texts import reports as texts_reports
from momentum.texts import workout as texts_workout


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def _signed_delta(value: float) -> str:
    formatted = fmt_number(abs(value))
    if formatted == "0":
        return formatted
    if value > 0:
        return f"+{formatted}"
    return f"−{formatted}"


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


def weekly_report(stats: WeeklyStats, body: ReportBody, comment: str | None = None) -> str:
    """Workout stats for the week, the goal/measurements and energy blocks, then the coach comment.

    An empty gym week still gets the body block (reminder or facts) instead of
    returning only ``WEEKLY_EMPTY``.
    """
    period = (
        f"{texts_common.fmt_date_short(stats.week_start)} – "
        f"{texts_common.fmt_date_short(stats.week_end)}"
    )
    head = f"{texts_reports.WEEKLY_TITLE}\n{period}"
    blocks = (head, _weekly_workout_block(stats), *_body_blocks(body, "week"))
    return "\n\n".join((*blocks, *_comment_block(comment)))


def monthly_report(stats: MonthlyStats, body: ReportBody, comment: str | None = None) -> str:
    """Workout stats for the month, the goal/measurements and energy blocks, then the coach comment.

    An empty gym month still gets the body block (reminder or facts) instead of
    returning only ``MONTHLY_EMPTY``.
    """
    head = f"{texts_reports.MONTHLY_TITLE}\n{texts_common.fmt_month_year(stats.month_start)}"
    blocks = (head, _monthly_workout_block(stats), *_body_blocks(body, "month"))
    return "\n\n".join((*blocks, *_comment_block(comment)))


def _comment_block(comment: str | None) -> tuple[str, ...]:
    """The coach comment under its header; model text, so escaped for HTML parse mode."""
    if not comment:
        return ()
    return (f"{texts_reports.COACH_COMMENT_TITLE}\n{escape(comment)}",)


def _body_blocks(body: ReportBody, kind: ReportKind) -> list[str]:
    """Goal/measurements, then energy and the one-time profile nudge when there are any."""
    blocks = [_body_block(body, kind)]
    if body.energy is not None:
        blocks.append(_energy_block(body.energy, kind))
    if body.profile_nudge:
        blocks.append(texts_reports.profile_nudge(body.profile_nudge))
    return blocks


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


def _body_block(body: ReportBody, kind: ReportKind) -> str:
    """Goal line (if any), then in-period facts, tone and pace — or the weekly-rhythm reminder."""
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
    pace = _pace_line(body)
    if pace:
        parts.append(pace)
    return "\n\n".join(parts)


def _facts_line(body: ReportBody, kind: ReportKind) -> str | None:
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


def _tone_line(body: ReportBody, kind: ReportKind) -> str | None:
    if body.tone == "progress":
        left = fmt_number(body.kg_left) if body.kg_left is not None else None
        return texts_reports.tone_progress(kind, left)
    if body.tone == "setback":
        return texts_reports.tone_setback(kind)
    if body.tone == "reached":
        return texts_reports.TONE_REACHED
    return None


def _per_month(kg_per_week: float) -> str:
    return _signed_delta(kg_per_week * WEEKS_PER_MONTH)


def _pace_line(body: ReportBody) -> str | None:
    """Trend vs plan in kg/month.

    Only when this period has a weigh-in, so the verdict and the projection are
    anchored to fresh data; never once the goal is reached or data is thin.
    """
    pace, goal = body.pace, body.goal
    if pace is None or goal is None or pace.status == "none" or body.tone == "reached":
        return None
    if body.change.weight_kg is None:
        return None

    actual = _per_month(pace.actual_kg_per_week)
    if pace.status == "unsafe":
        return texts_reports.pace_unsafe(actual)
    if goal.goal_type == "maintain":
        if pace.status == "on_track":
            return texts_reports.PACE_HOLDING
        return texts_reports.pace_drifting(actual)
    if pace.status == "stalled":
        if actual != "0" and delta_is_good(pace.actual_kg_per_week, goal.goal_type) is False:
            return texts_reports.pace_away(actual)
        return texts_reports.PACE_STALLED

    if pace.required_kg_per_week is None:
        line = texts_reports.pace_no_plan(actual)
    else:
        planned = _per_month(pace.required_kg_per_week)
        if pace.status == "ahead":
            line = texts_reports.pace_ahead(actual, planned)
        elif pace.status == "on_track":
            line = texts_reports.pace_on_track(actual, planned)
        else:
            line = texts_reports.pace_behind(actual, planned)

    if pace.projected_date is None:
        return line
    return texts_reports.pace_eta(line, texts_common.fmt_date(pace.projected_date))


def _energy_block(energy: EnergyStats, kind: ReportKind) -> str:
    """Daily burn, the intake guide for the goal's pace, and what the workouts added."""
    from_workouts = fmt_number(energy.daily_workout_kcal) if energy.daily_workout_kcal else None
    lines = [texts_reports.energy_burn(fmt_number(energy.daily_burn), from_workouts)]
    target = _energy_target_line(energy)
    if target:
        lines.append(target)
    workouts = _energy_workouts_line(energy, kind)
    if workouts:
        lines.append(workouts)
    return "\n".join(lines)


def _energy_target_line(energy: EnergyStats) -> str | None:
    rate = energy.target_kg_per_month
    if rate is None:
        return None
    if energy.below_floor:
        return texts_reports.energy_below_floor(_signed_delta(rate))
    if energy.daily_target is None:
        return None
    target = fmt_number(energy.daily_target)
    if rate == 0:
        return texts_reports.energy_target_maintain(target)
    return texts_reports.energy_target(_signed_delta(rate), target)


def _energy_workouts_line(energy: EnergyStats, kind: ReportKind) -> str | None:
    if energy.counted_workouts:
        return texts_reports.energy_workouts(
            kind,
            fmt_number(energy.workout_kcal),
            energy.counted_workouts,
            energy.skipped_workouts,
        )
    if energy.skipped_workouts:
        return texts_reports.energy_workouts_untimed(kind, energy.skipped_workouts)
    return None
