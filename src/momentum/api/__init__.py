from __future__ import annotations

from aiohttp import web

from momentum.api import suggestions
from momentum.api.auth import require_api_key


def register(app: web.Application) -> None:
    api_app = web.Application(middlewares=[require_api_key])
    api_app.add_routes(suggestions.routes)
    app.add_subapp("/api", api_app)
