"""Admin panel: menu, suggestion triage, and read-only user browsing."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from momentum.db.models import ImprovementRequest, UserBrief, Workout
from momentum.formatters import suggestions as fmt_suggestions
from momentum.formatters import users as fmt_users
from momentum.formatters import workout as fmt_workout
from momentum.keyboards.callbacks import (
    AdminMenuCB,
    AdminSuggestionCB,
    AdminUserCB,
    AdminWorkoutCB,
)
from momentum.texts import admin as texts_admin
from momentum.texts import common as texts_common
from momentum.texts import history as texts_history

SUGGESTION_FILTERS: tuple[str, ...] = ("new", "done", "rejected", texts_admin.SUGGESTION_FILTER_ALL)


def _add_pager(
    builder: InlineKeyboardBuilder,
    page: int,
    pages: int,
    to_page: Callable[[int], CallbackData],
) -> None:
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text=texts_history.BTN_PREV_PAGE, callback_data=to_page(page - 1).pack()
            )
        )
    if page < pages:
        nav.append(
            InlineKeyboardButton(
                text=texts_history.BTN_NEXT_PAGE, callback_data=to_page(page + 1).pack()
            )
        )
    if nav:
        builder.row(*nav)


def _to_admin_menu_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=texts_admin.BTN_ADMIN_TO_MENU, callback_data=AdminMenuCB(section="menu").pack()
    )


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_admin.BTN_ADMIN_SUGGESTIONS,
                    callback_data=AdminMenuCB(section="sug").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_admin.BTN_ADMIN_USERS,
                    callback_data=AdminMenuCB(section="usr").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_admin.BTN_ADMIN_CLOSE,
                    callback_data=AdminMenuCB(section="close").pack(),
                )
            ],
        ]
    )


def admin_suggestions_kb(
    requests: Sequence[ImprovementRequest], status: str, page: int, pages: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for request in requests:
        builder.row(
            InlineKeyboardButton(
                text=fmt_suggestions.suggestion_row_label(request),
                callback_data=AdminSuggestionCB(
                    action="open", status=status, request_id=request.id, page=page
                ).pack(),
            )
        )

    _add_pager(
        builder,
        page,
        pages,
        lambda target: AdminSuggestionCB(action="list", status=status, page=target),
    )

    filters = [
        InlineKeyboardButton(
            text=("• " if value == status else "") + texts_admin.suggestion_filter_label(value),
            callback_data=AdminSuggestionCB(action="list", status=value, page=1).pack(),
        )
        for value in SUGGESTION_FILTERS
    ]
    builder.row(*filters[:2])
    builder.row(*filters[2:])
    builder.row(_to_admin_menu_button())
    return builder.as_markup()


def admin_suggestion_detail_kb(
    request: ImprovementRequest, status: str, page: int
) -> InlineKeyboardMarkup:
    """Status buttons for every status the request is not already in."""
    builder = InlineKeyboardBuilder()

    builder.row(
        *[
            InlineKeyboardButton(
                text=texts_admin.suggestion_action_label(target),
                callback_data=AdminSuggestionCB(
                    action="set",
                    status=status,
                    target=target,
                    request_id=request.id,
                    page=page,
                ).pack(),
            )
            for target in texts_admin.SUGGESTION_STATUS_LABELS
            if target != request.status
        ]
    )
    builder.row(
        InlineKeyboardButton(
            text=texts_admin.BTN_ADMIN_TO_LIST,
            callback_data=AdminSuggestionCB(action="list", status=status, page=page).pack(),
        )
    )
    return builder.as_markup()


def admin_users_kb(users: Sequence[UserBrief], page: int, pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for user in users:
        builder.row(
            InlineKeyboardButton(
                text=fmt_users.user_row_label(user),
                callback_data=AdminUserCB(action="open", user_id=user.user_id, page=page).pack(),
            )
        )

    _add_pager(builder, page, pages, lambda target: AdminUserCB(action="list", page=target))
    builder.row(_to_admin_menu_button())
    return builder.as_markup()


def admin_user_kb(user_id: int, users_page: int) -> InlineKeyboardMarkup:
    """Read-only menu for one user — no edit or delete entry points."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_common.BTN_HISTORY,
                    callback_data=AdminWorkoutCB(
                        action="list", user_id=user_id, page=1, users_page=users_page
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_common.BTN_WEEK,
                    callback_data=AdminUserCB(
                        action="week", user_id=user_id, page=users_page
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=texts_common.BTN_MONTH,
                    callback_data=AdminUserCB(
                        action="month", user_id=user_id, page=users_page
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts_admin.BTN_ADMIN_TO_USERS,
                    callback_data=AdminUserCB(action="list", page=users_page).pack(),
                )
            ],
        ]
    )


def admin_back_to_user_kb(user_id: int, users_page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_admin.BTN_ADMIN_TO_USER,
                    callback_data=AdminUserCB(
                        action="open", user_id=user_id, page=users_page
                    ).pack(),
                )
            ]
        ]
    )


def admin_workouts_kb(
    workouts: Sequence[Workout], user_id: int, page: int, pages: int, users_page: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for workout in workouts:
        builder.row(
            InlineKeyboardButton(
                text=fmt_workout.history_row_label(workout),
                callback_data=AdminWorkoutCB(
                    action="open",
                    user_id=user_id,
                    workout_id=workout.id,
                    page=page,
                    users_page=users_page,
                ).pack(),
            )
        )

    _add_pager(
        builder,
        page,
        pages,
        lambda target: AdminWorkoutCB(
            action="list", user_id=user_id, page=target, users_page=users_page
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=texts_admin.BTN_ADMIN_TO_USER,
            callback_data=AdminUserCB(action="open", user_id=user_id, page=users_page).pack(),
        )
    )
    return builder.as_markup()


def admin_workout_detail_kb(user_id: int, page: int, users_page: int) -> InlineKeyboardMarkup:
    """Navigation only — an admin can never edit or delete someone's workout."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_admin.BTN_ADMIN_TO_LIST,
                    callback_data=AdminWorkoutCB(
                        action="list", user_id=user_id, page=page, users_page=users_page
                    ).pack(),
                )
            ]
        ]
    )
