"""/whatsnew and the «Что нового» menu button — read-only release notes.

Touches no FSM state, so it is safe mid-flow: the open question stays where it was.
"""

from __future__ import annotations

from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from momentum.keyboards import whats_new as kb_whats_new
from momentum.keyboards.callbacks import WhatsNewCB
from momentum.services import releases
from momentum.texts import whats_new as texts_whats_new

router = Router(name="whats_new")


def _render(version: str) -> tuple[str, InlineKeyboardMarkup | None]:
    released, body = texts_whats_new.RELEASES[version]
    versions = releases.visible_versions(texts_whats_new.RELEASES, releases.current_version())
    text = f"{texts_whats_new.header(version, released)}\n\n{body}"
    return text, kb_whats_new.versions_kb(versions, shown=version)


@router.message(Command("whatsnew"))
@router.message(F.text == texts_whats_new.BTN_WHATS_NEW)
async def cmd_whats_new(message: Message) -> None:
    version = releases.default_version(texts_whats_new.RELEASES, releases.current_version())
    if version is None:
        await message.answer(texts_whats_new.NO_NOTES)
        return
    text, kb = _render(version)
    await message.answer(text, reply_markup=kb)


@router.callback_query(WhatsNewCB.filter())
async def cb_whats_new(callback: CallbackQuery, callback_data: WhatsNewCB) -> None:
    await callback.answer()
    if callback_data.version not in texts_whats_new.RELEASES:
        return  # notes removed since the keyboard was sent
    text, kb = _render(callback_data.version)
    with suppress(TelegramBadRequest):  # "message is not modified" on a double tap
        await callback.message.edit_text(text, reply_markup=kb)
