"""WeeklyStats / MonthlyStats builders.

Pure functions over dates + a list of rows — no aiogram or DB imports, so the
same code serves the on-demand commands and the scheduled broadcast.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from momentum.db.models import WorkoutStatRow, WorkoutType
from momentum.services import periods
from momentum.services.workout_types import WORKOUT_TYPES

# `/week` streak walks backward week by week; this is the cap so one query covers it.
STREAK_LOOKBACK_WEEKS = 52


@dataclass(frozen=True)
class WeeklyStats:
    week_start: date
    week_end: date
    total: int
    by_type: tuple[tuple[WorkoutType, int], ...]
    prev_total: int
    diff: int
    pct: int | None  # None when the previous week was zero
    month_to_date: int
    streak: int
    goal: int


@dataclass(frozen=True)
class MonthlyStats:
    month_start: date
    month_end: date
    total: int
    by_type: tuple[tuple[WorkoutType, int], ...]
    weekly_avg: float
    body_parts: tuple[tuple[str, int], ...]
    prev_total: int
    diff: int
    pct: int | None


def _pct_change(total: int, prev: int) -> int | None:
    if prev == 0:
        return None
    return round((total - prev) / prev * 100)


def _in_range(workouts: list[WorkoutStatRow], start: date, end: date) -> list[WorkoutStatRow]:
    return [w for w in workouts if start <= w.performed_on <= end]


def _count_types(workouts: list[WorkoutStatRow]) -> tuple[tuple[WorkoutType, int], ...]:
    """Per-type counts > 0, in catalog order."""
    counts = Counter(w.workout_type for w in workouts)
    return tuple((t, counts[t]) for t in WORKOUT_TYPES if counts[t] > 0)


def _weekly_totals(workouts: list[WorkoutStatRow]) -> Counter[date]:
    return Counter(periods.week_start(w.performed_on) for w in workouts)


def _streak(totals: Counter[date], current_week_start: date, goal: int) -> int:
    """Consecutive weeks meeting the goal, walking back from the current week.

    The current week counts only when it already meets the goal; otherwise the
    walk starts from the week before it, so an in-progress week never breaks a
    streak that is still alive.
    """
    streak = 0
    cursor = current_week_start

    if totals.get(cursor, 0) >= goal:
        streak = 1
    cursor -= timedelta(weeks=1)

    for _ in range(STREAK_LOOKBACK_WEEKS):
        if totals.get(cursor, 0) < goal:
            break
        streak += 1
        cursor -= timedelta(weeks=1)

    return streak


def weekly_range(ref: date) -> tuple[date, date]:
    """Fetch window for weekly stats: current week plus ``STREAK_LOOKBACK_WEEKS`` of history.

    The report itself is only the week containing ``ref``. The extra lookback is
    so ``_streak`` can walk consecutive goal-weeks without a second query.
    """
    start, end = periods.week_bounds(ref)
    return periods.shift_weeks(start, -STREAK_LOOKBACK_WEEKS), end


def build_weekly_stats(workouts: list[WorkoutStatRow], ref: date, goal: int) -> WeeklyStats:
    """Stats for the week containing `ref`.

    ``workouts`` must cover at least ``weekly_range(ref)`` or the streak is truncated.
    """
    start, end = periods.week_bounds(ref)
    prev_start, prev_end = periods.prev_week_bounds(ref)

    current = _in_range(workouts, start, end)
    total = len(current)
    prev_total = len(_in_range(workouts, prev_start, prev_end))

    month_start, _ = periods.month_bounds(ref)
    month_to_date = len(_in_range(workouts, month_start, ref))

    return WeeklyStats(
        week_start=start,
        week_end=end,
        total=total,
        by_type=_count_types(current),
        prev_total=prev_total,
        diff=total - prev_total,
        pct=_pct_change(total, prev_total),
        month_to_date=month_to_date,
        streak=_streak(_weekly_totals(workouts), start, goal),
        goal=goal,
    )


def monthly_range(ref: date) -> tuple[date, date]:
    """Fetch window for monthly stats: this month plus the previous one (for the diff line)."""
    prev_start, _ = periods.prev_month_bounds(ref)
    _, end = periods.month_bounds(ref)
    return prev_start, end


def build_monthly_stats(
    workouts: list[WorkoutStatRow],
    body_parts: dict[str, int],
    ref: date,
    top_parts: int = 5,
) -> MonthlyStats:
    """Stats for the month containing `ref`.

    `body_parts` is already scoped to that month by the repo.
    """
    start, end = periods.month_bounds(ref)
    prev_start, prev_end = periods.prev_month_bounds(ref)

    current = _in_range(workouts, start, end)
    total = len(current)
    prev_total = len(_in_range(workouts, prev_start, prev_end))

    weeks = periods.weeks_touched(start, end)
    ranked = tuple(sorted(body_parts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_parts])

    return MonthlyStats(
        month_start=start,
        month_end=end,
        total=total,
        by_type=_count_types(current),
        weekly_avg=round(total / weeks, 1) if weeks else 0.0,
        body_parts=ranked,
        prev_total=prev_total,
        diff=total - prev_total,
        pct=_pct_change(total, prev_total),
    )
