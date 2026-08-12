"""Rendering of the workout detail card and history row labels (HTML parse mode)."""

from __future__ import annotations

from html import escape

from momentum.db.models import Workout
from momentum.formatters._shared import truncate
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

    description = workout.description.strip()
    lines.append(f"📝 {escape(description)}" if description else texts_workout.CARD_NO_DESCRIPTION)
    return "\n".join(lines)


def history_row_label(workout: Workout) -> str:
    """Short one-line label for a history list button."""
    icon = "💪" if workout.workout_type in ("gym", "home_workout") else "🏃"
    parts = [f"{texts_common.fmt_date(workout.performed_on)} {icon}"]

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
