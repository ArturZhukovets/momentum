"""/start, /help, /cancel, report toggles, and the user-upsert middleware."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from momentum import keyboards, texts
from momentum.db import repo
from momentum.keyboards import ActionCB

log = logging.getLogger(__name__)

router = Router(name="common")


class UserMiddleware(BaseMiddleware):
    """Keeps the users row in sync with whoever is talking to the bot.

    The last-seen identity is cached in-process so a chatty session doesn't
    issue an UPDATE on every single update.
    """

    def __init__(self) -> None:
        self._seen: dict[int, tuple[str | None, str | None]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is not None and not user.is_bot:
            identity = (user.username, user.first_name)
            if self._seen.get(user.id) != identity:
                await repo.upsert_user(user.id, user.username, user.first_name)
                self._seen[user.id] = identity
        return await handler(event, data)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = message.from_user.first_name if message.from_user else None
    await message.answer(texts.start_greeting(name), reply_markup=keyboards.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP, reply_markup=keyboards.main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL, reply_markup=keyboards.main_menu())
        return
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=keyboards.main_menu())


@router.callback_query(ActionCB.filter(F.name == "cancel"))
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Every ✖️ Отмена button, from any step of any flow."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.CANCELLED, reply_markup=None)


@router.message(Command("reports_on"))
async def cmd_reports_on(message: Message) -> None:
    await repo.set_reports_on(message.from_user.id, True)
    await message.answer(texts.REPORTS_ENABLED)


@router.message(Command("reports_off"))
async def cmd_reports_off(message: Message) -> None:
    await repo.set_reports_on(message.from_user.id, False)
    await message.answer(texts.REPORTS_DISABLED)
