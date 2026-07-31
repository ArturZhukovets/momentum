"""All SQL for the ``user_profiles`` table.

Every write is an upsert: the row is created lazily the first time the user
answers any profile question, and `users` stays untouched (identity only)."""

from __future__ import annotations

from datetime import date

from momentum.db.engine import conn
from momentum.db.models import Sex, UserProfile, from_date_opt, now_iso, to_date_opt


async def get_profile(user_id: int) -> UserProfile | None:
    async with conn().execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return UserProfile(
        user_id=row["user_id"],
        sex=row["sex"],
        birth_date=to_date_opt(row["birth_date"]),
        height_cm=row["height_cm"],
    )


async def upsert_profile(
    *,
    user_id: int,
    sex: Sex | None = None,
    birth_date: date | None = None,
    height_cm: float | None = None,
) -> None:
    """Write all three fields at once — the onboarding save."""
    now = now_iso()
    await conn().execute(
        """
        INSERT INTO user_profiles (user_id, sex, birth_date, height_cm, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            sex        = excluded.sex,
            birth_date = excluded.birth_date,
            height_cm  = excluded.height_cm,
            updated_at = excluded.updated_at
        """,
        (user_id, sex, from_date_opt(birth_date), height_cm, now, now),
    )
    await conn().commit()


async def set_sex(user_id: int, sex: Sex | None) -> None:
    now = now_iso()
    await conn().execute(
        """
        INSERT INTO user_profiles (user_id, sex, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            sex        = excluded.sex,
            updated_at = excluded.updated_at
        """,
        (user_id, sex, now, now),
    )
    await conn().commit()


async def set_birth_date(user_id: int, birth_date: date | None) -> None:
    now = now_iso()
    await conn().execute(
        """
        INSERT INTO user_profiles (user_id, birth_date, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            birth_date = excluded.birth_date,
            updated_at = excluded.updated_at
        """,
        (user_id, from_date_opt(birth_date), now, now),
    )
    await conn().commit()


async def set_height_cm(user_id: int, height_cm: float | None) -> None:
    now = now_iso()
    await conn().execute(
        """
        INSERT INTO user_profiles (user_id, height_cm, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            height_cm  = excluded.height_cm,
            updated_at = excluded.updated_at
        """,
        (user_id, height_cm, now, now),
    )
    await conn().commit()
