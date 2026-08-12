"""/history — paginated list, detail card, edit and delete."""

from __future__ import annotations

import logging
from math import ceil

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from momentum.config import settings
from momentum.db import workouts as db_workouts
from momentum.formatters import workout as fmt_workout
from momentum.keyboards import common as kb_common
from momentum.keyboards import history as kb_history
from momentum.keyboards.callbacks import PAGE_SIZE, HistCB, WorkoutCB
from momentum.services import periods
from momentum.states import EditWorkout
from momentum.texts import common as texts_common
from momentum.texts import history as texts_history

log = logging.getLogger(__name__)

router = Router(name="history")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


async def _page_view(user_id: int, page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    total = await db_workouts.count_workouts(user_id)
    if total == 0:
        return texts_history.HISTORY_EMPTY, None

    pages = max(1, ceil(total / PAGE_SIZE))
    page = min(max(page, 1), pages)

    workouts = await db_workouts.list_workouts(user_id, PAGE_SIZE, (page - 1) * PAGE_SIZE)
    return (
        texts_history.history_header(page, pages, total),
        kb_history.history_page_kb(workouts, page, pages),
    )


async def _replace(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    """Show `text` in place of the callback's message.

    A detail card carrying a photo cannot be edited into a plain text message,
    so in that case the message is dropped and a fresh one is sent.
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


async def _show_detail(callback: CallbackQuery, workout_id: int, page: int) -> None:
    workout = await db_workouts.get_workout(callback.from_user.id, workout_id)
    if workout is None:
        await callback.answer(texts_history.WORKOUT_NOT_FOUND, show_alert=True)
        return

    card = fmt_workout.workout_card(workout)
    markup = kb_history.workout_detail_kb(workout.id, page)
    await _replace(callback, card, markup)


async def _send_detail(message: Message, user_id: int, workout_id: int, page: int) -> None:
    """Detail card as a brand-new message (used after an edit)."""
    workout = await db_workouts.get_workout(user_id, workout_id)
    if workout is None:
        await message.answer(texts_history.WORKOUT_NOT_FOUND)
        return

    card = fmt_workout.workout_card(workout)
    markup = kb_history.workout_detail_kb(workout.id, page)
    await message.answer(card, reply_markup=markup)


# --------------------------------------------------------------------------
# List + pagination
# --------------------------------------------------------------------------


@router.message(Command("history"))
@router.message(F.text == texts_common.BTN_HISTORY)
async def cmd_history(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, markup = await _page_view(message.from_user.id, 1)
    await message.answer(text, reply_markup=markup)


@router.callback_query(HistCB.filter(F.action == "page"))
async def show_page(callback: CallbackQuery, callback_data: HistCB) -> None:
    await callback.answer()
    text, markup = await _page_view(callback.from_user.id, callback_data.value)
    await _replace(callback, text, markup)


@router.callback_query(HistCB.filter(F.action == "open"))
async def open_workout(callback: CallbackQuery, callback_data: HistCB, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _show_detail(callback, callback_data.value, page=callback_data.page)


# --------------------------------------------------------------------------
# Edit
# --------------------------------------------------------------------------


@router.callback_query(WorkoutCB.filter(F.action == "desc"))
async def ask_description(
    callback: CallbackQuery, callback_data: WorkoutCB, state: FSMContext
) -> None:
    await callback.answer()
    await state.set_state(EditWorkout.awaiting_description)
    await state.update_data(workout_id=callback_data.workout_id, page=callback_data.page)
    await callback.message.answer(
        texts_history.ASK_NEW_DESCRIPTION, reply_markup=kb_common.cancel_kb()
    )


@router.message(EditWorkout.awaiting_description, F.text)
async def save_description(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    workout_id, page = data["workout_id"], data["page"]
    if not await db_workouts.update_description(
        message.from_user.id, workout_id, message.text.strip()
    ):
        await message.answer(texts_history.WORKOUT_NOT_FOUND)
        return

    await message.answer(texts_history.DESCRIPTION_UPDATED)
    await _send_detail(message, message.from_user.id, workout_id, page)


@router.message(EditWorkout.awaiting_description)
async def description_invalid(message: Message) -> None:
    await message.answer(texts_common.ERR_TEXT_EXPECTED)


@router.callback_query(WorkoutCB.filter(F.action == "date"))
async def ask_date(callback: CallbackQuery, callback_data: WorkoutCB, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(EditWorkout.awaiting_date)
    await state.update_data(workout_id=callback_data.workout_id, page=callback_data.page)
    await callback.message.answer(texts_history.ASK_NEW_DATE, reply_markup=kb_common.cancel_kb())


@router.message(EditWorkout.awaiting_date, F.text)
async def save_date(message: Message, state: FSMContext) -> None:
    today = periods.today_in(settings.tz)
    parsed = periods.parse_user_date(message.text, today)

    if parsed is None:
        await message.answer(texts_common.ERR_DATE_PARSE)
        return
    if parsed > today:
        await message.answer(texts_common.ERR_DATE_FUTURE)
        return

    data = await state.get_data()
    await state.clear()

    workout_id, page = data["workout_id"], data["page"]
    if not await db_workouts.update_performed_on(message.from_user.id, workout_id, parsed):
        await message.answer(texts_history.WORKOUT_NOT_FOUND)
        return

    await message.answer(texts_history.DATE_UPDATED)
    await _send_detail(message, message.from_user.id, workout_id, page)


@router.message(EditWorkout.awaiting_date)
async def date_invalid(message: Message) -> None:
    await message.answer(texts_common.ERR_DATE_PARSE)


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------


@router.callback_query(WorkoutCB.filter(F.action == "del"))
async def ask_delete(callback: CallbackQuery, callback_data: WorkoutCB) -> None:
    await callback.answer(texts_history.ASK_DELETE_CONFIRM, show_alert=False)
    await callback.message.edit_reply_markup(
        reply_markup=kb_history.delete_confirm_kb(callback_data.workout_id, callback_data.page)
    )


@router.callback_query(WorkoutCB.filter(F.action == "del_yes"))
async def confirm_delete(callback: CallbackQuery, callback_data: WorkoutCB) -> None:
    deleted = await db_workouts.delete_workout(callback.from_user.id, callback_data.workout_id)
    await callback.answer(
        texts_history.WORKOUT_DELETED if deleted else texts_history.WORKOUT_NOT_FOUND
    )

    text, markup = await _page_view(callback.from_user.id, callback_data.page)
    await _replace(callback, text, markup)
