"""The fact snapshot a coach comment is written from, plus the flags the triage routes on.

Pure — no aiogram, DB or LangGraph imports, no Russian copy. Built from what the
report already computed (stats, ``ReportBody``, profile), so the comment reads
the same numbers the report prints: kg and cm rounded to one decimal, kcal as the
energy block rounds them. The guard checks the model's numbers against these
values, so this rounding is what the report shows, not an approximation of it.
Conclusions only — no per-workout history.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

from momentum.db.models import GoalType, ReportKind, UserProfile, WorkoutType
from momentum.services.energy import EnergyStats, missing_profile_fields
from momentum.services.measurements import (
    FIELDS,
    MeasurementField,
    PeriodChange,
    ReportBody,
    at_or_past_target,
)
from momentum.services.pace import WEEKS_PER_MONTH, PaceStats, PaceStatus
from momentum.services.stats import MonthlyStats, WeeklyStats

Section = Literal["workouts", "goal", "measurements", "pace", "energy"]

# A weigh-in this recent still describes the body, even from before the period —
# so a mid-week /week isn't "blind" for someone who weighs in on Sundays.
FRESH_WEIGHIN_DAYS = 7
# Below either, the pace is a start rather than a trend, even once a slope exists.
MIN_TREND_WEIGHINS = 3
MIN_TREND_SPAN_DAYS = 14
# Recomposition: the weight trend stays inside this band while the waist clearly shrinks.
RECOMP_MAX_TREND_KG_PER_MONTH = 0.5
RECOMP_MIN_WAIST_DROP_CM = 1.0


@dataclass(frozen=True)
class WorkoutFacts:
    """Workouts in the period; ``streak_weeks`` is weekly-only, ``weekly_avg`` monthly-only."""

    total: int
    by_type: Mapping[WorkoutType, int]
    prev_total: int
    diff: int
    pct: int | None  # None when the previous period was zero
    weekly_goal: int
    streak_weeks: int | None
    weekly_avg: float | None


@dataclass(frozen=True)
class GoalFacts:
    """``kg_left`` needs a weigh-in inside the period; ``reached`` goes by the latest one."""

    goal_type: GoalType
    target_weight_kg: float | None
    kg_left: float | None
    reached: bool


@dataclass(frozen=True)
class MeasurementFact:
    """Latest in-period value; ``delta`` is against the last value before the period."""

    value: float
    delta: float | None


@dataclass(frozen=True)
class PaceFacts:
    """The report's pace line in signed kg/month (minus = losing)."""

    status: PaceStatus
    actual_kg_per_month: float
    planned_kg_per_month: float | None
    projected_date: date | None


@dataclass(frozen=True)
class EnergyFacts:
    daily_burn_kcal: int
    daily_workout_kcal: int
    period_workout_kcal: int
    daily_target_kcal: int | None
    target_kg_per_month: float | None
    below_floor: bool


@dataclass(frozen=True)
class ReportFlags:
    """Data completeness and the pace verdict — everything the triage routes on.

    ``weighins_in_window`` counts the pace window's weigh-ins and is ``0``
    without a goal (no pace is built then). ``has_fresh_weighin``: one inside
    the period or within ``FRESH_WEIGHIN_DAYS`` of it. ``trend_ready``: the pace
    has a verdict backed by ``MIN_TREND_WEIGHINS`` over ``MIN_TREND_SPAN_DAYS``.
    """

    has_workouts: bool
    has_measurement: bool
    has_goal: bool
    has_profile: bool
    has_fresh_weighin: bool
    weighins_in_window: int
    trend_ready: bool
    goal_reached: bool
    pace_status: PaceStatus
    weight_flat_waist_down: bool


@dataclass(frozen=True)
class ReportFacts:
    """One report's facts. ``pace`` is ``None`` until the trend is ready, ``goal`` without a goal.

    ``measurements`` holds only fields recorded inside the period.
    """

    kind: ReportKind
    period_start: date
    period_end: date
    flags: ReportFlags
    workouts: WorkoutFacts
    goal: GoalFacts | None
    measurements: Mapping[MeasurementField, MeasurementFact]
    pace: PaceFacts | None
    energy: EnergyFacts | None

    def payload(self, sections: Iterable[Section]) -> dict[str, Any]:
        """The period plus only ``sections`` — what one situation's prompt gets to see.

        Empty sections are left out rather than sent as ``null``. Dates stay ``date``.
        """
        data: dict[str, Any] = {
            "kind": self.kind,
            "period_start": self.period_start,
            "period_end": self.period_end,
        }
        for section in sections:
            value = getattr(self, section)
            if value:
                data[section] = _plain(value)
        return data


def build_facts(
    stats: WeeklyStats | MonthlyStats,
    body: ReportBody,
    profile: UserProfile | None,
    weekly_goal: int,
    ref: date,
) -> ReportFacts:
    """Facts for the weekly or monthly report containing ``ref``, as of ``ref``."""
    if isinstance(stats, WeeklyStats):
        kind: ReportKind = "week"
        start, end = stats.week_start, stats.week_end
        streak_weeks, weekly_avg = stats.streak, None
    else:
        kind = "month"
        start, end = stats.month_start, stats.month_end
        streak_weeks, weekly_avg = None, stats.weekly_avg

    flags = _flags(stats.total, body, profile, min(ref, end))
    return ReportFacts(
        kind=kind,
        period_start=start,
        period_end=end,
        flags=flags,
        workouts=WorkoutFacts(
            total=stats.total,
            by_type=dict(stats.by_type),
            prev_total=stats.prev_total,
            diff=stats.diff,
            pct=stats.pct,
            weekly_goal=weekly_goal,
            streak_weeks=streak_weeks,
            weekly_avg=weekly_avg,
        ),
        goal=_goal_facts(body, flags.goal_reached),
        measurements=_measurement_facts(body.change),
        pace=_pace_facts(body.pace) if flags.trend_ready and body.pace is not None else None,
        energy=_energy_facts(body.energy) if body.energy is not None else None,
    )


def _flags(
    workouts_total: int, body: ReportBody, profile: UserProfile | None, as_of: date
) -> ReportFlags:
    pace = body.pace
    pace_status: PaceStatus = pace.status if pace is not None else "none"
    trend_ready = (
        pace is not None
        and pace.status != "none"
        and pace.points >= MIN_TREND_WEIGHINS
        and pace.span_days >= MIN_TREND_SPAN_DAYS
    )
    latest = body.latest_weight
    fresh = body.change.weight_kg is not None or (
        latest is not None and (as_of - latest.recorded_on).days <= FRESH_WEIGHIN_DAYS
    )
    reached = _goal_reached(body)
    return ReportFlags(
        has_workouts=workouts_total > 0,
        has_measurement=body.change.had_measurement,
        has_goal=body.goal is not None,
        has_profile=not missing_profile_fields(profile),
        has_fresh_weighin=fresh,
        weighins_in_window=pace.points if pace is not None else 0,
        trend_ready=trend_ready,
        goal_reached=reached,
        pace_status=pace_status,
        weight_flat_waist_down=trend_ready and not reached and _recomposition(body),
    )


def _goal_reached(body: ReportBody) -> bool:
    goal, latest = body.goal, body.latest_weight
    if goal is None or goal.target_weight_kg is None or latest is None:
        return False
    return at_or_past_target(latest.value, goal.target_weight_kg, goal.goal_type)


def _recomposition(body: ReportBody) -> bool:
    """A flat weight trend — not one pair of noisy weigh-ins — while the waist clearly shrinks."""
    pace, waist = body.pace, body.change.waist_cm
    if pace is None or waist is None or waist.delta is None:
        return False
    trend_kg_per_month = abs(pace.actual_kg_per_week) * WEEKS_PER_MONTH
    return (
        trend_kg_per_month < RECOMP_MAX_TREND_KG_PER_MONTH
        and waist.delta <= -RECOMP_MIN_WAIST_DROP_CM
    )


def _goal_facts(body: ReportBody, reached: bool) -> GoalFacts | None:
    goal = body.goal
    if goal is None:
        return None
    return GoalFacts(
        goal_type=goal.goal_type,
        target_weight_kg=_round_opt(goal.target_weight_kg),
        kg_left=_round_opt(body.kg_left),
        reached=reached,
    )


def _measurement_facts(change: PeriodChange) -> dict[MeasurementField, MeasurementFact]:
    facts: dict[MeasurementField, MeasurementFact] = {}
    for field in FIELDS:
        snap = getattr(change, field)
        if snap is not None:
            facts[field] = MeasurementFact(value=_round(snap.value), delta=_round_opt(snap.delta))
    return facts


def _pace_facts(pace: PaceStats) -> PaceFacts:
    planned = pace.required_kg_per_week
    return PaceFacts(
        status=pace.status,
        actual_kg_per_month=_round(pace.actual_kg_per_week * WEEKS_PER_MONTH),
        planned_kg_per_month=None if planned is None else _round(planned * WEEKS_PER_MONTH),
        projected_date=pace.projected_date,
    )


def _energy_facts(energy: EnergyStats) -> EnergyFacts:
    return EnergyFacts(
        daily_burn_kcal=energy.daily_burn,
        daily_workout_kcal=energy.daily_workout_kcal,
        period_workout_kcal=energy.workout_kcal,
        daily_target_kcal=energy.daily_target,
        target_kg_per_month=_round_opt(energy.target_kg_per_month),
        below_floor=energy.below_floor,
    )


def _round(value: float) -> float:
    """One decimal, as the report prints kg and cm; ``-0.0`` becomes ``0.0``."""
    return round(value, 1) or 0.0


def _round_opt(value: float | None) -> float | None:
    return None if value is None else _round(value)


def _plain(value: Any) -> Any:
    """A fact dataclass (or a mapping of them) as plain dicts, dates left as ``date``."""
    if isinstance(value, Mapping):
        return {key: asdict(item) for key, item in value.items()}
    return asdict(value)
