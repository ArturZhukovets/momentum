import asyncio
import os
from datetime import datetime
from typing import Literal

import aiohttp
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

PAGE_SIZE = 200
REMOTE_API_URL = "https://89-125-51-9.sslip.io/api/suggestions"


class SuggestionItem(BaseModel):
    id: int
    user_id: int
    user_full_name: str
    request_text: str
    status: Literal["new", "done", "rejected"]
    created_at: datetime


async def main() -> None:
    api_key = os.getenv("INTERNAL_API_KEY")
    if not api_key:
        raise SystemExit("INTERNAL_API_KEY is not set")

    headers = {"X-API-Key": api_key}
    suggestions: list[SuggestionItem] = []
    offset = 0

    async with aiohttp.ClientSession() as session:
        while True:
            params = {"limit": PAGE_SIZE, "offset": offset}
            async with session.get(REMOTE_API_URL, headers=headers, params=params) as response:
                response.raise_for_status()
                data = await response.json()

            page = [SuggestionItem.model_validate(item) for item in data["items"]]
            suggestions.extend(page)
            offset += len(page)

            if offset >= data["total"] or not page:
                break


if __name__ == "__main__":
    asyncio.run(main())
