"""Measurement snapshot and period-change builders.

Pure functions over a list of rows — no aiogram or DB imports. A weight-only
row does not wipe yesterday's waist, and a pre-period waist is not inherited
into «this week's» facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal

from momentum.db.models import BodyMeasurement, GoalType, UserGoal

if TYPE_CHECKING:
    # `pace` and `energy` build on this module, so a runtime import would cycle.
    from momentum.services.energy import EnergyStats, ProfileField
    from momentum.services.pace import PaceStats

MeasurementField = Literal["weight_kg", "waist_cm", "chest_cm", "hips_cm", "thigh_cm", "arm_cm"]
PeriodTone = Literal["progress", "setback", "reached", "none"]

FIELDS: tuple[MeasurementField, ...] = (
    "weight_kg",
    "waist_cm",
    "chest_cm",
    "hips_cm",
    "thigh_cm",
    "arm_cm",
)

# Below this, a weight delta is noise for lose/gain/muscle — not praise, not a setback.
WEIGHT_NOISE_KG = 0.2
# Wider band for maintain: staying inside it is the goal, leaving it is a setback.
MAINTAIN_NOISE_KG = 0.5


@dataclass(frozen=True)
class FieldSnapshot:
    """Latest non-null value of one measurement field."""

    value: float
    recorded_on: date
    delta: float | None  # None when this field has no earlier non-null value
    previous_on: date | None  # date of the row `delta` was computed against


@dataclass(frozen=True)
class MeasurementSnapshot:
    weight_kg: FieldSnapshot | None = None
    waist_cm: FieldSnapshot | None = None
    chest_cm: FieldSnapshot | None = None
    hips_cm: FieldSnapshot | None = None
    thigh_cm: FieldSnapshot | None = None
    arm_cm: FieldSnapshot | None = None


def build_snapshot(rows: list[BodyMeasurement]) -> MeasurementSnapshot:
    """Latest non-null per field, plus the delta to the previous non-null.

    `rows` may be in any order; newest `(recorded_on, id)` wins. Each field is
    walked independently, so a weight-only row is ignored when resolving waist.
    """
    newest_first_rows = sorted(rows, key=lambda r: (r.recorded_on, r.id), reverse=True)
    return MeasurementSnapshot(
        **{field: _field_snapshot(newest_first_rows, field) for field in FIELDS}
    )


def _field_snapshot(rows: list[BodyMeasurement], field: MeasurementField) -> FieldSnapshot | None:
    """
    Latest non-null value of one measurement field recorded with delta to the previous non-null.
    """
    current: float | None = None
    recorded_on: date | None = None
    previous: float | None = None
    previous_on: date | None = None
    for row in rows:
        value: float | None = getattr(row, field)
        if value is None:
            continue
        if current is None:
            current = value
            recorded_on = row.recorded_on
            continue
        previous = value
        previous_on = row.recorded_on
        break

    if current is None or recorded_on is None:
        return None
    delta = None if previous is None else current - previous
    return FieldSnapshot(
        value=current,
        recorded_on=recorded_on,
        delta=delta,
        previous_on=previous_on,
    )


@dataclass(frozen=True)
class PeriodChange:
    """Per-field current-vs-baseline inside a date window.

    ``had_measurement`` is true when any row falls in ``[start, end]``, even a
    weight-only one. Fields without a current value in the window are ``None``.
    """

    had_measurement: bool
    weight_kg: FieldSnapshot | None = None
    waist_cm: FieldSnapshot | None = None
    chest_cm: FieldSnapshot | None = None
    hips_cm: FieldSnapshot | None = None
    thigh_cm: FieldSnapshot | None = None
    arm_cm: FieldSnapshot | None = None


@dataclass(frozen=True)
class ReportBody:
    """Goal + period change + tone + pace + energy, ready for the weekly/monthly report formatter.

    ``profile_nudge`` lists the profile answers to ask for; empty unless this
    report is the one that carries the one-time nudge.
    """

    change: PeriodChange
    goal: UserGoal | None
    tone: PeriodTone
    kg_left: float | None
    pace: PaceStats | None
    energy: EnergyStats | None
    profile_nudge: tuple[ProfileField, ...]


def build_period_change(rows: list[BodyMeasurement], start: date, end: date) -> PeriodChange:
    """Latest in-window value per field, delta against the last value before ``start``.

    No current in ``[start, end]`` → field omitted (pre-period values are not
    inherited). No baseline → value without a delta. Newest ``(recorded_on, id)``
    wins on the same day, same as the all-time snapshot.
    """
    newest_first = sorted(rows, key=lambda r: (r.recorded_on, r.id), reverse=True)
    in_period = [r for r in newest_first if start <= r.recorded_on <= end]
    before = [r for r in newest_first if r.recorded_on < start]
    return PeriodChange(
        had_measurement=bool(in_period),
        **{field: _period_field(in_period, before, field) for field in FIELDS},
    )


def period_tone(change: PeriodChange, goal: UserGoal | None) -> PeriodTone:
    """Classify the period's weight change against the goal; circumferences ignored."""
    if goal is None or change.weight_kg is None:
        return "none"

    current = change.weight_kg.value
    target = goal.target_weight_kg
    if target is not None and at_or_past_target(current, target, goal.goal_type):
        return "reached"

    delta = change.weight_kg.delta
    if delta is None:
        return "none"

    if goal.goal_type == "maintain":
        return "progress" if abs(delta) < MAINTAIN_NOISE_KG else "setback"

    if abs(delta) < WEIGHT_NOISE_KG:
        return "none"
    if goal.goal_type == "lose":
        return "progress" if delta < 0 else "setback"
    return "progress" if delta > 0 else "setback"


def delta_is_good(delta: float, goal_type: GoalType | None) -> bool | None:
    """Whether a signed measurement delta is toward the goal.

    ``None`` when there is no preferred direction (no goal, maintain, or zero).
    Circumferences use the same polarity as weight: down is good on lose, up on
    gain/muscle.
    """
    direction = goal_direction(goal_type) if goal_type is not None else 0
    if direction == 0 or delta == 0:
        return None
    return delta * direction > 0


def goal_direction(goal_type: GoalType) -> int:
    """-1 when the goal wants the weight down, +1 up, 0 for maintain."""
    if goal_type == "lose":
        return -1
    if goal_type in ("gain", "muscle"):
        return 1
    return 0


def latest_weight_kg(rows: list[BodyMeasurement]) -> float | None:
    """Newest non-null weight in ``rows`` (any order); circumference-only rows are skipped."""
    newest_first = sorted(rows, key=lambda r: (r.recorded_on, r.id), reverse=True)
    latest = _latest_non_null(newest_first, "weight_kg")
    return latest[0] if latest is not None else None


def kg_left(change: PeriodChange, goal: UserGoal | None) -> float | None:
    """``abs(target - current)`` when both weights are known, else ``None``."""
    if goal is None or goal.target_weight_kg is None or change.weight_kg is None:
        return None
    return abs(goal.target_weight_kg - change.weight_kg.value)


def _period_field(
    in_period: list[BodyMeasurement],
    before: list[BodyMeasurement],
    field: MeasurementField,
) -> FieldSnapshot | None:
    current = _latest_non_null(in_period, field)
    if current is None:
        return None
    value, recorded_on = current
    baseline = _latest_non_null(before, field)
    if baseline is None:
        return FieldSnapshot(value=value, recorded_on=recorded_on, delta=None, previous_on=None)
    prev_value, previous_on = baseline
    return FieldSnapshot(
        value=value,
        recorded_on=recorded_on,
        delta=value - prev_value,
        previous_on=previous_on,
    )


def _latest_non_null(
    rows: list[BodyMeasurement], field: MeasurementField
) -> tuple[float, date] | None:
    for row in rows:
        value: float | None = getattr(row, field)
        if value is not None:
            return value, row.recorded_on
    return None


def at_or_past_target(current: float, target: float, goal_type: GoalType) -> bool:
    """Within the noise band of ``target``, or beyond it in the goal's direction."""
    if abs(current - target) < WEIGHT_NOISE_KG:
        return True
    return (current - target) * goal_direction(goal_type) > 0
