"""All queries for the ``body_measurements`` table.

Every query is scoped by ``user_id``. Rows are append-only history: the same day
may hold several measurements, and the newest one wins in the reports."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import insert, select

from momentum.db import tables
from momentum.db.engine import new_session
from momentum.db.models import BodyMeasurement, now_iso, to_datetime

# Newest first, with the insertion order breaking same-day ties.
_ORDER_NEWEST = (tables.BodyMeasurement.recorded_on.desc(), tables.BodyMeasurement.id.desc())


def _measurement_from_row(row: Any) -> BodyMeasurement:
    return BodyMeasurement(
        id=row.id,
        user_id=row.user_id,
        recorded_on=row.recorded_on,
        weight_kg=row.weight_kg,
        waist_cm=row.waist_cm,
        chest_cm=row.chest_cm,
        hips_cm=row.hips_cm,
        thigh_cm=row.thigh_cm,
        arm_cm=row.arm_cm,
        note=row.note or "",
        created_at=to_datetime(row.created_at),
    )


async def add_measurement(
    *,
    user_id: int,
    recorded_on: date,
    weight_kg: float | None = None,
    waist_cm: float | None = None,
    chest_cm: float | None = None,
    hips_cm: float | None = None,
    thigh_cm: float | None = None,
    arm_cm: float | None = None,
    note: str = "",
) -> int:
    async with new_session() as s:
        result = await s.execute(
            insert(tables.BodyMeasurement).values(
                user_id=user_id,
                recorded_on=recorded_on,
                weight_kg=weight_kg,
                waist_cm=waist_cm,
                chest_cm=chest_cm,
                hips_cm=hips_cm,
                thigh_cm=thigh_cm,
                arm_cm=arm_cm,
                note=note,
                created_at=now_iso(),
            )
        )
        await s.commit()
    return int(result.inserted_primary_key[0])


async def latest_measurement(user_id: int) -> BodyMeasurement | None:
    async with new_session() as s:
        row = (
            await s.execute(
                select(tables.BodyMeasurement)
                .where(tables.BodyMeasurement.user_id == user_id)
                .order_by(*_ORDER_NEWEST)
                .limit(1)
            )
        ).scalar_one_or_none()
    return _measurement_from_row(row) if row else None


async def latest_weight(user_id: int) -> float | None:
    """Most recent non-null weight — a measurement may hold circumferences only."""
    async with new_session() as s:
        return await s.scalar(
            select(tables.BodyMeasurement.weight_kg)
            .where(
                tables.BodyMeasurement.user_id == user_id,
                tables.BodyMeasurement.weight_kg.is_not(None),
            )
            .order_by(*_ORDER_NEWEST)
            .limit(1)
        )


async def list_measurements(user_id: int, limit: int, offset: int) -> list[BodyMeasurement]:
    """A page of measurements, newest first."""
    async with new_session() as s:
        rows = (
            (
                await s.execute(
                    select(tables.BodyMeasurement)
                    .where(tables.BodyMeasurement.user_id == user_id)
                    .order_by(*_ORDER_NEWEST)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
    return [_measurement_from_row(r) for r in rows]
