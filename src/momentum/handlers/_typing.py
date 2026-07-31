"""Shared "bot is typing…" delay, reusable wherever a handler sends a
follow-up message and wants Telegram's typing indicator to bridge the pause.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.enums import ChatAction


async def typing_delay(bot: Bot, chat_id: int, seconds: float = 2.0) -> None:
    """Show the "typing…" indicator, then wait `seconds` before the caller sends.

    Telegram auto-expires a chat action after ~5s, so keep `seconds` under
    that for a single call — a longer pause would need to re-trigger it.
    """
    await bot.send_chat_action(chat_id, ChatAction.TYPING)
    await asyncio.sleep(seconds)
