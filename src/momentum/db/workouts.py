"""All SQL for the ``workouts`` / ``workout_body_parts`` tables.

Every query is scoped by ``user_id`` so ids can't be poked cross-user."""

from __future__ import annotations

from datetime import date
from typing import Any

from momentum.db.engine import conn
from momentum.db.models import ISO_DATE, Workout, WorkoutPoint, now_iso, to_date


async def add_workout(
    *,
    user_id: int,
    kind: str,
    performed_on: date,
    description: str = "",
    photo_file_id: str | None = None,
    body_parts: list[str] | None = None,
) -> int:
    """Insert a workout and its body parts in one transaction."""
    db = conn()
    cur = await db.execute(
        """
        INSERT INTO workouts (user_id, kind, performed_on, description, photo_file_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            kind,
            performed_on.strftime(ISO_DATE),
            description,
            photo_file_id,
            now_iso(),
        ),
    )
    workout_id = int(cur.lastrowid)
    if body_parts:
        await db.executemany(
            "INSERT OR IGNORE INTO workout_body_parts (workout_id, body_part) VALUES (?, ?)",
            [(workout_id, part) for part in body_parts],
        )
    await db.commit()
    return workout_id


async def update_description(user_id: int, workout_id: int, description: str) -> bool:
    cur = await conn().execute(
        "UPDATE workouts SET description = ? WHERE id = ? AND user_id = ?",
        (description, workout_id, user_id),
    )
    await conn().commit()
    return cur.rowcount > 0


async def update_performed_on(user_id: int, workout_id: int, performed_on: date) -> bool:
    cur = await conn().execute(
        "UPDATE workouts SET performed_on = ? WHERE id = ? AND user_id = ?",
        (performed_on.strftime(ISO_DATE), workout_id, user_id),
    )
    await conn().commit()
    return cur.rowcount > 0


async def delete_workout(user_id: int, workout_id: int) -> bool:
    cur = await conn().execute(
        "DELETE FROM workouts WHERE id = ? AND user_id = ?", (workout_id, user_id)
    )
    await conn().commit()
    return cur.rowcount > 0


def _workout_from_row(row: Any, body_parts: tuple[str, ...] = ()) -> Workout:
    return Workout(
        id=row["id"],
        user_id=row["user_id"],
        kind=row["kind"],
        performed_on=to_date(row["performed_on"]),
        description=row["description"] or "",
        photo_file_id=row["photo_file_id"],
        body_parts=body_parts,
    )


async def get_workout(user_id: int, workout_id: int) -> Workout | None:
    async with conn().execute(
        "SELECT * FROM workouts WHERE id = ? AND user_id = ?", (workout_id, user_id)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None

    async with conn().execute(
        "SELECT body_part FROM workout_body_parts WHERE workout_id = ?", (workout_id,)
    ) as cur:
        parts = tuple(r["body_part"] for r in await cur.fetchall())

    return _workout_from_row(row, parts)


async def count_workouts(user_id: int) -> int:
    async with conn().execute(
        "SELECT COUNT(*) AS n FROM workouts WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    return int(row["n"])


async def list_workouts(user_id: int, limit: int, offset: int) -> list[Workout]:
    """A page of workouts, newest first, with body parts attached."""
    async with conn().execute(
        """
        SELECT * FROM workouts
        WHERE user_id = ?
        ORDER BY performed_on DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        return []

    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" * len(ids))
    async with conn().execute(
        "SELECT workout_id, body_part FROM workout_body_parts "
        f"WHERE workout_id IN ({placeholders})",
        ids,
    ) as cur:
        part_rows = await cur.fetchall()

    parts_by_id: dict[int, list[str]] = {}
    for r in part_rows:
        parts_by_id.setdefault(r["workout_id"], []).append(r["body_part"])

    return [_workout_from_row(r, tuple(parts_by_id.get(r["id"], ()))) for r in rows]


async def points_between(user_id: int, start: date, end: date) -> list[WorkoutPoint]:
    """Dates + kinds in ``[start, end]`` — the input to the stats builders."""
    async with conn().execute(
        """
        SELECT performed_on, kind FROM workouts
        WHERE user_id = ? AND performed_on BETWEEN ? AND ?
        """,
        (user_id, start.strftime(ISO_DATE), end.strftime(ISO_DATE)),
    ) as cur:
        rows = await cur.fetchall()
    return [WorkoutPoint(to_date(r["performed_on"]), r["kind"]) for r in rows]


async def body_part_counts(user_id: int, start: date, end: date) -> dict[str, int]:
    async with conn().execute(
        """
        SELECT bp.body_part AS part, COUNT(*) AS n
        FROM workout_body_parts bp
        JOIN workouts w ON w.id = bp.workout_id
        WHERE w.user_id = ? AND w.performed_on BETWEEN ? AND ?
        GROUP BY bp.body_part
        ORDER BY n DESC, part ASC
        """,
        (user_id, start.strftime(ISO_DATE), end.strftime(ISO_DATE)),
    ) as cur:
        rows = await cur.fetchall()
    return {r["part"]: r["n"] for r in rows}
