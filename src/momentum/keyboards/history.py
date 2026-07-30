"""/history — paginated list, detail card, delete confirm."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from momentum.db.models import Workout
from momentum.formatters import workout as fmt_workout
from momentum.keyboards.callbacks import HistCB, WorkoutCB
from momentum.texts import common as texts_common
from momentum.texts import history as texts_history


def history_page_kb(workouts: Sequence[Workout], page: int, pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for workout in workouts:
        builder.row(
            InlineKeyboardButton(
                text=fmt_workout.history_row_label(workout),
                callback_data=HistCB(action="open", value=workout.id, page=page).pack(),
            )
        )

    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text=texts_history.BTN_PREV_PAGE,
                callback_data=HistCB(action="page", value=page - 1).pack(),
            )
        )
    if page < pages:
        nav.append(
            InlineKeyboardButton(
                text=texts_history.BTN_NEXT_PAGE,
                callback_data=HistCB(action="page", value=page + 1).pack(),
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
                    text=texts_history.BTN_EDIT_DESCRIPTION,
                    callback_data=WorkoutCB(action="desc", workout_id=workout_id, page=page).pack(),
                ),
                InlineKeyboardButton(
                    text=texts_history.BTN_EDIT_DATE,
                    callback_data=WorkoutCB(action="date", workout_id=workout_id, page=page).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts_history.BTN_DELETE,
                    callback_data=WorkoutCB(action="del", workout_id=workout_id, page=page).pack(),
                ),
                InlineKeyboardButton(
                    text=texts_history.BTN_BACK,
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
                    text=texts_history.BTN_DELETE_YES,
                    callback_data=WorkoutCB(
                        action="del_yes", workout_id=workout_id, page=page
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=texts_common.BTN_CANCEL,
                    callback_data=HistCB(action="open", value=workout_id, page=page).pack(),
                ),
            ]
        ]
    )
