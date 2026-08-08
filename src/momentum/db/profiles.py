"""All queries for the ``user_profiles`` table.

Every write is an upsert: the row is created lazily the first time the user
answers any profile question, and `users` stays untouched (identity only)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from momentum.db import tables
from momentum.db.engine import new_session
from momentum.db.models import Sex, UserProfile, now_iso


async def get_profile(user_id: int) -> UserProfile | None:
    async with new_session() as s:
        row = (
            await s.execute(select(tables.UserProfile).where(tables.UserProfile.user_id == user_id))
        ).scalar_one_or_none()
    if row is None:
        return None
    return UserProfile(
        user_id=row.user_id,
        sex=row.sex,
        birth_date=row.birth_date,
        height_cm=row.height_cm,
    )


async def _upsert(user_id: int, **fields: Any) -> None:
    """Insert the row or update just ``fields``, always bumping ``updated_at``."""
    now = now_iso()
    stmt = insert(tables.UserProfile).values(
        user_id=user_id, created_at=now, updated_at=now, **fields
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[tables.UserProfile.user_id],
        set_={**{name: getattr(stmt.excluded, name) for name in fields}, "updated_at": now},
    )
    async with new_session() as s:
        await s.execute(stmt)
        await s.commit()


async def upsert_profile(
    *,
    user_id: int,
    sex: Sex | None = None,
    birth_date: date | None = None,
    height_cm: float | None = None,
) -> None:
    """Write all three fields at once — the onboarding save."""
    await _upsert(user_id, sex=sex, birth_date=birth_date, height_cm=height_cm)


async def set_sex(user_id: int, sex: Sex | None) -> None:
    await _upsert(user_id, sex=sex)


async def set_birth_date(user_id: int, birth_date: date | None) -> None:
    await _upsert(user_id, birth_date=birth_date)


async def set_height_cm(user_id: int, height_cm: float | None) -> None:
    await _upsert(user_id, height_cm=height_cm)
