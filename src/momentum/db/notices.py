"""All queries for the ``user_notices`` table — one-time notices, each sent at most once.

Every query is scoped by ``user_id``. A new one-time notice is a new key here,
not a new column on ``users``.
"""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert

from momentum.db import tables
from momentum.db.engine import new_session
from momentum.db.models import now_iso

# Stored in `user_notices.notice`: renaming a key sends that notice to everybody again.
PROFILE_NUDGE = "profile_nudge"


async def claim_notice(user_id: int, notice: str) -> bool:
    """Record ``notice`` as sent; ``True`` only for the call that recorded it."""
    stmt = (
        insert(tables.UserNotice)
        .values(user_id=user_id, notice=notice, sent_at=now_iso())
        .on_conflict_do_nothing(
            index_elements=[tables.UserNotice.user_id, tables.UserNotice.notice]
        )
    )
    async with new_session() as s:
        result = await s.execute(stmt)
        await s.commit()
    return result.rowcount > 0
