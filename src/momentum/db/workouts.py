"""All queries for the ``workouts`` / ``workout_body_parts`` tables.

Every query is scoped by ``user_id`` so ids can't be poked cross-user."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from momentum.db import tables
from momentum.db.engine import new_session
from momentum.db.models import Workout, WorkoutStatRow, WorkoutType, now_iso


async def add_workout(
    *,
    user_id: int,
    workout_type: WorkoutType,
    performed_on: date,
    description: str = "",
    duration_min: int | None = None,
    distance_km: float | None = None,
    effort: str | None = None,
    body_parts: list[str] | None = None,
) -> int:
    """Insert a workout and its body parts in one transaction."""
    async with new_session() as s:
        result = await s.execute(
            insert(tables.Workout).values(
                user_id=user_id,
                workout_type=workout_type,
                performed_on=performed_on,
                description=description,
                duration_min=duration_min,
                distance_km=distance_km,
                effort=effort,
                created_at=now_iso(),
            )
        )
        workout_id = int(result.inserted_primary_key[0])
        if body_parts:
            await s.execute(
                sqlite_insert(tables.WorkoutBodyPart).on_conflict_do_nothing(),
                [{"workout_id": workout_id, "body_part": part} for part in body_parts],
            )
        await s.commit()
    return workout_id


async def update_description(user_id: int, workout_id: int, description: str) -> bool:
    async with new_session() as s:
        result = await s.execute(
            update(tables.Workout)
            .where(tables.Workout.id == workout_id, tables.Workout.user_id == user_id)
            .values(description=description)
        )
        await s.commit()
    return result.rowcount > 0


async def update_performed_on(user_id: int, workout_id: int, performed_on: date) -> bool:
    async with new_session() as s:
        result = await s.execute(
            update(tables.Workout)
            .where(tables.Workout.id == workout_id, tables.Workout.user_id == user_id)
            .values(performed_on=performed_on)
        )
        await s.commit()
    return result.rowcount > 0


async def delete_workout(user_id: int, workout_id: int) -> bool:
    async with new_session() as s:
        result = await s.execute(
            delete(tables.Workout).where(
                tables.Workout.id == workout_id, tables.Workout.user_id == user_id
            )
        )
        await s.commit()
    return result.rowcount > 0


def _workout_from_row(row: Any, body_parts: tuple[str, ...] = ()) -> Workout:
    return Workout(
        id=row.id,
        user_id=row.user_id,
        workout_type=row.workout_type,
        performed_on=row.performed_on,
        description=row.description or "",
        duration_min=row.duration_min,
        distance_km=row.distance_km,
        effort=row.effort,
        body_parts=body_parts,
    )


async def get_workout(user_id: int, workout_id: int) -> Workout | None:
    async with new_session() as s:
        row = (
            await s.execute(
                select(tables.Workout).where(
                    tables.Workout.id == workout_id, tables.Workout.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None

        parts = tuple(
            (
                await s.execute(
                    select(tables.WorkoutBodyPart.body_part).where(
                        tables.WorkoutBodyPart.workout_id == workout_id
                    )
                )
            )
            .scalars()
            .all()
        )

    return _workout_from_row(row, parts)


async def count_workouts(user_id: int) -> int:
    async with new_session() as s:
        count = await s.scalar(
            select(func.count())
            .select_from(tables.Workout)
            .where(tables.Workout.user_id == user_id)
        )
    return int(count or 0)


async def list_workouts(user_id: int, limit: int, offset: int) -> list[Workout]:
    """A page of workouts, newest first, with body parts attached."""
    async with new_session() as s:
        rows = (
            (
                await s.execute(
                    select(tables.Workout)
                    .where(tables.Workout.user_id == user_id)
                    .order_by(tables.Workout.performed_on.desc(), tables.Workout.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )

        if not rows:
            return []

        # One query for every page's parts instead of one per workout.
        part_rows = (
            await s.execute(
                select(tables.WorkoutBodyPart.workout_id, tables.WorkoutBodyPart.body_part).where(
                    tables.WorkoutBodyPart.workout_id.in_([r.id for r in rows])
                )
            )
        ).all()

    parts_by_id: dict[int, list[str]] = {}
    for r in part_rows:
        parts_by_id.setdefault(r.workout_id, []).append(r.body_part)

    return [_workout_from_row(r, tuple(parts_by_id.get(r.id, ()))) for r in rows]


async def list_workouts_for_stats(user_id: int, start: date, end: date) -> list[WorkoutStatRow]:
    """Date + type in ``[start, end]`` — the slim projection stats builders need."""
    async with new_session() as s:
        rows = (
            await s.execute(
                select(tables.Workout.performed_on, tables.Workout.workout_type).where(
                    tables.Workout.user_id == user_id,
                    tables.Workout.performed_on.between(start, end),
                )
            )
        ).all()
    return [WorkoutStatRow(r.performed_on, r.workout_type) for r in rows]


async def body_part_counts(user_id: int, start: date, end: date) -> dict[str, int]:
    count = func.count().label("n")
    async with new_session() as s:
        rows = (
            await s.execute(
                select(tables.WorkoutBodyPart.body_part.label("part"), count)
                .join(tables.Workout, tables.Workout.id == tables.WorkoutBodyPart.workout_id)
                .where(
                    tables.Workout.user_id == user_id,
                    tables.Workout.performed_on.between(start, end),
                )
                .group_by(tables.WorkoutBodyPart.body_part)
                .order_by(count.desc(), tables.WorkoutBodyPart.body_part.asc())
            )
        ).all()
    return {r.part: r.n for r in rows}
