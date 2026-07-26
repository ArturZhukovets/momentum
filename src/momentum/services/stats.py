"""WeeklyStats / MonthlyStats builders.

Pure functions over dates + a list of rows — no aiogram or DB imports, so the
same code serves the on-demand commands and the scheduled broadcast.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from momentum.db.repo import WorkoutPoint
from momentum.services import periods

STREAK_LOOKBACK_WEEKS = 52


@dataclass(frozen=True)
class WeeklyStats:
    week_start: date
    week_end: date
    total: int
    cardio: int
    strength: int
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
    cardio: int
    strength: int
    cardio_pct: int
    strength_pct: int
    weekly_avg: float
    body_parts: tuple[tuple[str, int], ...]
    prev_total: int
    diff: int
    pct: int | None


def _pct_change(total: int, prev: int) -> int | None:
    if prev == 0:
        return None
    return round((total - prev) / prev * 100)


def _in_range(points: list[WorkoutPoint], start: date, end: date) -> list[WorkoutPoint]:
    return [p for p in points if start <= p.performed_on <= end]


def _split_kinds(points: list[WorkoutPoint]) -> tuple[int, int]:
    """(cardio, strength)"""
    counts = Counter(p.kind for p in points)
    return counts.get("cardio", 0), counts.get("strength", 0)


def _weekly_totals(points: list[WorkoutPoint]) -> Counter[date]:
    return Counter(periods.week_start(p.performed_on) for p in points)


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
    """Date range the weekly builder needs points for (streak lookback included)."""
    start, end = periods.week_bounds(ref)
    return periods.shift_weeks(start, -STREAK_LOOKBACK_WEEKS), end


def build_weekly_stats(points: list[WorkoutPoint], ref: date, goal: int) -> WeeklyStats:
    """Stats for the week containing `ref`.

    `points` must cover at least `weekly_range(ref)` for the streak to be right.
    """
    start, end = periods.week_bounds(ref)
    prev_start, prev_end = periods.prev_week_bounds(ref)

    current = _in_range(points, start, end)
    cardio, strength = _split_kinds(current)
    total = len(current)
    prev_total = len(_in_range(points, prev_start, prev_end))

    month_start, _ = periods.month_bounds(ref)
    month_to_date = len(_in_range(points, month_start, ref))

    return WeeklyStats(
        week_start=start,
        week_end=end,
        total=total,
        cardio=cardio,
        strength=strength,
        prev_total=prev_total,
        diff=total - prev_total,
        pct=_pct_change(total, prev_total),
        month_to_date=month_to_date,
        streak=_streak(_weekly_totals(points), start, goal),
        goal=goal,
    )


def monthly_range(ref: date) -> tuple[date, date]:
    """Date range the monthly builder needs points for (previous month included)."""
    prev_start, _ = periods.prev_month_bounds(ref)
    _, end = periods.month_bounds(ref)
    return prev_start, end


def build_monthly_stats(
    points: list[WorkoutPoint],
    body_parts: dict[str, int],
    ref: date,
    top_parts: int = 5,
) -> MonthlyStats:
    """Stats for the month containing `ref`.

    `body_parts` is already scoped to that month by the repo.
    """
    start, end = periods.month_bounds(ref)
    prev_start, prev_end = periods.prev_month_bounds(ref)

    current = _in_range(points, start, end)
    cardio, strength = _split_kinds(current)
    total = len(current)
    prev_total = len(_in_range(points, prev_start, prev_end))

    weeks = periods.weeks_touched(start, end)
    ranked = tuple(sorted(body_parts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_parts])

    return MonthlyStats(
        month_start=start,
        month_end=end,
        total=total,
        cardio=cardio,
        strength=strength,
        cardio_pct=round(cardio / total * 100) if total else 0,
        strength_pct=round(strength / total * 100) if total else 0,
        weekly_avg=round(total / weeks, 1) if weeks else 0.0,
        body_parts=ranked,
        prev_total=prev_total,
        diff=total - prev_total,
        pct=_pct_change(total, prev_total),
    )
