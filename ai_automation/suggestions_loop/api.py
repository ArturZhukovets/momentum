"""The remote suggestions endpoint — the loop's only network dependency."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

import aiohttp
from pydantic import BaseModel


class SuggestionItem(BaseModel):
    """One record as the remote API returns it."""

    id: int
    user_id: int
    user_full_name: str
    request_text: str
    status: Literal["new", "done", "rejected"]
    created_at: datetime


class SuggestionsAPI:
    """Paginated read-only client for the remote suggestions endpoint."""

    URL = "https://89-125-51-9.sslip.io/api/suggestions"
    PAGE_SIZE = 200

    def __init__(self, url: str = URL, page_size: int = PAGE_SIZE) -> None:
        self.url = url
        self.page_size = page_size

    def _headers(self) -> dict[str, str]:
        api_key = os.getenv("INTERNAL_API_KEY")
        if not api_key:
            raise SystemExit("INTERNAL_API_KEY is not set")
        return {"X-API-Key": api_key}

    async def fetch_all(self) -> list[SuggestionItem]:
        """Every suggestion, newest first."""
        headers = self._headers()
        suggestions: list[SuggestionItem] = []
        offset = 0

        async with aiohttp.ClientSession() as session:
            while True:
                params = {"limit": self.page_size, "offset": offset}
                async with session.get(self.url, headers=headers, params=params) as response:
                    if response.status >= 400:
                        body = await response.text()
                        raise SystemExit(f"API error {response.status} {response.reason}: {body}")
                    data = await response.json()

                page = [SuggestionItem.model_validate(item) for item in data["items"]]
                suggestions.extend(page)
                offset += len(page)

                if offset >= data["total"] or not page:
                    break

        return sorted(suggestions, key=lambda s: s.created_at, reverse=True)
