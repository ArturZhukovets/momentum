"""Collect free-text improvement requests from users."""

from __future__ import annotations

from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from momentum import keyboards, texts
from momentum.db import repo
from momentum.states import Suggestion

router = Router(name="suggestions")


@router.message(Command("suggest"))
async def start_suggestion(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Suggestion.awaiting_text)
    prompt = await message.answer(texts.ASK_SUGGESTION, reply_markup=keyboards.cancel_kb())
    await state.update_data(prompt_id=prompt.message_id)


@router.message(Suggestion.awaiting_text, F.text)
async def save_suggestion(message: Message, state: FSMContext, bot: Bot) -> None:
    request_text = message.text.strip()
    if not request_text:
        await message.answer(texts.ERR_SUGGESTION_EMPTY)
        return

    await repo.add_improvement_request(
        user_id=message.from_user.id,
        user_full_name=message.from_user.full_name,
        request_text=request_text,
    )

    data = await state.get_data()
    await state.clear()
    prompt_id = data.get("prompt_id")
    if prompt_id is not None:
        with suppress(TelegramAPIError):
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=prompt_id,
                reply_markup=None,
            )
    await message.answer(texts.SUGGESTION_SAVED, reply_markup=keyboards.main_menu())


@router.message(Suggestion.awaiting_text)
async def suggestion_invalid(message: Message) -> None:
    await message.answer(texts.ERR_TEXT_EXPECTED)
