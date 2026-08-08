"""All queries for the ``user_goals`` table.

Every query is scoped by ``user_id``. One active goal per user is enforced by
the partial unique index ``ux_user_goals_active``; swapping an active goal for a
new one is deliberately not supported yet, so callers create a goal only after
``get_active_goal`` came back empty."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import insert, select

from momentum.db import tables
from momentum.db.engine import new_session
from momentum.db.models import GoalType, UserGoal, now_iso, to_datetime


def _goal_from_row(row: Any) -> UserGoal:
    return UserGoal(
        id=row.id,
        user_id=row.user_id,
        goal_type=row.goal_type,
        start_weight_kg=row.start_weight_kg,
        target_weight_kg=row.target_weight_kg,
        target_date=row.target_date,
        note=row.note or "",
        is_active=bool(row.is_active),
        created_at=to_datetime(row.created_at),
    )


async def get_active_goal(user_id: int) -> UserGoal | None:
    async with new_session() as s:
        row = (
            await s.execute(
                select(tables.UserGoal).where(
                    tables.UserGoal.user_id == user_id,
                    tables.UserGoal.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
    return _goal_from_row(row) if row else None


async def create_goal(
    *,
    user_id: int,
    goal_type: GoalType,
    start_weight_kg: float | None = None,
    target_weight_kg: float | None = None,
    target_date: date | None = None,
    note: str = "",
) -> int:
    async with new_session() as s:
        result = await s.execute(
            insert(tables.UserGoal).values(
                user_id=user_id,
                goal_type=goal_type,
                start_weight_kg=start_weight_kg,
                target_weight_kg=target_weight_kg,
                target_date=target_date,
                note=note,
                created_at=now_iso(),
            )
        )
        await s.commit()
    return int(result.inserted_primary_key[0])
