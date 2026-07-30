"""All SQL for the ``users`` table."""

from __future__ import annotations

from typing import Any

from momentum.db.engine import conn
from momentum.db.models import UserBrief, UserRow, now_iso, to_datetime


async def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    await conn().execute(
        """
        INSERT INTO users (user_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username   = excluded.username,
            first_name = excluded.first_name
        """,
        (user_id, username, first_name, now_iso()),
    )
    await conn().commit()


async def set_reports_on(user_id: int, enabled: bool) -> None:
    await conn().execute(
        "UPDATE users SET reports_on = ? WHERE user_id = ?",
        (1 if enabled else 0, user_id),
    )
    await conn().commit()


async def get_reports_on(user_id: int) -> bool:
    async with conn().execute("SELECT reports_on FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    return bool(row["reports_on"]) if row else True


async def list_subscribers() -> list[UserRow]:
    async with conn().execute(
        """
        SELECT user_id, username, first_name, reports_on
        FROM users
        WHERE reports_on = 1
        ORDER BY user_id
        """
    ) as cur:
        rows = await cur.fetchall()
    return [
        UserRow(
            user_id=r["user_id"],
            username=r["username"],
            first_name=r["first_name"],
            reports_on=bool(r["reports_on"]),
        )
        for r in rows
    ]


def _user_brief_from_row(row: Any) -> UserBrief:
    return UserBrief(
        user_id=row["user_id"],
        username=row["username"],
        first_name=row["first_name"],
        created_at=to_datetime(row["created_at"]),
        workout_count=int(row["workout_count"]),
    )


# One aggregate instead of a count query per user.
_USER_BRIEF_SELECT = """
    SELECT u.user_id, u.username, u.first_name, u.created_at,
           COUNT(w.id) AS workout_count
    FROM users u
    LEFT JOIN workouts w ON w.user_id = u.user_id
"""


async def count_users() -> int:
    async with conn().execute("SELECT COUNT(*) AS n FROM users") as cur:
        row = await cur.fetchone()
    return int(row["n"])


async def list_users(limit: int, offset: int) -> list[UserBrief]:
    """A page of registered users, newest first, with their workout counts."""
    async with conn().execute(
        f"""
        {_USER_BRIEF_SELECT}
        GROUP BY u.user_id
        ORDER BY u.created_at DESC, u.user_id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ) as cur:
        rows = await cur.fetchall()
    return [_user_brief_from_row(r) for r in rows]


async def get_user(user_id: int) -> UserBrief | None:
    async with conn().execute(
        f"""
        {_USER_BRIEF_SELECT}
        WHERE u.user_id = ?
        GROUP BY u.user_id
        """,
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    return _user_brief_from_row(row) if row else None
