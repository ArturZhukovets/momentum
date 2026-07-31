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
    STEP_WEIGHT,
    WEIGHT_KG_RANGE,
    read_number,
)
from momentum.handlers._prompts import drop_prompt_kb, send_prompt
from momentum.keyboards import profile as kb_profile
from momentum.keyboards.callbacks import ProfileCB, SkipCB
from momentum.services import periods
from momentum.states import Measure
from momentum.texts import common as texts_common
from momentum.texts import profile as texts_profile

router = Router(name="measure")

# Circumference steps, in the order they are asked:
# state -> FSM data key, skip id, prompt.
_GIRTH_STEPS: tuple[tuple[State, str, str, str], ...] = (
    (Measure.waist, "waist_cm", "waist", texts_profile.ASK_WAIST),
    (Measure.chest, "chest_cm", "chest", texts_profile.ASK_CHEST),
    (Measure.hips, "hips_cm", "hips", texts_profile.ASK_HIPS),
    (Measure.thigh, "thigh_cm", "thigh", texts_profile.ASK_THIGH),
    (Measure.arm, "arm_cm", "arm", texts_profile.ASK_ARM),
)
_GIRTH_STATES = tuple(step[0] for step in _GIRTH_STEPS)


@router.message(Command("measure"))
@router.message(F.text == texts_common.BTN_MEASURE)
async def cmd_measure(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await state.set_state(Measure.weight)
    await send_prompt(
        bot,
        message.chat.id,
        state,
        texts_profile.ASK_MEASURE_WEIGHT,
        kb_profile.skip_cancel_kb(STEP_WEIGHT),
    )


@router.message(Measure.weight, F.text)
async def got_measure_weight(message: Message, state: FSMContext, bot: Bot) -> None:
    weight = await read_number(
        message, WEIGHT_KG_RANGE, texts_profile.err_weight_range(*WEIGHT_KG_RANGE)
    )
    if weight is None:
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data(weight_kg=weight)
    await _offer_body_measure(bot, message.chat.id, state)


@router.callback_query(Measure.weight, SkipCB.filter(F.step == STEP_WEIGHT))
async def skip_measure_weight(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _offer_body_measure(bot, callback.message.chat.id, state)


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
    await _ask_girth(bot, callback.message.chat.id, state, index=0)


@router.callback_query(Measure.offering_body, ProfileCB.filter(F.action == "measure_save"))
async def save_from_offer(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _save_measurement(bot, callback.message.chat.id, callback.from_user.id, state)


async def _ask_girth(bot: Bot, chat_id: int, state: FSMContext, *, index: int) -> None:
    girth_state, _, step, prompt = _GIRTH_STEPS[index]
    await state.set_state(girth_state)
    await send_prompt(bot, chat_id, state, prompt, kb_profile.skip_cancel_kb(step))


async def _next_girth(
    bot: Bot, chat_id: int, user_id: int, state: FSMContext, *, done_index: int
) -> None:
    if done_index + 1 < len(_GIRTH_STEPS):
        await _ask_girth(bot, chat_id, state, index=done_index + 1)
    else:
        await _save_measurement(bot, chat_id, user_id, state)


async def _girth_index(state: FSMContext) -> int:
    current = await state.get_state()
    return next(i for i, step in enumerate(_GIRTH_STEPS) if step[0].state == current)


@router.message(StateFilter(*_GIRTH_STATES), F.text)
async def got_girth(message: Message, state: FSMContext, bot: Bot) -> None:
    index = await _girth_index(state)
    field = _GIRTH_STEPS[index][1]

    value = await read_number(
        message, GIRTH_CM_RANGE, texts_profile.err_measure_range(*GIRTH_CM_RANGE)
    )
    if value is None:
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data(**{field: value})
    await _next_girth(bot, message.chat.id, message.from_user.id, state, done_index=index)


@router.callback_query(StateFilter(*_GIRTH_STATES), SkipCB.filter())
async def skip_girth(
    callback: CallbackQuery, callback_data: SkipCB, state: FSMContext, bot: Bot
) -> None:
    await callback.answer()
    index = await _girth_index(state)
    if callback_data.step != _GIRTH_STEPS[index][2]:  # stale keyboard
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await _next_girth(bot, callback.message.chat.id, callback.from_user.id, state, done_index=index)


async def _save_measurement(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    values = {
        "weight_kg": data.get("weight_kg"),
        **{field: data.get(field) for _, field, _, _ in _GIRTH_STEPS},
    }
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


@router.message(StateFilter(Measure.offering_body))
async def expects_button(message: Message) -> None:
    await message.answer(texts_profile.ERR_USE_BUTTONS)


@router.message(Measure.weight)
@router.message(StateFilter(*_GIRTH_STATES))
async def expects_number(message: Message) -> None:
    await message.answer(texts_profile.ERR_NUMBER)
