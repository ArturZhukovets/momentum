"""/start, /help, /cancel, report toggles, and the user-upsert middleware."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, TelegramObject, User

from momentum.db import profiles as db_profiles
from momentum.db import users as db_users
from momentum.handlers import onboarding as onboarding_handlers
from momentum.handlers._typing import typing_delay
from momentum.keyboards import common as kb_common
from momentum.keyboards.callbacks import ActionCB
from momentum.texts import common as texts_common
from momentum.texts import reports as texts_reports

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
                await db_users.upsert_user(user.id, user.username, user.first_name)
                self._seen[user.id] = identity
        return await handler(event, data)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    """Greet, and walk a brand-new user through onboarding.

    A `user_profiles` row — even one holding nothing but nulls — means the
    questionnaire has already been offered, so /start stays a plain greeting
    from then on.
    """
    await state.clear()
    name = message.from_user.first_name if message.from_user else None
    profile = await db_profiles.get_profile(message.from_user.id)
    if profile:
        await message.answer(texts_common.start_greeting(name), reply_markup=kb_common.main_menu())
    else:
        await message.answer(texts_common.start_greeting(name), reply_markup=ReplyKeyboardRemove())
        await typing_delay(bot, message.chat.id)
        await onboarding_handlers.offer_onboarding(message, state)
   


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts_common.HELP, reply_markup=kb_common.main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts_common.NOTHING_TO_CANCEL, reply_markup=kb_common.main_menu())
        return
    await state.clear()
    await message.answer(texts_common.CANCELLED, reply_markup=kb_common.main_menu())


@router.callback_query(ActionCB.filter(F.name == "cancel"))
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Every ✖️ Отмена button, from any step of any flow."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(texts_common.CANCELLED, reply_markup=kb_common.main_menu())


@router.message(Command("reports_on"))
async def cmd_reports_on(message: Message) -> None:
    await db_users.set_reports_on(message.from_user.id, True)
    await message.answer(texts_reports.REPORTS_ENABLED)


@router.message(Command("reports_off"))
async def cmd_reports_off(message: Message) -> None:
    await db_users.set_reports_on(message.from_user.id, False)
    await message.answer(texts_reports.REPORTS_DISABLED)
