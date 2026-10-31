"""All queries for the ``users`` table."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert

from momentum.db import tables
from momentum.db.engine import new_session
from momentum.db.models import UserBrief, UserRow, now_iso, to_datetime


async def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    stmt = insert(tables.User).values(
        user_id=user_id, username=username, first_name=first_name, created_at=now_iso()
    )
    # created_at is deliberately not refreshed — it marks the signup.
    stmt = stmt.on_conflict_do_update(
        index_elements=[tables.User.user_id],
        set_={"username": stmt.excluded.username, "first_name": stmt.excluded.first_name},
    )
    async with new_session() as s:
        await s.execute(stmt)
        await s.commit()


async def set_reports_on(user_id: int, enabled: bool) -> None:
    async with new_session() as s:
        await s.execute(
            tables.User.__table__.update()
            .where(tables.User.user_id == user_id)
            .values(reports_on=enabled)
        )
        await s.commit()


async def get_reports_on(user_id: int) -> bool:
    async with new_session() as s:
        value = await s.scalar(select(tables.User.reports_on).where(tables.User.user_id == user_id))
    return True if value is None else bool(value)


async def list_subscribers() -> list[UserRow]:
    async with new_session() as s:
        rows = (
            await s.execute(
                select(
                    tables.User.user_id,
                    tables.User.username,
                    tables.User.first_name,
                    tables.User.reports_on,
                )
                .where(tables.User.reports_on.is_(True))
                .order_by(tables.User.user_id)
            )
        ).all()
    return [
        UserRow(
            user_id=r.user_id,
            username=r.username,
            first_name=r.first_name,
            reports_on=bool(r.reports_on),
        )
        for r in rows
    ]


# One aggregate instead of a count query per user.
_USER_BRIEF_SELECT = (
    select(
        tables.User.user_id,
        tables.User.username,
        tables.User.first_name,
        tables.User.created_at,
        func.count(tables.Workout.id).label("workout_count"),
    )
    .join(tables.Workout, tables.Workout.user_id == tables.User.user_id, isouter=True)
    .group_by(tables.User.user_id)
)


def _user_brief_from_row(row: Any) -> UserBrief:
    return UserBrief(
        user_id=row.user_id,
        username=row.username,
        first_name=row.first_name,
        created_at=to_datetime(row.created_at),
        workout_count=int(row.workout_count),
    )


async def count_users() -> int:
    async with new_session() as s:
        return int(await s.scalar(select(func.count()).select_from(tables.User)) or 0)


async def list_users(limit: int, offset: int) -> list[UserBrief]:
    """A page of registered users, newest first, with their workout counts."""
    async with new_session() as s:
        rows = (
            await s.execute(
                _USER_BRIEF_SELECT.order_by(
                    tables.User.created_at.desc(), tables.User.user_id.desc()
                )
                .limit(limit)
                .offset(offset)
            )
        ).all()
    return [_user_brief_from_row(r) for r in rows]


async def get_user(user_id: int) -> UserBrief | None:
    async with new_session() as s:
        row = (await s.execute(_USER_BRIEF_SELECT.where(tables.User.user_id == user_id))).first()
    return _user_brief_from_row(row) if row else None
