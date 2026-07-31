"""The add-workout FSM: cardio (photo) and strength (body parts) flows."""

from __future__ import annotations

from datetime import date, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from momentum.config import settings
from momentum.db import workouts as db_workouts
from momentum.formatters import workout as fmt_workout
from momentum.handlers._prompts import drop_prompt_kb, edit_prompt, send_prompt
from momentum.keyboards import common as kb_common
from momentum.keyboards import workout as kb_workout
from momentum.keyboards.callbacks import ActionCB, DateCB, KindCB, PartCB
from momentum.services import periods
from momentum.states import AddWorkout
from momentum.texts import common as texts_common
from momentum.texts import workout as texts_workout

router = Router(name="add_workout")


# --------------------------------------------------------------------------
# Entry
# --------------------------------------------------------------------------


@router.message(Command("add"))
@router.message(F.text == texts_common.BTN_ADD)
async def start_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddWorkout.choosing_kind)
    sent = await message.answer(texts_workout.ASK_KIND, reply_markup=kb_workout.kind_kb())
    await state.update_data(prompt_id=sent.message_id)


@router.callback_query(AddWorkout.choosing_kind, KindCB.filter())
async def choose_kind(callback: CallbackQuery, callback_data: KindCB, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(kind=callback_data.value)

    if callback_data.value == "cardio":
        await state.set_state(AddWorkout.cardio_photo)
        await edit_prompt(
            callback, state, texts_workout.ASK_CARDIO_PHOTO, kb_workout.skip_cancel_kb()
        )
    else:
        await state.update_data(parts=[])
        await state.set_state(AddWorkout.strength_parts)
        await edit_prompt(callback, state, texts_workout.ASK_PARTS, kb_workout.parts_kb([]))


# --------------------------------------------------------------------------
# Cardio: photo
# --------------------------------------------------------------------------


@router.message(AddWorkout.cardio_photo, F.photo)
async def cardio_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await _ask_description(bot, message.chat.id, state)


@router.message(AddWorkout.cardio_photo)
async def cardio_photo_invalid(message: Message) -> None:
    await message.answer(texts_workout.ASK_PHOTO_AGAIN)


@router.callback_query(AddWorkout.cardio_photo, ActionCB.filter(F.name == "skip"))
async def cardio_photo_skip(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_description(bot, callback.message.chat.id, state)


async def _ask_description(bot: Bot, chat_id: int, state: FSMContext) -> None:
    kind = (await state.get_data())["kind"]
    next_state = (
        AddWorkout.cardio_description if kind == "cardio" else AddWorkout.strength_description
    )
    await state.set_state(next_state)
    await send_prompt(
        bot, chat_id, state, texts_workout.ASK_DESCRIPTION, kb_workout.skip_cancel_kb()
    )


# --------------------------------------------------------------------------
# Strength: body parts
# --------------------------------------------------------------------------


@router.callback_query(AddWorkout.strength_parts, PartCB.filter())
async def toggle_part(callback: CallbackQuery, callback_data: PartCB, state: FSMContext) -> None:
    selected: list[str] = list((await state.get_data()).get("parts", []))
    part = callback_data.value

    if part in selected:
        selected.remove(part)
    elif part == texts_workout.FULL_BODY:
        selected = [texts_workout.FULL_BODY]  # "full body" is exclusive
    else:
        selected = [p for p in selected if p != texts_workout.FULL_BODY]
        selected.append(part)

    await state.update_data(parts=selected)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=kb_workout.parts_kb(selected))


@router.callback_query(AddWorkout.strength_parts, ActionCB.filter(F.name == "parts_done"))
async def parts_done(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    selected = (await state.get_data()).get("parts", [])
    if not selected:
        await callback.answer(texts_workout.ASK_PARTS_EMPTY, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_description(bot, callback.message.chat.id, state)


# --------------------------------------------------------------------------
# Description -> date
# --------------------------------------------------------------------------


@router.message(StateFilter(AddWorkout.cardio_description, AddWorkout.strength_description), F.text)
async def got_description(message: Message, state: FSMContext, bot: Bot) -> None:
    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data(description=message.text.strip())
    await _ask_date(bot, message.chat.id, state)


@router.message(StateFilter(AddWorkout.cardio_description, AddWorkout.strength_description))
async def description_invalid(message: Message) -> None:
    await message.answer(texts_common.ERR_TEXT_EXPECTED)


@router.callback_query(
    StateFilter(AddWorkout.cardio_description, AddWorkout.strength_description),
    ActionCB.filter(F.name == "skip"),
)
async def skip_description(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(description="")
    await _ask_date(bot, callback.message.chat.id, state)


async def _ask_date(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(AddWorkout.choosing_date)
    await send_prompt(bot, chat_id, state, texts_workout.ASK_DATE, kb_workout.date_kb())


@router.callback_query(AddWorkout.choosing_date, DateCB.filter())
async def choose_date(
    callback: CallbackQuery, callback_data: DateCB, state: FSMContext, bot: Bot
) -> None:
    await callback.answer()
    today = periods.today_in(settings.tz)

    if callback_data.value == "custom":
        await state.set_state(AddWorkout.custom_date)
        await edit_prompt(callback, state, texts_workout.ASK_CUSTOM_DATE, kb_common.cancel_kb())
        return

    performed_on = today if callback_data.value == "today" else today - timedelta(days=1)
    await callback.message.edit_reply_markup(reply_markup=None)
    await _finish(bot, callback.message.chat.id, callback.from_user.id, performed_on, state)


@router.message(AddWorkout.custom_date, F.text)
async def custom_date(message: Message, state: FSMContext, bot: Bot) -> None:
    today = periods.today_in(settings.tz)
    parsed = periods.parse_user_date(message.text, today)

    if parsed is None:
        await message.answer(texts_common.ERR_DATE_PARSE)
        return
    if parsed > today:
        await message.answer(texts_common.ERR_DATE_FUTURE)
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await _finish(bot, message.chat.id, message.from_user.id, parsed, state)


@router.message(AddWorkout.custom_date)
async def custom_date_invalid(message: Message) -> None:
    await message.answer(texts_common.ERR_DATE_PARSE)


# --------------------------------------------------------------------------
# Save
# --------------------------------------------------------------------------


async def _finish(
    bot: Bot, chat_id: int, user_id: int, performed_on: date, state: FSMContext
) -> None:
    data = await state.get_data()
    await state.clear()

    kind = data["kind"]
    body_parts = list(data.get("parts", [])) if kind == "strength" else []

    workout_id = await db_workouts.add_workout(
        user_id=user_id,
        kind=kind,
        performed_on=performed_on,
        description=data.get("description", ""),
        photo_file_id=data.get("photo_file_id") if kind == "cardio" else None,
        body_parts=body_parts,
    )

    workout = await db_workouts.get_workout(user_id, workout_id)
    week_start, week_end = periods.week_bounds(performed_on)
    done = len(await db_workouts.points_between(user_id, week_start, week_end))

    card = f"{texts_workout.WORKOUT_SAVED}\n\n{fmt_workout.workout_card(workout)}"
    nudge = texts_workout.weekly_nudge(done, settings.WEEKLY_GOAL)

    await bot.send_message(chat_id, f"{card}\n\n{nudge}", reply_markup=kb_common.main_menu())
