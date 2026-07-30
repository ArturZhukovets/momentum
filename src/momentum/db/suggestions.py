"""All SQL for the ``improvement_requests`` table."""

from __future__ import annotations

from typing import Any

from momentum.db.engine import conn
from momentum.db.models import ImprovementRequest, ImprovementRequestStatus, now_iso, to_datetime


async def add_improvement_request(*, user_id: int, user_full_name: str, request_text: str) -> int:
    cur = await conn().execute(
        """
        INSERT INTO improvement_requests (user_id, user_full_name, request_text, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, user_full_name, request_text, now_iso()),
    )
    await conn().commit()
    return int(cur.lastrowid)


async def set_improvement_request_status(request_id: int, status: ImprovementRequestStatus) -> bool:
    cur = await conn().execute(
        "UPDATE improvement_requests SET status = ? WHERE id = ?",
        (status, request_id),
    )
    await conn().commit()
    return cur.rowcount > 0


def _improvement_request_from_row(row: Any) -> ImprovementRequest:
    return ImprovementRequest(
        id=row["id"],
        user_id=row["user_id"],
        user_full_name=row["user_full_name"],
        request_text=row["request_text"],
        status=row["status"],
        created_at=to_datetime(row["created_at"]),
    )


async def count_improvement_requests(status: ImprovementRequestStatus | None = None) -> int:
    """`None` counts every status."""
    where = "" if status is None else "WHERE status = ?"
    params = () if status is None else (status,)
    async with conn().execute(
        f"SELECT COUNT(*) AS n FROM improvement_requests {where}", params
    ) as cur:
        row = await cur.fetchone()
    return int(row["n"])


async def list_improvement_requests(
    status: ImprovementRequestStatus | None,
    limit: int,
    offset: int,
) -> list[ImprovementRequest]:
    """A page of requests, newest first. `None` lists every status."""
    where = "" if status is None else "WHERE status = ?"
    params: tuple[Any, ...] = (limit, offset) if status is None else (status, limit, offset)
    async with conn().execute(
        f"""
        SELECT * FROM improvement_requests
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ) as cur:
        rows = await cur.fetchall()
    return [_improvement_request_from_row(r) for r in rows]


async def get_improvement_request(request_id: int) -> ImprovementRequest | None:
    async with conn().execute(
        "SELECT * FROM improvement_requests WHERE id = ?", (request_id,)
    ) as cur:
        row = await cur.fetchone()
    return _improvement_request_from_row(row) if row else None
