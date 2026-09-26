"""Actual vs planned weight pace, plus the pace presets the goal flow offers.

Pure functions over measurement rows — no aiogram or DB imports, no Russian copy.
The actual pace is a least-squares slope over every weigh-in in the window, not
first-minus-last: weight swings ±1 kg a day on water and salt, and one outlier at
either end would flip the verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from momentum.db.models import BodyMeasurement, GoalType, UserGoal
from momentum.services import periods
from momentum.services.measurements import (
    MAINTAIN_NOISE_KG,
    WEIGHT_NOISE_KG,
    at_or_past_target,
    goal_direction,
)

PaceStatus = Literal["ahead", "on_track", "behind", "stalled", "unsafe", "none"]

WEEKS_PER_MONTH = 4.345
PACE_WINDOW_WEEKS = 8
# Weigh-ins closer together than this make a slope out of water noise.
MIN_SPAN_DAYS = 7
# Within ±25% of the planned pace counts as on track.
ON_TRACK_TOLERANCE = 0.25
# Losing more than this share of body weight a week costs muscle, not just fat.
UNSAFE_WEEKLY_LOSS_SHARE = 0.01
# A first-diet-week water drop looks unsafe on two points; the warning needs a real trend.
UNSAFE_MIN_POINTS = 3
UNSAFE_MIN_SPAN_DAYS = 14
# A projection further out than this is a guess, not a forecast.
MAX_PROJECTION_WEEKS = 104

# kg/month, unsigned. Maintain has none: its planned pace is zero by definition.
RATE_PRESETS: dict[GoalType, tuple[float, ...]] = {
    "lose": (1.0, 2.0, 3.0),
    "gain": (0.5, 1.0, 2.0),
    # Muscle grows ~0.5–1 kg/month even for a beginner; anything faster is water and fat.
    "muscle": (0.5, 1.0),
}


@dataclass(frozen=True)
class PaceStats:
    """Weight pace over the window, in signed kg/week (minus = losing).

    ``required_kg_per_week`` is ``None`` when the pace question was skipped and
    ``0`` for maintain. With no plan, moving toward the goal is ``on_track``;
    ``stalled`` covers both standing still and moving away. For maintain,
    ``on_track`` means the weight holds and ``behind`` that it drifts either
    way. ``unsafe`` is lose-only. ``none`` means nothing to report: too few
    weigh-ins, or the target is already reached. ``projected_date`` is ``None``
    when the trend never reaches the target (or not within
    ``MAX_PROJECTION_WEEKS``).
    """

    actual_kg_per_week: float
    required_kg_per_week: float | None
    projected_date: date | None
    status: PaceStatus
    points: int


def rate_presets(goal_type: GoalType) -> tuple[float, ...]:
    """Pace choices for the goal flow; empty when there is nothing to ask."""
    return RATE_PRESETS.get(goal_type, ())


def pace_range(ref: date) -> tuple[date, date]:
    """Weigh-ins that feed the pace: the ``PACE_WINDOW_WEEKS`` up to and including ``ref``."""
    return periods.shift_weeks(ref, -PACE_WINDOW_WEEKS), ref


def build_pace(rows: list[BodyMeasurement], goal: UserGoal | None, ref: date) -> PaceStats | None:
    """Actual pace vs the goal's plan; ``None`` without a goal.

    ``rows`` may be in any order and reach outside the window — only weigh-ins
    inside ``pace_range(ref)`` count. The projection starts from the trend line
    at the latest weigh-in, so one salty day doesn't move the date by weeks.
    """
    if goal is None:
        return None

    start, end = pace_range(ref)
    weighins = [
        (r.recorded_on, r.weight_kg)
        for r in sorted(rows, key=lambda r: (r.recorded_on, r.id))
        if r.weight_kg is not None and start <= r.recorded_on <= end
    ]
    required = _required_kg_per_week(goal)
    points = len(weighins)

    span_days = (weighins[-1][0] - weighins[0][0]).days if weighins else 0
    if span_days < MIN_SPAN_DAYS:
        return _nothing_to_report(required, points)

    latest_on, latest_kg = weighins[-1]
    target = goal.target_weight_kg
    if target is not None and at_or_past_target(latest_kg, target, goal.goal_type):
        return _nothing_to_report(required, points)

    slope_per_day, trend_kg = _trend(weighins)
    actual = slope_per_day * 7
    if _is_unsafe(goal.goal_type, actual, latest_kg, points, span_days):
        status: PaceStatus = "unsafe"
    else:
        status = _status(goal.goal_type, actual, required, span_days / 7)
    projected = None if status == "stalled" else _projected_date(goal, actual, latest_on, trend_kg)
    return PaceStats(
        actual_kg_per_week=actual,
        required_kg_per_week=required,
        projected_date=projected,
        status=status,
        points=points,
    )


def _nothing_to_report(required: float | None, points: int) -> PaceStats:
    return PaceStats(
        actual_kg_per_week=0.0,
        required_kg_per_week=required,
        projected_date=None,
        status="none",
        points=points,
    )


def _required_kg_per_week(goal: UserGoal) -> float | None:
    if goal.goal_type == "maintain":
        return 0.0
    if goal.target_rate_kg_per_month is None:
        return None
    return goal_direction(goal.goal_type) * goal.target_rate_kg_per_month / WEEKS_PER_MONTH


def _trend(weighins: list[tuple[date, float]]) -> tuple[float, float]:
    """Least-squares (slope kg/day, fitted weight at the latest weigh-in).

    The caller guarantees at least two distinct dates.
    """
    origin = weighins[0][0]
    xs = [(recorded_on - origin).days for recorded_on, _ in weighins]
    ys = [weight for _, weight in weighins]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    slope = sxy / sxx
    return slope, mean_y + slope * (xs[-1] - mean_x)


def _is_unsafe(
    goal_type: GoalType, actual: float, weight_kg: float, points: int, span_days: int
) -> bool:
    """Losing too fast on purpose; other goals losing weight read as stalled/drifting."""
    return (
        goal_type == "lose"
        and points >= UNSAFE_MIN_POINTS
        and span_days >= UNSAFE_MIN_SPAN_DAYS
        and -actual > UNSAFE_WEEKLY_LOSS_SHARE * weight_kg
    )


def _status(
    goal_type: GoalType, actual: float, required: float | None, span_weeks: float
) -> PaceStatus:
    """Classify the trend; "near zero" means the line moved less than the noise band."""
    drift_kg = abs(actual) * span_weeks
    if goal_type == "maintain":
        return "on_track" if drift_kg < MAINTAIN_NOISE_KG else "behind"

    toward = actual * goal_direction(goal_type)
    if toward <= 0 or drift_kg < WEIGHT_NOISE_KG:
        return "stalled"
    if required is None:
        return "on_track"

    ratio = toward / abs(required)
    if ratio > 1 + ON_TRACK_TOLERANCE:
        return "ahead"
    if ratio >= 1 - ON_TRACK_TOLERANCE:
        return "on_track"
    return "behind"


def _projected_date(goal: UserGoal, actual: float, latest_on: date, trend_kg: float) -> date | None:
    """When the current trend hits the target; ``None`` if it never does."""
    target = goal.target_weight_kg
    direction = goal_direction(goal.goal_type)
    toward = actual * direction
    if target is None or toward <= 0:
        return None
    left_kg = max((target - trend_kg) * direction, 0.0)
    weeks = left_kg / toward
    if weeks > MAX_PROJECTION_WEEKS:
        return None
    return latest_on + timedelta(weeks=weeks)
