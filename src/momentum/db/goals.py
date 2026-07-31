"""All SQL for the ``user_goals`` table.

Every query is scoped by ``user_id``. One active goal per user is enforced by
the partial unique index ``ux_user_goals_active``; swapping an active goal for a
new one is deliberately not supported yet, so callers create a goal only after
``get_active_goal`` came back empty."""

from __future__ import annotations

from datetime import date
from typing import Any

from momentum.db.engine import conn
from momentum.db.models import GoalType, UserGoal, from_date_opt, now_iso, to_date_opt, to_datetime


def _goal_from_row(row: Any) -> UserGoal:
    return UserGoal(
        id=row["id"],
        user_id=row["user_id"],
        goal_type=row["goal_type"],
        start_weight_kg=row["start_weight_kg"],
        target_weight_kg=row["target_weight_kg"],
        target_date=to_date_opt(row["target_date"]),
        note=row["note"] or "",
        is_active=bool(row["is_active"]),
        created_at=to_datetime(row["created_at"]),
    )


async def get_active_goal(user_id: int) -> UserGoal | None:
    async with conn().execute(
        "SELECT * FROM user_goals WHERE user_id = ? AND is_active = 1",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
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
    cur = await conn().execute(
        """
        INSERT INTO user_goals (
            user_id, goal_type, start_weight_kg, target_weight_kg, target_date, note, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            goal_type,
            start_weight_kg,
            target_weight_kg,
            from_date_opt(target_date),
            note,
            now_iso(),
        ),
    )
    await conn().commit()
    return int(cur.lastrowid)
