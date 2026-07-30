from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import TelegramObject, User

from momentum.config import settings


class IsAdmin(Filter):
    """
    Passes when the update's sender is on the configured allowlist.

    Applied at router level to both `message` and `callback_query`, so every
    single update is re-checked: a previously rendered inline button is never
    treated as proof of access.
    """

    async def __call__(self, event: TelegramObject, event_from_user: User | None = None) -> bool:
        return event_from_user is not None and event_from_user.id in settings.ADMIN_USER_IDS
