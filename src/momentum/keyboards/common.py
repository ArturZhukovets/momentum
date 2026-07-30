"""The persistent main menu, and the cancel button/keyboard every flow reuses."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from momentum.keyboards.callbacks import ActionCB
from momentum.texts import common as texts_common

CANCEL_BUTTON = InlineKeyboardButton(
    text=texts_common.BTN_CANCEL, callback_data=ActionCB(name="cancel").pack()
)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts_common.BTN_ADD)],
            [KeyboardButton(text=texts_common.BTN_HISTORY)],
            [
                KeyboardButton(text=texts_common.BTN_WEEK),
                KeyboardButton(text=texts_common.BTN_MONTH),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[CANCEL_BUTTON]])
