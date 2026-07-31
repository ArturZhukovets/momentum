"""The add-workout flow: kind, skip/cancel, body parts, date."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from momentum.keyboards.callbacks import ActionCB, DateCB, KindCB, PartCB
from momentum.keyboards.common import CANCEL_BUTTON
from momentum.texts import common as texts_common
from momentum.texts import workout as texts_workout


def kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_workout.BTN_CARDIO, callback_data=KindCB(value="cardio").pack()
                ),
                InlineKeyboardButton(
                    text=texts_workout.BTN_STRENGTH, callback_data=KindCB(value="strength").pack()
                ),
            ],
            [CANCEL_BUTTON],
        ]
    )


def skip_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_common.BTN_SKIP, callback_data=ActionCB(name="skip").pack()
                )
            ],
            [CANCEL_BUTTON],
        ]
    )


def parts_kb(selected: Sequence[str]) -> InlineKeyboardMarkup:
    """Multi-select grid; selected items get a ✅ prefix."""
    builder = InlineKeyboardBuilder()

    for part in texts_workout.BODY_PARTS:
        if part == texts_workout.FULL_BODY:
            continue
        mark = "✅ " if part in selected else ""
        builder.button(
            text=f"{mark}{texts_workout.body_part_label(part)}", callback_data=PartCB(value=part)
        )
    builder.adjust(2)

    mark = "✅ " if texts_workout.FULL_BODY in selected else ""
    builder.row(
        InlineKeyboardButton(
            text=f"{mark}{texts_workout.body_part_label(texts_workout.FULL_BODY)}",
            callback_data=PartCB(value=texts_workout.FULL_BODY).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=texts_workout.BTN_DONE, callback_data=ActionCB(name="parts_done").pack()
        ),
        CANCEL_BUTTON,
    )
    return builder.as_markup()


def date_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_workout.BTN_TODAY, callback_data=DateCB(value="today").pack()
                ),
                InlineKeyboardButton(
                    text=texts_workout.BTN_YESTERDAY,
                    callback_data=DateCB(value="yesterday").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts_workout.BTN_OTHER_DATE, callback_data=DateCB(value="custom").pack()
                )
            ],
            [CANCEL_BUTTON],
        ]
    )
