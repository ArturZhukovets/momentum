from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

log = logging.getLogger(__name__)


async def send_prompt(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Send a new prompt message and stash its id in FSM for later keyboard cleanup."""
    sent = await bot.send_message(chat_id, text, reply_markup=markup)
    await state.update_data(prompt_id=sent.message_id)


async def edit_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Replace the callback message with the next prompt; refresh stashed prompt_id."""
    await callback.message.edit_text(text, reply_markup=markup)
    await state.update_data(prompt_id=callback.message.message_id)


async def drop_prompt_kb(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Strip the keyboard from the last prompt after a text reply; clear prompt_id."""
    prompt_id = (await state.get_data()).get("prompt_id")
    if not prompt_id:
        return
    try:
        await bot.edit_message_reply_markup(chat_id, prompt_id, reply_markup=None)
    except Exception:  # message too old, already edited, or deleted — harmless
        log.debug("Could not clear prompt keyboard", exc_info=True)
    await state.update_data(prompt_id=None)
