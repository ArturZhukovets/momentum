"""Row dataclasses shared by the db submodules, plus date/time conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

ISO_DATE = "%Y-%m-%d"

ImprovementRequestStatus = Literal["new", "done", "rejected"]


@dataclass(frozen=True)
class Workout:
    id: int
    user_id: int
    kind: str
    performed_on: date
    description: str
    photo_file_id: str | None
    body_parts: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkoutPoint:
    """Minimal row used by the pure stats builders."""

    performed_on: date
    kind: str


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


def to_date(value: str) -> date:
    return datetime.strptime(value, ISO_DATE).date()


def to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
