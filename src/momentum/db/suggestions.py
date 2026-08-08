"""All queries for the ``improvement_requests`` table."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select, update

from momentum.db import tables
from momentum.db.engine import new_session
from momentum.db.models import ImprovementRequest, ImprovementRequestStatus, now_iso, to_datetime


async def add_improvement_request(*, user_id: int, user_full_name: str, request_text: str) -> int:
    async with new_session() as s:
        result = await s.execute(
            insert(tables.ImprovementRequest).values(
                user_id=user_id,
                user_full_name=user_full_name,
                request_text=request_text,
                created_at=now_iso(),
            )
        )
        await s.commit()
    return int(result.inserted_primary_key[0])


async def set_improvement_request_status(request_id: int, status: ImprovementRequestStatus) -> bool:
    async with new_session() as s:
        result = await s.execute(
            update(tables.ImprovementRequest)
            .where(tables.ImprovementRequest.id == request_id)
            .values(status=status)
        )
        await s.commit()
    return result.rowcount > 0


def _improvement_request_from_row(row: Any) -> ImprovementRequest:
    return ImprovementRequest(
        id=row.id,
        user_id=row.user_id,
        user_full_name=row.user_full_name,
        request_text=row.request_text,
        status=row.status,
        created_at=to_datetime(row.created_at),
    )


async def count_improvement_requests(status: ImprovementRequestStatus | None = None) -> int:
    """`None` counts every status."""
    stmt = select(func.count()).select_from(tables.ImprovementRequest)
    if status is not None:
        stmt = stmt.where(tables.ImprovementRequest.status == status)
    async with new_session() as s:
        return int(await s.scalar(stmt) or 0)


async def list_improvement_requests(
    status: ImprovementRequestStatus | None,
    limit: int,
    offset: int,
) -> list[ImprovementRequest]:
    """A page of requests, newest first. `None` lists every status."""
    stmt = select(tables.ImprovementRequest)
    if status is not None:
        stmt = stmt.where(tables.ImprovementRequest.status == status)
    stmt = (
        stmt.order_by(
            tables.ImprovementRequest.created_at.desc(), tables.ImprovementRequest.id.desc()
        )
        .limit(limit)
        .offset(offset)
    )
    async with new_session() as s:
        rows = (await s.execute(stmt)).scalars().all()
    return [_improvement_request_from_row(r) for r in rows]


async def get_improvement_request(request_id: int) -> ImprovementRequest | None:
    async with new_session() as s:
        row = (
            await s.execute(
                select(tables.ImprovementRequest).where(tables.ImprovementRequest.id == request_id)
            )
        ).scalar_one_or_none()
    return _improvement_request_from_row(row) if row else None
