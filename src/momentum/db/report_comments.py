"""All queries for the ``report_comments`` table — the coach comment cache.

Every query is scoped by ``user_id``. A row is only reused while its
``facts_hash`` still matches: the same period with new facts gets a new comment.
An empty ``comment`` is a cached "no comment": the model was asked, and no draft
passed the guard.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from momentum.db import tables
from momentum.db.engine import new_session
from momentum.db.models import ReportKind, now_iso


async def get_comment(
    user_id: int, kind: ReportKind, period_start: date, facts_hash: str
) -> str | None:
    """The cached comment for this period, unless it was written from other facts."""
    async with new_session() as s:
        return await s.scalar(
            select(tables.ReportComment.comment).where(
                tables.ReportComment.user_id == user_id,
                tables.ReportComment.kind == kind,
                tables.ReportComment.period_start == period_start,
                tables.ReportComment.facts_hash == facts_hash,
            )
        )


async def save_comment(
    user_id: int, kind: ReportKind, period_start: date, facts_hash: str, comment: str
) -> None:
    """Store the period's comment, replacing one written from older facts."""
    stmt = insert(tables.ReportComment).values(
        user_id=user_id,
        kind=kind,
        period_start=period_start,
        facts_hash=facts_hash,
        comment=comment,
        created_at=now_iso(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            tables.ReportComment.user_id,
            tables.ReportComment.kind,
            tables.ReportComment.period_start,
        ],
        set_={
            "facts_hash": stmt.excluded.facts_hash,
            "comment": stmt.excluded.comment,
            "created_at": stmt.excluded.created_at,
        },
    )
    async with new_session() as s:
        await s.execute(stmt)
        await s.commit()
