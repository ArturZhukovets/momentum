"""The add-workout FSM: pick a type, walk its catalog fields, then date → save."""

from __future__ import annotations

from datetime import date, timedelta
from typing import cast

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from momentum.config import settings
from momentum.db import workouts as db_workouts
from momentum.db.models import WorkoutType
from momentum.formatters import workout as fmt_workout
from momentum.handlers._prompts import drop_prompt_kb, edit_prompt, send_prompt
from momentum.keyboards import common as kb_common
from momentum.keyboards import workout as kb_workout
from momentum.keyboards.callbacks import ActionCB, ChoiceCB, DateCB, PartCB, SkipCB, TypeCB
from momentum.services import periods
from momentum.services.workout_types import FieldSpec, field_at_index, parse_text
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
    await state.set_state(AddWorkout.choosing_type)
    sent = await message.answer(texts_workout.ASK_TYPE, reply_markup=kb_workout.type_kb())
    await state.update_data(prompt_id=sent.message_id)


@router.callback_query(AddWorkout.choosing_type, TypeCB.filter())
async def choose_type(callback: CallbackQuery, callback_data: TypeCB, state: FSMContext) -> None:
    await callback.answer()
    workout_type = cast(WorkoutType, callback_data.value)
    await state.update_data(
        workout_type=workout_type,
        field_index=0,
        body_parts=[],
        duration_min=None,
        distance_km=None,
        effort=None,
        description="",
    )
    await _ask_current_field(callback.bot, callback.message.chat.id, state, callback=callback)


# --------------------------------------------------------------------------
# Generic field walker
# --------------------------------------------------------------------------


def _field_input_error(field: FieldSpec) -> str:
    if field.input_type == "int":
        return texts_workout.ERR_DURATION
    if field.input_type == "float":
        return texts_workout.ERR_DISTANCE
    return texts_common.ERR_TEXT_EXPECTED


def _markup_for(field: FieldSpec, data: dict) -> InlineKeyboardMarkup:
    if field.input_type == "multi_choice":
        return kb_workout.parts_kb(data.get("body_parts", []))
    if field.input_type == "choice":
        return kb_workout.choice_kb(field)
    return kb_workout.skip_cancel_kb(field.name)


async def _ask_current_field(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    *,
    callback: CallbackQuery | None = None,
) -> None:
    data = await state.get_data()
    field = field_at_index(data["workout_type"], data["field_index"])
    if field is None:
        if callback is not None:
            await callback.message.edit_reply_markup(reply_markup=None)
        await _ask_date(bot, chat_id, state)
        return

    await state.set_state(AddWorkout.field_input)
    prompt = texts_workout.field_prompt(field.name)
    markup = _markup_for(field, data)

    if callback is not None:
        await edit_prompt(callback, state, prompt, markup)
    else:
        await send_prompt(bot, chat_id, state, prompt, markup)


async def _advance(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(field_index=data["field_index"] + 1)
    await _ask_current_field(bot, chat_id, state)


@router.callback_query(AddWorkout.field_input, SkipCB.filter())
async def skip_field(
    callback: CallbackQuery, callback_data: SkipCB, state: FSMContext, bot: Bot
) -> None:
    data = await state.get_data()
    field = field_at_index(data["workout_type"], data["field_index"])
    if field is None or callback_data.step != field.name:
        await callback.answer()
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    if field.name == "body_parts":
        await state.update_data(body_parts=[])
    elif field.name == "description":
        await state.update_data(description="")
    else:
        await state.update_data({field.name: None})

    await _advance(bot, callback.message.chat.id, state)


@router.callback_query(AddWorkout.field_input, ChoiceCB.filter())
async def choose_value(
    callback: CallbackQuery, callback_data: ChoiceCB, state: FSMContext, bot: Bot
) -> None:
    data = await state.get_data()
    field = field_at_index(data["workout_type"], data["field_index"])
    if (
        field is None
        or field.input_type != "choice"
        or callback_data.field != field.name
        or callback_data.value not in field.choices
    ):
        await callback.answer()
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data({field.name: callback_data.value})
    await _advance(bot, callback.message.chat.id, state)


@router.callback_query(AddWorkout.field_input, PartCB.filter())
async def toggle_part(callback: CallbackQuery, callback_data: PartCB, state: FSMContext) -> None:
    data = await state.get_data()
    field = field_at_index(data["workout_type"], data["field_index"])
    if field is None or field.input_type != "multi_choice":
        await callback.answer()
        return

    selected: list[str] = list(data.get("body_parts", []))
    part = callback_data.value

    if part in selected:
        selected.remove(part)
    elif part == texts_workout.FULL_BODY:
        selected = [texts_workout.FULL_BODY]
    else:
        selected = [p for p in selected if p != texts_workout.FULL_BODY]
        selected.append(part)

    await state.update_data(body_parts=selected)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=kb_workout.parts_kb(selected))


@router.callback_query(AddWorkout.field_input, ActionCB.filter(F.name == "parts_done"))
async def parts_done(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    field = field_at_index(data["workout_type"], data["field_index"])
    if field is None or field.input_type != "multi_choice":
        await callback.answer()
        return

    selected = data.get("body_parts", [])
    if not selected:
        await callback.answer(texts_workout.ASK_PARTS_EMPTY, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _advance(bot, callback.message.chat.id, state)


@router.message(AddWorkout.field_input, F.text)
async def field_text(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    field = field_at_index(data["workout_type"], data["field_index"])
    if field is None:
        return

    value = parse_text(field, message.text)
    if value is None:
        await message.answer(_field_input_error(field))
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data({field.name: value})
    await _advance(bot, message.chat.id, state)


@router.message(AddWorkout.field_input)
async def field_invalid(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = field_at_index(data["workout_type"], data["field_index"])
    if field is None:
        return
    await message.answer(_field_input_error(field))


# --------------------------------------------------------------------------
# Date
# --------------------------------------------------------------------------


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

    workout_id = await db_workouts.add_workout(
        user_id=user_id,
        workout_type=data["workout_type"],
        performed_on=performed_on,
        description=data.get("description") or "",
        duration_min=data.get("duration_min"),
        distance_km=data.get("distance_km"),
        effort=data.get("effort"),
        body_parts=list(data.get("body_parts") or []),
    )

    workout = await db_workouts.get_workout(user_id, workout_id)
    week_start, week_end = periods.week_bounds(performed_on)
    done = len(await db_workouts.points_between(user_id, week_start, week_end))

    card = f"{texts_workout.WORKOUT_SAVED}\n\n{fmt_workout.workout_card(workout)}"
    nudge = texts_workout.weekly_nudge(done, settings.WEEKLY_GOAL)

    await bot.send_message(chat_id, f"{card}\n\n{nudge}", reply_markup=kb_common.main_menu())
