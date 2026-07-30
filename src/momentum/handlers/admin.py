"""Private admin panel: suggestion triage plus read-only browsing of users.

Nothing here can modify another user's workouts — the keyboards emit only
navigation callbacks, and every workout lookup stays scoped by owner id.
"""

from __future__ import annotations

import logging
from math import ceil

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from momentum.auth import IsAdmin
from momentum.config import settings
from momentum.db import suggestions as db_suggestions
from momentum.db import users as db_users
from momentum.db import workouts as db_workouts
from momentum.db.models import UserBrief
from momentum.formatters import suggestions as fmt_suggestions
from momentum.formatters import users as fmt_users
from momentum.formatters import workout as fmt_workout
from momentum.keyboards import admin as kb_admin
from momentum.keyboards.callbacks import (
    PAGE_SIZE,
    AdminMenuCB,
    AdminSuggestionCB,
    AdminUserCB,
    AdminWorkoutCB,
)
from momentum.services import periods, reports
from momentum.texts import admin as texts_admin
from momentum.texts import history as texts_history

log = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

# Separate router: the main one is admin-only, so denial must live elsewhere.
denied_router = Router(name="admin_denied")

DEFAULT_SUGGESTION_FILTER = "new"


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _clamp_page(page: int, total: int) -> tuple[int, int]:
    pages = max(1, ceil(total / PAGE_SIZE))
    return min(max(page, 1), pages), pages


async def _replace(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    """Show `text` in place of the callback's message.

    A card carrying a photo cannot be edited into a plain text message, so in
    that case the message is dropped and a fresh one is sent.
    """
    message = callback.message
    if message.photo:
        try:
            await message.delete()
        except Exception:
            log.debug("Could not delete photo message", exc_info=True)
        await message.answer(text, reply_markup=markup)
        return

    await message.edit_text(text, reply_markup=markup)


async def _answer(callback: CallbackQuery, alert: str | None = None) -> None:
    """The single `callback.answer()` every handler owes Telegram."""
    await callback.answer(alert, show_alert=alert is not None)


# --------------------------------------------------------------------------
# Menu
# --------------------------------------------------------------------------


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts_admin.ADMIN_MENU_TITLE, reply_markup=kb_admin.admin_menu_kb())


@denied_router.message(Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    await message.answer(texts_admin.ADMIN_DENIED)


@router.callback_query(AdminMenuCB.filter(F.section == "menu"))
async def show_menu(callback: CallbackQuery) -> None:
    await _replace(callback, texts_admin.ADMIN_MENU_TITLE, kb_admin.admin_menu_kb())
    await _answer(callback)


@router.callback_query(AdminMenuCB.filter(F.section == "close"))
async def close_menu(callback: CallbackQuery) -> None:
    await _replace(callback, texts_admin.ADMIN_CLOSED, None)
    await _answer(callback)


@router.callback_query(AdminMenuCB.filter(F.section == "sug"))
async def open_suggestions(callback: CallbackQuery) -> None:
    text, markup = await _suggestion_page(DEFAULT_SUGGESTION_FILTER, 1)
    await _replace(callback, text, markup)
    await _answer(callback)


@router.callback_query(AdminMenuCB.filter(F.section == "usr"))
async def open_users(callback: CallbackQuery) -> None:
    text, markup = await _user_page(1)
    await _replace(callback, text, markup)
    await _answer(callback)


# --------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------


def _normalize_filter(value: str) -> str:
    return value if value in kb_admin.SUGGESTION_FILTERS else DEFAULT_SUGGESTION_FILTER


async def _suggestion_page(status: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    status_filter = None if status == texts_admin.SUGGESTION_FILTER_ALL else status
    total = await db_suggestions.count_improvement_requests(status_filter)
    page, pages = _clamp_page(page, total)

    requests = await db_suggestions.list_improvement_requests(
        status_filter, PAGE_SIZE, (page - 1) * PAGE_SIZE
    )
    text = (
        texts_admin.admin_suggestions_empty(status)
        if total == 0
        else texts_admin.admin_suggestions_header(status, page, pages, total)
    )
    return text, kb_admin.admin_suggestions_kb(requests, status, page, pages)


async def _show_suggestion(
    callback: CallbackQuery, request_id: int, status: str, page: int
) -> str | None:
    """Redraw the detail view; falls back to the list if the request is gone."""
    request = await db_suggestions.get_improvement_request(request_id)
    if request is None:
        text, markup = await _suggestion_page(status, page)
        await _replace(callback, text, markup)
        return texts_admin.ADMIN_SUGGESTION_NOT_FOUND

    await _replace(
        callback,
        fmt_suggestions.suggestion_card(request),
        kb_admin.admin_suggestion_detail_kb(request, status, page),
    )
    return None


@router.callback_query(AdminSuggestionCB.filter(F.action == "list"))
async def show_suggestion_list(callback: CallbackQuery, callback_data: AdminSuggestionCB) -> None:
    text, markup = await _suggestion_page(
        _normalize_filter(callback_data.status), callback_data.page
    )
    await _replace(callback, text, markup)
    await _answer(callback)


@router.callback_query(AdminSuggestionCB.filter(F.action == "open"))
async def show_suggestion(callback: CallbackQuery, callback_data: AdminSuggestionCB) -> None:
    alert = await _show_suggestion(
        callback,
        callback_data.request_id,
        _normalize_filter(callback_data.status),
        callback_data.page,
    )
    await _answer(callback, alert)


@router.callback_query(AdminSuggestionCB.filter(F.action == "set"))
async def set_suggestion_status(callback: CallbackQuery, callback_data: AdminSuggestionCB) -> None:
    """Idempotent write, then a redraw from the value the database now holds."""
    status = _normalize_filter(callback_data.status)
    if callback_data.target not in texts_admin.SUGGESTION_STATUS_LABELS:
        await _answer(callback, texts_admin.ADMIN_UNKNOWN_ACTION)
        return

    updated = await db_suggestions.set_improvement_request_status(
        callback_data.request_id, callback_data.target
    )
    if not updated:
        text, markup = await _suggestion_page(status, callback_data.page)
        await _replace(callback, text, markup)
        await _answer(callback, texts_admin.ADMIN_SUGGESTION_NOT_FOUND)
        return

    alert = await _show_suggestion(callback, callback_data.request_id, status, callback_data.page)
    await _answer(callback, alert or texts_admin.ADMIN_STATUS_UPDATED)


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------


async def _user_page(page: int) -> tuple[str, InlineKeyboardMarkup]:
    total = await db_users.count_users()
    page, pages = _clamp_page(page, total)

    users = await db_users.list_users(PAGE_SIZE, (page - 1) * PAGE_SIZE)
    text = (
        texts_admin.ADMIN_USERS_EMPTY
        if total == 0
        else texts_admin.admin_users_header(page, pages, total)
    )
    return text, kb_admin.admin_users_kb(users, page, pages)


async def _resolve_user(callback: CallbackQuery, user_id: int, users_page: int) -> UserBrief | None:
    """The selected user, or `None` after redrawing the list for a stale id."""
    user = await db_users.get_user(user_id)
    if user is None:
        text, markup = await _user_page(users_page)
        await _replace(callback, text, markup)
    return user


@router.callback_query(AdminUserCB.filter(F.action == "list"))
async def show_user_list(callback: CallbackQuery, callback_data: AdminUserCB) -> None:
    text, markup = await _user_page(callback_data.page)
    await _replace(callback, text, markup)
    await _answer(callback)


@router.callback_query(AdminUserCB.filter(F.action == "open"))
async def show_user(callback: CallbackQuery, callback_data: AdminUserCB) -> None:
    user = await _resolve_user(callback, callback_data.user_id, callback_data.page)
    if user is None:
        await _answer(callback, texts_admin.ADMIN_USER_NOT_FOUND)
        return

    await _replace(
        callback,
        fmt_users.user_card(user),
        kb_admin.admin_user_kb(user.user_id, callback_data.page),
    )
    await _answer(callback)


@router.callback_query(AdminUserCB.filter(F.action.in_({"week", "month"})))
async def show_user_report(callback: CallbackQuery, callback_data: AdminUserCB) -> None:
    """Exactly the text the selected user would get from /week or /month."""
    user = await _resolve_user(callback, callback_data.user_id, callback_data.page)
    if user is None:
        await _answer(callback, texts_admin.ADMIN_USER_NOT_FOUND)
        return

    build = (
        reports.build_weekly_text if callback_data.action == "week" else reports.build_monthly_text
    )
    body = await build(user.user_id, periods.today_in(settings.tz))

    await _replace(
        callback,
        f"{fmt_users.user_title(user)}\n\n{body}",
        kb_admin.admin_back_to_user_kb(user.user_id, callback_data.page),
    )
    await _answer(callback)


# --------------------------------------------------------------------------
# Another user's workouts — read only
# --------------------------------------------------------------------------


async def _workout_page(
    user: UserBrief, page: int, users_page: int
) -> tuple[str, InlineKeyboardMarkup]:
    total = await db_workouts.count_workouts(user.user_id)
    page, pages = _clamp_page(page, total)

    workouts = await db_workouts.list_workouts(user.user_id, PAGE_SIZE, (page - 1) * PAGE_SIZE)
    body = (
        texts_admin.ADMIN_HISTORY_EMPTY
        if total == 0
        else texts_history.history_header(page, pages, total)
    )
    return (
        f"{fmt_users.user_title(user)}\n\n{body}",
        kb_admin.admin_workouts_kb(workouts, user.user_id, page, pages, users_page),
    )


@router.callback_query(AdminWorkoutCB.filter(F.action == "list"))
async def show_workout_list(callback: CallbackQuery, callback_data: AdminWorkoutCB) -> None:
    user = await _resolve_user(callback, callback_data.user_id, callback_data.users_page)
    if user is None:
        await _answer(callback, texts_admin.ADMIN_USER_NOT_FOUND)
        return

    text, markup = await _workout_page(user, callback_data.page, callback_data.users_page)
    await _replace(callback, text, markup)
    await _answer(callback)


@router.callback_query(AdminWorkoutCB.filter(F.action == "open"))
async def show_workout(callback: CallbackQuery, callback_data: AdminWorkoutCB) -> None:
    user = await _resolve_user(callback, callback_data.user_id, callback_data.users_page)
    if user is None:
        await _answer(callback, texts_admin.ADMIN_USER_NOT_FOUND)
        return

    # Scoped by owner as well as id, so a mismatched pair resolves to nothing.
    workout = await db_workouts.get_workout(user.user_id, callback_data.workout_id)
    if workout is None:
        text, markup = await _workout_page(user, callback_data.page, callback_data.users_page)
        await _replace(callback, text, markup)
        await _answer(callback, texts_history.WORKOUT_NOT_FOUND)
        return

    card = f"{fmt_users.user_title(user)}\n\n{fmt_workout.workout_card(workout)}"
    markup = kb_admin.admin_workout_detail_kb(
        user.user_id, callback_data.page, callback_data.users_page
    )

    if workout.photo_file_id:
        try:
            await callback.message.delete()
        except Exception:
            log.debug("Could not delete list message", exc_info=True)
        await callback.message.answer_photo(
            workout.photo_file_id, caption=card, reply_markup=markup
        )
    else:
        await _replace(callback, card, markup)

    await _answer(callback)
