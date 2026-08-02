"""/measure — weight first, circumferences on request, one row at the end."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

from momentum.config import settings
from momentum.db import measurements as db_measurements
from momentum.formatters import profile as fmt_profile
from momentum.handlers._profile_common import (
    GIRTH_CM_RANGE,
    WEIGHT_KG_RANGE,
    read_number,
)
from momentum.handlers._prompts import edit_prompt, send_prompt
from momentum.keyboards import profile as kb_profile
from momentum.keyboards.callbacks import MeasureFieldCB, ProfileCB
from momentum.services import periods
from momentum.states import Measure
from momentum.texts import common as texts_common
from momentum.texts import profile as texts_profile

router = Router(name="measure")

# Circumference steps, in the order they are asked: state -> FSM data key, prompt.
_MEASURE_STEPS: tuple[tuple[State, str, str], ...] = (
    (Measure.chest, "chest_cm", texts_profile.ASK_CHEST),
    (Measure.waist, "waist_cm", texts_profile.ASK_WAIST),
    (Measure.hips, "hips_cm", texts_profile.ASK_HIPS),
    (Measure.thigh, "thigh_cm", texts_profile.ASK_THIGH),
    (Measure.arm, "arm_cm", texts_profile.ASK_ARM),
)
_MEASURE_STATES = tuple(step[0] for step in _MEASURE_STEPS)


# Every collectible field, weight included: FSM data key -> (state to re-enter, prompt).
# Used by the review step to re-ask a single field without restarting the whole flow.
_FIELD_STEPS: dict[str, tuple[State, str]] = {
    "weight_kg": (Measure.weight, texts_profile.ASK_MEASURE_WEIGHT),
    **{field: (state, prompt) for state, field, prompt in _MEASURE_STEPS},
}


@router.message(Command("measure"))
@router.message(F.text == texts_common.BTN_MEASURE)
async def cmd_measure(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    today = periods.today_in(settings.tz)
    last_measurement = await db_measurements.latest_measurement(message.from_user.id)
    if last_measurement and last_measurement.recorded_on == today:
        card = fmt_profile.measurement_card(last_measurement)
        await bot.send_message(message.chat.id, f"{texts_profile.MEASURE_ALREADY_TODAY}\n\n{card}")
        return

    await state.set_state(Measure.weight)
    await send_prompt(bot, message.chat.id, state, texts_profile.ASK_MEASURE_WEIGHT)


@router.message(Measure.weight, F.text)
async def got_measure_weight(message: Message, state: FSMContext, bot: Bot) -> None:
    weight = await read_number(
        message, WEIGHT_KG_RANGE, texts_profile.err_weight_range(*WEIGHT_KG_RANGE)
    )
    if weight is None:
        return

    editing = (await state.get_data()).get("editing", False)
    await state.update_data(weight_kg=weight, editing=False)
    if editing:
        await _show_review(bot, message.chat.id, state)
    else:
        await _offer_body_measure(bot, message.chat.id, state)


async def _offer_body_measure(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Measure.offering_body)
    await send_prompt(
        bot,
        chat_id,
        state,
        texts_profile.OFFER_BODY_MEASURE,
        kb_profile.offer_body_measure_kb(),
    )


@router.callback_query(Measure.offering_body, ProfileCB.filter(F.action == "body_measure"))
async def start_body_measure(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await bot.send_message(callback.message.chat.id, texts_profile.MEASURE_GUIDE)
    await _ask_girth(bot, callback.message.chat.id, state, index=0)


@router.callback_query(Measure.offering_body, ProfileCB.filter(F.action == "measure_save"))
async def save_from_offer(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _show_review(bot, callback.message.chat.id, state)


async def _ask_girth(bot: Bot, chat_id: int, state: FSMContext, *, index: int) -> None:
    girth_state, _, prompt = _MEASURE_STEPS[index]
    await state.set_state(girth_state)
    await send_prompt(bot, chat_id, state, prompt)


async def _next_girth(bot: Bot, chat_id: int, state: FSMContext, *, done_index: int) -> None:
    if done_index + 1 < len(_MEASURE_STEPS):
        await _ask_girth(bot, chat_id, state, index=done_index + 1)
    else:
        await _show_review(bot, chat_id, state)


async def _girth_index(state: FSMContext) -> int:
    current = await state.get_state()
    return next(i for i, step in enumerate(_MEASURE_STEPS) if step[0].state == current)


@router.message(StateFilter(*_MEASURE_STATES), F.text)
async def got_girth(message: Message, state: FSMContext, bot: Bot) -> None:
    index = await _girth_index(state)
    field = _MEASURE_STEPS[index][1]

    value = await read_number(
        message, GIRTH_CM_RANGE, texts_profile.err_measure_range(*GIRTH_CM_RANGE)
    )
    if value is None:
        return

    editing = (await state.get_data()).get("editing", False)
    await state.update_data(**{field: value}, editing=False)
    if editing:
        await _show_review(bot, message.chat.id, state)
    else:
        await _next_girth(bot, message.chat.id, state, done_index=index)


def _collect_values(data: dict) -> dict[str, float | None]:
    return {
        "weight_kg": data.get("weight_kg"),
        **{field: data.get(field) for _, field, _ in _MEASURE_STEPS},
    }


async def _show_review(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Measure.review)
    values = _collect_values(await state.get_data())
    card = fmt_profile.measurement_review_card(**values)
    text = f"{texts_profile.MEASURE_REVIEW_HINT}\n\n{card}"
    await send_prompt(bot, chat_id, state, text, kb_profile.measure_review_kb())


@router.callback_query(Measure.review, ProfileCB.filter(F.action == "measure_confirm"))
async def confirm_review(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _save_measurement(bot, callback.message.chat.id, callback.from_user.id, state)


@router.callback_query(Measure.review, ProfileCB.filter(F.action == "measure_edit"))
async def choose_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    values = _collect_values(await state.get_data())
    fields = [field for field in texts_profile.MEASURE_FIELDS if values.get(field) is not None]

    await state.set_state(Measure.choosing_field)
    keyboard = kb_profile.measure_edit_fields_kb(fields)
    await edit_prompt(callback, state, texts_profile.MEASURE_EDIT_PROMPT, keyboard)


@router.callback_query(Measure.choosing_field, MeasureFieldCB.filter())
async def start_edit_field(
    callback: CallbackQuery, callback_data: MeasureFieldCB, state: FSMContext, bot: Bot
) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    target_state, prompt = _FIELD_STEPS[callback_data.field]
    await state.update_data(editing=True)
    await state.set_state(target_state)
    await send_prompt(bot, callback.message.chat.id, state, prompt)


async def _save_measurement(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    values = _collect_values(await state.get_data())
    await state.clear()

    if all(value is None for value in values.values()):
        await bot.send_message(chat_id, texts_profile.MEASURE_EMPTY)
        return

    await db_measurements.add_measurement(
        user_id=user_id, recorded_on=periods.today_in(settings.tz), **values
    )

    measurement = await db_measurements.latest_measurement(user_id)
    card = fmt_profile.measurement_card(measurement)
    await bot.send_message(chat_id, f"{texts_profile.MEASURE_SAVED}\n\n{card}")


# --------------------------------------------------------------------------
# Fallbacks — registered last, so the specific handlers above always win
# --------------------------------------------------------------------------


@router.message(StateFilter(Measure.offering_body, Measure.review, Measure.choosing_field))
async def expects_button(message: Message) -> None:
    await message.answer(texts_profile.ERR_USE_BUTTONS)


@router.message(Measure.weight)
@router.message(StateFilter(*_MEASURE_STATES))
async def expects_number(message: Message) -> None:
    await message.answer(texts_profile.ERR_NUMBER)
