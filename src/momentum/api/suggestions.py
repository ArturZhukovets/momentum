from __future__ import annotations

from typing import Any, get_args

from aiohttp import web

from momentum.db import suggestions as db_suggestions
from momentum.db.models import ImprovementRequest, ImprovementRequestStatus

VALID_STATUSES = get_args(ImprovementRequestStatus)

routes = web.RouteTableDef()


def _serialize(request: ImprovementRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "user_id": request.user_id,
        "user_full_name": request.user_full_name,
        "request_text": request.request_text,
        "status": request.status,
        "created_at": request.created_at.isoformat(),
    }


@routes.get("/suggestions")
async def list_suggestions(request: web.Request) -> web.Response:
    """List improvement requests, newest first.

    Query params: ``status`` (optional: new|approved|done|rejected; omitted = every status),
    ``limit`` (1–200, default 50),
    ``offset`` (>= 0, default 0).

    Response JSON::

        {
          "total": int,       # matching rows (ignores limit/offset)
          "limit": int,
          "offset": int,
          "items": [
            {
              "id": int,
              "user_id": int,
              "user_full_name": str,
              "request_text": str,
              "status": "new" | "approved" | "done" | "rejected",
              "created_at": str   # ISO-8601 datetime
            },
            ...
          ]
        }
    """
    status = request.query.get("status")
    if status is not None and status not in VALID_STATUSES:
        raise web.HTTPBadRequest(text=f"status must be one of {', '.join(VALID_STATUSES)}")

    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))
    except ValueError as exc:
        raise web.HTTPBadRequest(text="limit and offset must be integers") from exc
    if not 1 <= limit <= 200:
        raise web.HTTPBadRequest(text="limit must be between 1 and 200")
    if offset < 0:
        raise web.HTTPBadRequest(text="offset must be >= 0")

    items = await db_suggestions.list_improvement_requests(status, limit, offset)
    total = await db_suggestions.count_improvement_requests(status)

    return web.json_response(
        {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [_serialize(item) for item in items],
        }
    )
