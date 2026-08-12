"""Pure catalog of workout types and the ordered, skippable fields each one asks.

The add-workout FSM walks ``fields_for(type)`` generically — adding a type means
extending this module (plus Russian labels in ``texts/``), not touching the FSM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from momentum.db.models import WorkoutType

InputType = Literal["int", "float", "choice", "multi_choice", "text"]
ParsedValue = int | float | str

_NUMBER_RE = re.compile(r"^\s*(\d{1,4}(?:[.,]\d{1,2})?)\s*$")

WORKOUT_TYPES: tuple[WorkoutType, ...] = (
    "running",
    "swimming",
    "elliptical",
    "gym",
    "home_workout",
)

EFFORT_VALUES: tuple[str, ...] = ("easy", "moderate", "hard")

FULL_BODY = "full_body"

BODY_PARTS: tuple[str, ...] = (
    "chest",
    "back",
    "legs",
    "shoulders",
    "arms",
    "core",
    FULL_BODY,
)


@dataclass(frozen=True)
class FieldSpec:
    name: str
    input_type: InputType
    choices: tuple[str, ...] = ()
    minimum: int | float | None = None
    maximum: int | float | None = None


DURATION = FieldSpec("duration_min", "int", minimum=1, maximum=600)
DISTANCE = FieldSpec("distance_km", "float", minimum=0.01, maximum=500.0)
EFFORT = FieldSpec("effort", "choice", EFFORT_VALUES)
DESCRIPTION = FieldSpec("description", "text")
BODY_PARTS_FIELD = FieldSpec("body_parts", "multi_choice", BODY_PARTS)

_FIELDS_BY_TYPE: dict[WorkoutType, tuple[FieldSpec, ...]] = {
    "running": (DURATION, DISTANCE, EFFORT, DESCRIPTION),
    "swimming": (DURATION, DISTANCE, EFFORT, DESCRIPTION),
    "elliptical": (DURATION, EFFORT, DESCRIPTION),
    "gym": (BODY_PARTS_FIELD, DESCRIPTION),
    "home_workout": (BODY_PARTS_FIELD, DURATION, DESCRIPTION),
}


def fields_for(workout_type: WorkoutType) -> tuple[FieldSpec, ...]:
    return _FIELDS_BY_TYPE[workout_type]


def field_at_index(workout_type: WorkoutType, index: int) -> FieldSpec | None:
    """Return the field at an ordered catalog index, if it exists."""
    fields = fields_for(workout_type)
    return fields[index] if 0 <= index < len(fields) else None


def parse_text(field: FieldSpec, text: str | None) -> ParsedValue | None:
    """Parse and validate text input according to a field specification."""
    if field.input_type == "text":
        return (text or "").strip()
    if field.input_type not in ("int", "float"):
        return None

    match = _NUMBER_RE.match(text or "")
    if match is None:
        return None

    raw = match.group(1)
    if field.input_type == "int":
        if "," in raw or "." in raw:
            return None
        value: int | float = int(raw)
    else:
        value = float(raw.replace(",", "."))

    if field.minimum is not None and value < field.minimum:
        return None
    if field.maximum is not None and value > field.maximum:
        return None
    return value
