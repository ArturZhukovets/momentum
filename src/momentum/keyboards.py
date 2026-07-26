"""All keyboards and callback_data factories."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from momentum import texts
from momentum.db.repo import Workout
from momentum.formatters import history_row_label

PAGE_SIZE = 7


# --------------------------------------------------------------------------
# Callback data factories
# --------------------------------------------------------------------------


class ActionCB(CallbackData, prefix="act"):
    """Generic flow control: cancel, skip, parts_done."""

    name: str


class KindCB(CallbackData, prefix="kind"):
    value: str  # cardio | strength


class PartCB(CallbackData, prefix="part"):
    value: str  # a body part DB value


class DateCB(CallbackData, prefix="date"):
    value: str  # today | yesterday | custom


class HistCB(CallbackData, prefix="hist"):
    action: str  # page | open
    value: int  # page number, or workout id for `open`
    page: int = 1  # page to return to from a detail card


class WorkoutCB(CallbackData, prefix="wk"):
    action: str  # desc | date | del | del_yes | back
    workout_id: int
    page: int


CANCEL_BUTTON = InlineKeyboardButton(
    text=texts.BTN_CANCEL, callback_data=ActionCB(name="cancel").pack()
)


# --------------------------------------------------------------------------
# Menu
# --------------------------------------------------------------------------


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_ADD)],
            [KeyboardButton(text=texts.BTN_HISTORY)],
            [KeyboardButton(text=texts.BTN_WEEK), KeyboardButton(text=texts.BTN_MONTH)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# --------------------------------------------------------------------------
# Add flow
# --------------------------------------------------------------------------


def kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.BTN_CARDIO, callback_data=KindCB(value="cardio").pack()
                ),
                InlineKeyboardButton(
                    text=texts.BTN_STRENGTH, callback_data=KindCB(value="strength").pack()
                ),
            ],
            [CANCEL_BUTTON],
        ]
    )


def skip_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.BTN_SKIP, callback_data=ActionCB(name="skip").pack())],
            [CANCEL_BUTTON],
        ]
    )


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[CANCEL_BUTTON]])


def parts_kb(selected: Sequence[str]) -> InlineKeyboardMarkup:
    """Multi-select grid; selected items get a ✅ prefix."""
    builder = InlineKeyboardBuilder()

    for part in texts.BODY_PARTS:
        if part == texts.FULL_BODY:
            continue
        mark = "✅ " if part in selected else ""
        builder.button(
            text=f"{mark}{texts.body_part_label(part)}", callback_data=PartCB(value=part)
        )
    builder.adjust(2)

    mark = "✅ " if texts.FULL_BODY in selected else ""
    builder.row(
        InlineKeyboardButton(
            text=f"{mark}{texts.body_part_label(texts.FULL_BODY)}",
            callback_data=PartCB(value=texts.FULL_BODY).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(text=texts.BTN_DONE, callback_data=ActionCB(name="parts_done").pack()),
        CANCEL_BUTTON,
    )
    return builder.as_markup()


def date_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.BTN_TODAY, callback_data=DateCB(value="today").pack()
                ),
                InlineKeyboardButton(
                    text=texts.BTN_YESTERDAY, callback_data=DateCB(value="yesterday").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts.BTN_OTHER_DATE, callback_data=DateCB(value="custom").pack()
                )
            ],
            [CANCEL_BUTTON],
        ]
    )


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------


def history_page_kb(workouts: Sequence[Workout], page: int, pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for workout in workouts:
        builder.row(
            InlineKeyboardButton(
                text=history_row_label(workout),
                callback_data=HistCB(action="open", value=workout.id, page=page).pack(),
            )
        )

    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text=texts.BTN_PREV_PAGE, callback_data=HistCB(action="page", value=page - 1).pack()
            )
        )
    if page < pages:
        nav.append(
            InlineKeyboardButton(
                text=texts.BTN_NEXT_PAGE, callback_data=HistCB(action="page", value=page + 1).pack()
            )
        )
    if nav:
        builder.row(*nav)

    return builder.as_markup()


def workout_detail_kb(workout_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.BTN_EDIT_DESCRIPTION,
                    callback_data=WorkoutCB(action="desc", workout_id=workout_id, page=page).pack(),
                ),
                InlineKeyboardButton(
                    text=texts.BTN_EDIT_DATE,
                    callback_data=WorkoutCB(action="date", workout_id=workout_id, page=page).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts.BTN_DELETE,
                    callback_data=WorkoutCB(action="del", workout_id=workout_id, page=page).pack(),
                ),
                InlineKeyboardButton(
                    text=texts.BTN_BACK,
                    callback_data=HistCB(action="page", value=page).pack(),
                ),
            ],
        ]
    )


def delete_confirm_kb(workout_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.BTN_DELETE_YES,
                    callback_data=WorkoutCB(
                        action="del_yes", workout_id=workout_id, page=page
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=texts.BTN_CANCEL,
                    callback_data=HistCB(action="open", value=workout_id, page=page).pack(),
                ),
            ]
        ]
    )
