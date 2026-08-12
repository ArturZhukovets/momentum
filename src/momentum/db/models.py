"""Row dataclasses shared by the db submodules, plus date/time conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

ISO_DATE = "%Y-%m-%d"

ImprovementRequestStatus = Literal["new", "done", "rejected"]
Sex = Literal["male", "female"]
GoalType = Literal["lose", "gain", "maintain", "muscle"]
WorkoutType = Literal["running", "swimming", "elliptical", "gym", "home_workout"]


@dataclass(frozen=True)
class Workout:
    id: int
    user_id: int
    workout_type: WorkoutType
    performed_on: date
    description: str
    duration_min: int | None = None
    distance_km: float | None = None
    effort: str | None = None
    body_parts: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkoutPoint:
    """Minimal row used by the pure stats builders."""

    performed_on: date
    workout_type: WorkoutType


@dataclass(frozen=True)
class UserRow:
    """The middleware/settings row — identity plus the report subscription."""

    user_id: int
    username: str | None
    first_name: str | None
    reports_on: bool


@dataclass(frozen=True)
class UserBrief:
    """The browse row — identity plus signup date and workout count."""

    user_id: int
    username: str | None
    first_name: str | None
    created_at: datetime
    workout_count: int


@dataclass(frozen=True)
class ImprovementRequest:
    id: int
    user_id: int
    user_full_name: str
    request_text: str
    status: ImprovementRequestStatus
    created_at: datetime


@dataclass(frozen=True)
class UserProfile:
    """Optional facts the user told us about themselves. Every field is skippable."""

    user_id: int
    sex: Sex | None
    birth_date: date | None
    height_cm: float | None


@dataclass(frozen=True)
class UserGoal:
    id: int
    user_id: int
    goal_type: GoalType
    start_weight_kg: float | None
    target_weight_kg: float | None
    target_date: date | None
    note: str
    is_active: bool
    created_at: datetime


@dataclass(frozen=True)
class BodyMeasurement:
    id: int
    user_id: int
    recorded_on: date
    weight_kg: float | None
    waist_cm: float | None
    chest_cm: float | None
    hips_cm: float | None
    thigh_cm: float | None
    arm_cm: float | None
    note: str
    created_at: datetime


def to_date(value: str) -> date:
    return datetime.strptime(value, ISO_DATE).date()


def to_date_opt(value: str | None) -> date | None:
    return to_date(value) if value else None


def from_date_opt(value: date | None) -> str | None:
    return value.strftime(ISO_DATE) if value is not None else None


def to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
