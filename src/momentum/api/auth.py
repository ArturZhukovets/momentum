"""Shared API-key check for the internal HTTP API."""

from __future__ import annotations

import secrets

from aiohttp import web
from aiohttp.typedefs import Handler

from momentum.config import settings

API_KEY_HEADER = "X-API-Key"


@web.middleware
async def require_api_key(request: web.Request, handler: Handler) -> web.StreamResponse:
    expected = settings.INTERNAL_API_KEY.get_secret_value()
    if not expected:
        raise web.HTTPServiceUnavailable(text="INTERNAL_API_KEY is not configured")

    provided = request.headers.get(API_KEY_HEADER, "")
    if not secrets.compare_digest(provided, expected):
        raise web.HTTPUnauthorized(text="Invalid or missing API key")

    return await handler(request)
