"""Rendering of the workout detail card and history row labels (HTML parse mode)."""

from __future__ import annotations

from html import escape

from momentum.db.models import Workout
from momentum.formatters._shared import truncate
from momentum.formatters.profile import fmt_number
from momentum.texts import common as texts_common
from momentum.texts import workout as texts_workout


def workout_card(workout: Workout) -> str:
    lines = [
        f"<b>{texts_workout.KIND_TITLES[workout.workout_type]}</b>",
        f"📅 {texts_common.fmt_date(workout.performed_on)}, "
        f"{texts_common.fmt_weekday(workout.performed_on)}",
    ]
    if workout.body_parts:
        lines.append(f"🎯 {texts_workout.body_parts_line(workout.body_parts)}")
    details = _details_line(workout)
    if details:
        lines.append(details)

    description = workout.description.strip()
    lines.append(f"📝 {escape(description)}" if description else texts_workout.CARD_NO_DESCRIPTION)
    return "\n".join(lines)


def _details_line(workout: Workout) -> str | None:
    """Duration · distance · effort — whichever were recorded, in the order they're asked."""
    details = []
    if workout.duration_min is not None:
        details.append(texts_workout.card_duration(workout.duration_min))
    if workout.distance_km is not None:
        details.append(texts_workout.card_distance(fmt_number(workout.distance_km)))
    if workout.effort is not None:
        details.append(texts_workout.choice_label("effort", workout.effort))
    return texts_workout.CARD_DETAILS_SEPARATOR.join(details) or None


def history_row_label(workout: Workout) -> str:
    """Short one-line label for a history list button."""
    parts = [
        f"{texts_common.fmt_date(workout.performed_on)} — "
        f"{texts_workout.type_label(workout.workout_type)}"
    ]

    if workout.body_parts:
        # Strip the emoji prefix — the row is already narrow.
        names = [
            texts_workout.body_part_label(p).split(" ", 1)[-1]
            for p in texts_workout.BODY_PARTS
            if p in workout.body_parts
        ]
        parts.append(", ".join(names))
    elif workout.description.strip():
        parts.append(workout.description.strip())

    return truncate(" · ".join(parts))
