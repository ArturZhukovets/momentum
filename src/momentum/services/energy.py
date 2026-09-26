"""Energy estimate: workout burn (MET), basal rate (Mifflin–St Jeor) and a daily intake guide.

Pure functions over numbers and rows — no aiogram or DB imports, no Russian copy.
Both formulas carry a spread of a couple hundred kcal, so every figure meant for
the user is rounded to ``ROUND_KCAL_TO``. Nothing is calibrated against the actual
weight trend: food isn't tracked, so a plan-vs-fact gap can't be pinned on either
the intake or the burn.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from momentum.db.models import Sex, UserGoal, UserProfile, WorkoutStatRow, WorkoutType
from momentum.services import periods
from momentum.services.measurements import at_or_past_target
from momentum.services.pace import WEEKS_PER_MONTH, planned_kg_per_month
from momentum.services.workout_types import EFFORT_VALUES

ProfileField = Literal["birth_date", "sex", "height_cm"]

# What the basal rate needs from the profile, in onboarding order.
PROFILE_FIELDS: tuple[ProfileField, ...] = ("birth_date", "sex", "height_cm")

# Compendium of Physical Activities (Ainsworth et al.); inner keys are `EFFORT_VALUES`.
MET_BY_EFFORT: dict[WorkoutType, dict[str, float]] = {
    "running": {"easy": 8.3, "moderate": 9.8, "hard": 11.8},
    "swimming": {"easy": 5.8, "moderate": 8.3, "hard": 10.0},
    "elliptical": {"easy": 5.0, "moderate": 7.0, "hard": 9.0},
    "gym": {"easy": 3.5, "moderate": 5.0, "hard": 6.0},
    "home_workout": {"easy": 3.8, "moderate": 5.5, "hard": 7.0},
}
# A skipped effort question reads as an ordinary session.
DEFAULT_EFFORT = "moderate"
# kcal/min = MET × 3.5 × kg / 200: 1 MET is 3.5 ml O₂ per kg per minute, ~5 kcal per litre O₂.
KCAL_PER_MET_KG_MIN = 3.5 / 200

# Mifflin–St Jeor (1990): 10 × kg + 6.25 × cm − 5 × age + a sex offset.
MIFFLIN_SEX_OFFSET: dict[Sex, float] = {"male": 5, "female": -161}
# Sedentary activity level: everyday life with no training on top.
BASELINE_ACTIVITY_FACTOR = 1.2
# Energy in ~1 kg of body fat (the classic 3500 kcal per pound).
KCAL_PER_KG = 7700
# The month the pace line uses, so "2 kg a month" means the same thing across the report.
DAYS_PER_MONTH = WEEKS_PER_MONTH * 7
ROUND_KCAL_TO = 50
# Workout burn is averaged over the days elapsed, but never fewer than a week's worth,
# so one fresh session isn't spread over a single day.
MIN_AVERAGING_DAYS = 7


@dataclass(frozen=True)
class EnergyStats:
    """Daily burn and intake guide for one report period.

    Every kcal field except ``bmr`` is rounded to ``ROUND_KCAL_TO``. Workout
    figures cover only workouts with a recorded duration; the rest are
    ``skipped_workouts``. ``target_kg_per_month`` is the goal's signed pace
    (``0`` for maintain) and ``None`` when there is no guide to give: no goal, a
    skipped pace, or the target already reached. ``daily_target`` is ``None``
    then, and also when the guide would fall below the basal rate — the one
    number the report refuses to print (``below_floor``).
    """

    workout_kcal: int
    counted_workouts: int
    skipped_workouts: int
    bmr: int
    daily_workout_kcal: int
    daily_burn: int
    target_kg_per_month: float | None
    daily_target: int | None
    below_floor: bool


def missing_profile_fields(profile: UserProfile | None) -> tuple[ProfileField, ...]:
    """Profile answers the basal rate needs but the user skipped (all of them without a row)."""
    if profile is None:
        return PROFILE_FIELDS
    return tuple(field for field in PROFILE_FIELDS if getattr(profile, field) is None)


def basal_rate(sex: Sex, age: int, height_cm: float, weight_kg: float) -> float:
    """Mifflin–St Jeor resting burn, kcal/day."""
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + MIFFLIN_SEX_OFFSET[sex]


def session_kcal(workout: WorkoutStatRow, weight_kg: float) -> float | None:
    """Burn of one workout; ``None`` without a duration. A missing effort counts as moderate."""
    if workout.duration_min is None:
        return None
    effort = workout.effort if workout.effort in EFFORT_VALUES else DEFAULT_EFFORT
    met = MET_BY_EFFORT[workout.workout_type][effort]
    return met * KCAL_PER_MET_KG_MIN * weight_kg * workout.duration_min


def build_energy(
    profile: UserProfile | None,
    weight_kg: float | None,
    goal: UserGoal | None,
    workouts: list[WorkoutStatRow],
    start: date,
    end: date,
    ref: date,
) -> EnergyStats | None:
    """Burn and guide for ``[start, end]`` as of ``ref``; ``None`` without sex, age, height, weight.

    ``workouts`` may reach outside the window — only in-window rows count. The
    workout burn is averaged over the days elapsed by ``ref`` (at least
    ``MIN_AVERAGING_DAYS``), so an in-progress month isn't diluted by days that
    haven't happened; a finished period averages over all of its days.
    """
    if (
        weight_kg is None
        or profile is None
        or profile.sex is None
        or profile.birth_date is None
        or profile.height_cm is None
    ):
        return None

    age = periods.years_since(profile.birth_date, ref)
    bmr = basal_rate(profile.sex, age, profile.height_cm, weight_kg)

    in_period = [w for w in workouts if start <= w.performed_on <= end]
    burns = [kcal for w in in_period if (kcal := session_kcal(w, weight_kg)) is not None]
    workout_total = sum(burns)
    elapsed_days = (min(ref, end) - start).days + 1
    daily_workouts = workout_total / max(elapsed_days, MIN_AVERAGING_DAYS)
    daily_burn = bmr * BASELINE_ACTIVITY_FACTOR + daily_workouts

    kg_per_month = _guide_kg_per_month(goal, weight_kg)
    target = None
    if kg_per_month is not None:
        target = _round_kcal(daily_burn + kg_per_month * KCAL_PER_KG / DAYS_PER_MONTH)
    # "About BMR" is the basal rate rounded like the guide itself; below it, no number.
    below_floor = target is not None and target < _round_kcal(bmr)

    return EnergyStats(
        # A short session still burned something; it must not read as «~0 kcal».
        workout_kcal=max(_round_kcal(workout_total), ROUND_KCAL_TO) if burns else 0,
        counted_workouts=len(burns),
        skipped_workouts=len(in_period) - len(burns),
        bmr=round(bmr),
        daily_workout_kcal=_round_kcal(daily_workouts),
        daily_burn=_round_kcal(daily_burn),
        target_kg_per_month=kg_per_month,
        daily_target=None if below_floor else target,
        below_floor=below_floor,
    )


def _guide_kg_per_month(goal: UserGoal | None, weight_kg: float) -> float | None:
    """The pace the guide is built for; ``None`` once a lose/gain/muscle target is reached."""
    if goal is None:
        return None
    target = goal.target_weight_kg
    reached = (
        goal.goal_type != "maintain"
        and target is not None
        and at_or_past_target(weight_kg, target, goal.goal_type)
    )
    return None if reached else planned_kg_per_month(goal)


def _round_kcal(kcal: float) -> int:
    return round(kcal / ROUND_KCAL_TO) * ROUND_KCAL_TO
