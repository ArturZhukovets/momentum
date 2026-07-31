"""All SQL for the ``body_measurements`` table.

Every query is scoped by ``user_id``. Rows are append-only history: the same day
may hold several measurements, and the newest one wins in the reports."""

from __future__ import annotations

from datetime import date
from typing import Any

from momentum.db.engine import conn
from momentum.db.models import ISO_DATE, BodyMeasurement, now_iso, to_date, to_datetime

# Newest first, with the insertion order breaking same-day ties.
_ORDER_NEWEST = "ORDER BY recorded_on DESC, id DESC"


def _measurement_from_row(row: Any) -> BodyMeasurement:
    return BodyMeasurement(
        id=row["id"],
        user_id=row["user_id"],
        recorded_on=to_date(row["recorded_on"]),
        weight_kg=row["weight_kg"],
        waist_cm=row["waist_cm"],
        chest_cm=row["chest_cm"],
        hips_cm=row["hips_cm"],
        thigh_cm=row["thigh_cm"],
        arm_cm=row["arm_cm"],
        note=row["note"] or "",
        created_at=to_datetime(row["created_at"]),
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
    cur = await conn().execute(
        """
        INSERT INTO body_measurements (
            user_id, recorded_on, weight_kg,
            waist_cm, chest_cm, hips_cm, thigh_cm, arm_cm,
            note, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            recorded_on.strftime(ISO_DATE),
            weight_kg,
            waist_cm,
            chest_cm,
            hips_cm,
            thigh_cm,
            arm_cm,
            note,
            now_iso(),
        ),
    )
    await conn().commit()
    return int(cur.lastrowid)


async def latest_measurement(user_id: int) -> BodyMeasurement | None:
    async with conn().execute(
        f"SELECT * FROM body_measurements WHERE user_id = ? {_ORDER_NEWEST} LIMIT 1",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    return _measurement_from_row(row) if row else None


async def latest_weight(user_id: int) -> float | None:
    """Most recent non-null weight — a measurement may hold circumferences only."""
    async with conn().execute(
        f"""
        SELECT weight_kg FROM body_measurements
        WHERE user_id = ? AND weight_kg IS NOT NULL
        {_ORDER_NEWEST}
        LIMIT 1
        """,
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    return row["weight_kg"] if row else None


async def list_measurements(user_id: int, limit: int, offset: int) -> list[BodyMeasurement]:
    """A page of measurements, newest first."""
    async with conn().execute(
        f"""
        SELECT * FROM body_measurements
        WHERE user_id = ?
        {_ORDER_NEWEST}
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    ) as cur:
        rows = await cur.fetchall()
    return [_measurement_from_row(r) for r in rows]
