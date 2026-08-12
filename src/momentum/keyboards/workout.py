"""The add-workout flow: type, skippable fields, body parts, date."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from momentum.keyboards.callbacks import ActionCB, ChoiceCB, DateCB, PartCB, SkipCB, TypeCB
from momentum.keyboards.common import CANCEL_BUTTON
from momentum.services.workout_types import WORKOUT_TYPES, FieldSpec
from momentum.texts import common as texts_common
from momentum.texts import workout as texts_workout


def type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for workout_type in WORKOUT_TYPES:
        builder.button(
            text=texts_workout.type_label(workout_type),
            callback_data=TypeCB(value=workout_type),
        )
    builder.adjust(2)
    builder.row(CANCEL_BUTTON)
    return builder.as_markup()


def skip_cancel_kb(step: str) -> InlineKeyboardMarkup:
    """Skip guarded by ``SkipCB.step`` so a leftover keyboard can't skip the wrong field."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_common.BTN_SKIP, callback_data=SkipCB(step=step).pack()
                )
            ],
            [CANCEL_BUTTON],
        ]
    )


def choice_kb(field: FieldSpec) -> InlineKeyboardMarkup:
    """Single-choice field (e.g. effort) plus skip/cancel."""
    builder = InlineKeyboardBuilder()
    for value in field.choices:
        builder.button(
            text=texts_workout.choice_label(field.name, value),
            callback_data=ChoiceCB(field=field.name, value=value),
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text=texts_common.BTN_SKIP, callback_data=SkipCB(step=field.name).pack()
        )
    )
    builder.row(CANCEL_BUTTON)
    return builder.as_markup()


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
        InlineKeyboardButton(
            text=texts_common.BTN_SKIP, callback_data=SkipCB(step="body_parts").pack()
        ),
    )
    builder.row(CANCEL_BUTTON)
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
