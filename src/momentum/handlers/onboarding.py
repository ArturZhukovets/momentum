"""The onboarding FSM, entered once from /start when no profile row exists yet.

`users` is written only by the identity middleware; everything asked here
lands in `user_profiles`, `user_goals` and `body_measurements`. Every
question can be skipped, so all three tables hold nullable answers.

The goal-type/target-weight steps (`Onboarding.goal_type`,
`Onboarding.target_weight`) are also entered from `/goal` (see
`handlers/goal.py`'s `start_goal`, which calls `_ask_goal_type` here with
`step=None`) — they stay in this module because the states themselves are
named `Onboarding.*`.
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from momentum.config import settings
from momentum.db import goals as db_goals
from momentum.db import measurements as db_measurements
from momentum.db import profiles as db_profiles
from momentum.formatters import profile as fmt_profile
from momentum.handlers._profile_common import (
    HEIGHT_CM_RANGE,
    STEP_BIRTH_DATE,
    STEP_GOAL_TYPE,
    STEP_HEIGHT,
    STEP_SEX,
    STEP_TARGET_WEIGHT,
    STEP_WEIGHT,
    WEIGHT_KG_RANGE,
    read_birth_date,
    read_number,
)
from momentum.handlers._prompts import drop_prompt_kb, send_prompt
from momentum.keyboards import common as kb_common
from momentum.keyboards import profile as kb_profile
from momentum.keyboards.callbacks import GoalTypeCB, ProfileCB, SexCB, SkipCB
from momentum.services import periods
from momentum.states import Onboarding
from momentum.texts import common as texts_common
from momentum.texts import profile as texts_profile

router = Router(name="onboarding")


# --------------------------------------------------------------------------
# Onboarding — asked once, from /start, when no profile row exists yet
# --------------------------------------------------------------------------


async def offer_onboarding(message: Message, state: FSMContext) -> None:
    """Entry point called by /start for a user we know nothing about.

    Just shows the offer with a "start" button — the FSM only begins once the
    user taps it, in `confirm_onboarding` below.
    """
    await state.clear()
    await message.answer(
        texts_profile.ONBOARDING_OFFER, reply_markup=kb_profile.start_onboarding_kb()
    )


@router.callback_query(ProfileCB.filter(F.action == "start_onboarding"))
async def confirm_onboarding(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_birth_date(bot, callback.message.chat.id, state)


async def _ask_birth_date(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Onboarding.birth_date)
    await send_prompt(
        bot,
        chat_id,
        state,
        texts_profile.ASK_BIRTH_DATE,
        kb_profile.skip_cancel_kb(STEP_BIRTH_DATE, cancel=False),
    )


@router.message(Onboarding.birth_date, F.text)
async def got_birth_date(message: Message, state: FSMContext, bot: Bot) -> None:
    birth_date = await read_birth_date(message)
    if birth_date is None:
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data(birth_date=birth_date)
    await _ask_sex(bot, message.chat.id, state)


@router.callback_query(Onboarding.birth_date, SkipCB.filter(F.step == STEP_BIRTH_DATE))
async def skip_birth_date(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_sex(bot, callback.message.chat.id, state)


async def _ask_sex(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Onboarding.sex)
    await send_prompt(
        bot, chat_id, state, texts_profile.ASK_SEX, kb_profile.sex_kb(step=STEP_SEX, cancel=False)
    )


@router.callback_query(Onboarding.sex, SexCB.filter())
async def got_sex(
    callback: CallbackQuery, callback_data: SexCB, state: FSMContext, bot: Bot
) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(sex=callback_data.value)
    await _ask_height(bot, callback.message.chat.id, state)


@router.callback_query(Onboarding.sex, SkipCB.filter(F.step == STEP_SEX))
async def skip_sex(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_height(bot, callback.message.chat.id, state)


async def _ask_height(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Onboarding.height)
    await send_prompt(
        bot,
        chat_id,
        state,
        texts_profile.ASK_HEIGHT,
        kb_profile.skip_cancel_kb(STEP_HEIGHT, cancel=False),
    )


@router.message(Onboarding.height, F.text)
async def got_height(message: Message, state: FSMContext, bot: Bot) -> None:
    height = await read_number(
        message, HEIGHT_CM_RANGE, texts_profile.err_height_range(*HEIGHT_CM_RANGE)
    )
    if height is None:
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data(height_cm=height)
    await _after_profile_steps(bot, message.chat.id, message.from_user.id, state)


@router.callback_query(Onboarding.height, SkipCB.filter(F.step == STEP_HEIGHT))
async def skip_height(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _after_profile_steps(bot, callback.message.chat.id, callback.from_user.id, state)


async def _after_profile_steps(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    """Ask about the goal — unless there already is one.

    Reachable: cancelling onboarding leaves no profile row, so /start offers it
    again, and by then the user may have set a goal through /goal. Only one
    active goal per user is allowed, so don't ask for a second.
    """
    if await db_goals.get_active_goal(user_id) is None:
        await _ask_goal_type(bot, chat_id, state, step=STEP_GOAL_TYPE)
    else:
        await _ask_current_weight(bot, chat_id, state)


# --------------------------------------------------------------------------
# Goal steps — shared by onboarding and by /goal for a user without a goal
# --------------------------------------------------------------------------


async def _ask_goal_type(bot: Bot, chat_id: int, state: FSMContext, *, step: str | None) -> None:
    """`step` is None when the goal is the whole point of the flow (/goal)."""
    await state.set_state(Onboarding.goal_type)
    await send_prompt(
        bot,
        chat_id,
        state,
        texts_profile.ASK_GOAL_TYPE,
        kb_profile.goal_type_kb(step=step, cancel=False),
    )


@router.callback_query(Onboarding.goal_type, GoalTypeCB.filter())
async def got_goal_type(
    callback: CallbackQuery, callback_data: GoalTypeCB, state: FSMContext, bot: Bot
) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(goal_type=callback_data.value)
    await _ask_target_weight(bot, callback.message.chat.id, state)


@router.callback_query(Onboarding.goal_type, SkipCB.filter(F.step == STEP_GOAL_TYPE))
async def skip_goal_type(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """No goal type means no goal at all, so the target weight is moot too."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_current_weight(bot, callback.message.chat.id, state)


async def _ask_target_weight(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Onboarding.target_weight)
    await send_prompt(
        bot,
        chat_id,
        state,
        texts_profile.ASK_TARGET_WEIGHT,
        kb_profile.skip_cancel_kb(STEP_TARGET_WEIGHT, cancel=False),
    )


@router.message(Onboarding.target_weight, F.text)
async def got_target_weight(message: Message, state: FSMContext, bot: Bot) -> None:
    weight = await read_number(
        message, WEIGHT_KG_RANGE, texts_profile.err_weight_range(*WEIGHT_KG_RANGE)
    )
    if weight is None:
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data(target_weight_kg=weight)
    await _after_goal_steps(bot, message.chat.id, message.from_user.id, state)


@router.callback_query(Onboarding.target_weight, SkipCB.filter(F.step == STEP_TARGET_WEIGHT))
async def skip_target_weight(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _after_goal_steps(bot, callback.message.chat.id, callback.from_user.id, state)


async def _after_goal_steps(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    if (await state.get_data()).get("goal_only"):
        await _save_goal_only(bot, chat_id, user_id, state)
    else:
        await _ask_current_weight(bot, chat_id, state)


async def _save_goal_only(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    """Finish the /goal flow: the start weight is whatever was last measured."""
    data = await state.get_data()
    await state.clear()

    goal_type = data.get("goal_type")
    if goal_type is None:  # /goal never offers «Пропустить» on the type
        return

    start_weight = await db_measurements.latest_weight(user_id)
    await db_goals.create_goal(
        user_id=user_id,
        goal_type=goal_type,
        start_weight_kg=start_weight,
        target_weight_kg=data.get("target_weight_kg"),
    )

    goal = await db_goals.get_active_goal(user_id)
    card = fmt_profile.goal_card(goal, start_weight)
    await bot.send_message(chat_id, f"{texts_profile.GOAL_SAVED}\n\n{card}")


# --------------------------------------------------------------------------
# Onboarding — first weight, then save everything at once
# --------------------------------------------------------------------------


async def _ask_current_weight(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Onboarding.weight)
    await send_prompt(
        bot,
        chat_id,
        state,
        texts_profile.ASK_CURRENT_WEIGHT,
        kb_profile.skip_cancel_kb(STEP_WEIGHT, cancel=False),
    )


@router.message(Onboarding.weight, F.text)
async def got_current_weight(message: Message, state: FSMContext, bot: Bot) -> None:
    weight = await read_number(
        message, WEIGHT_KG_RANGE, texts_profile.err_weight_range(*WEIGHT_KG_RANGE)
    )
    if weight is None:
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.update_data(weight_kg=weight)
    await _finish_onboarding(bot, message.chat.id, message.from_user.id, state)


@router.callback_query(Onboarding.weight, SkipCB.filter(F.step == STEP_WEIGHT))
async def skip_current_weight(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _finish_onboarding(bot, callback.message.chat.id, callback.from_user.id, state)


async def _finish_onboarding(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    # Written even when every answer was skipped: the row's existence is what
    # tells /start that this user has already been through onboarding.
    await db_profiles.upsert_profile(
        user_id=user_id,
        sex=data.get("sex"),
        birth_date=data.get("birth_date"),
        height_cm=data.get("height_cm"),
    )

    weight = data.get("weight_kg")
    if weight is not None:
        await db_measurements.add_measurement(
            user_id=user_id,
            recorded_on=periods.today_in(settings.tz),
            weight_kg=weight,
        )

    goal_type = data.get("goal_type")
    if goal_type is not None and await db_goals.get_active_goal(user_id) is None:
        await db_goals.create_goal(
            user_id=user_id,
            goal_type=goal_type,
            start_weight_kg=weight,
            target_weight_kg=data.get("target_weight_kg"),
        )

    await bot.send_message(
        chat_id, texts_profile.ONBOARDING_DONE, reply_markup=kb_common.main_menu()
    )


# --------------------------------------------------------------------------
# Fallbacks — registered last, so the specific handlers above always win
# --------------------------------------------------------------------------


@router.message(StateFilter(Onboarding.sex, Onboarding.goal_type))
async def expects_button(message: Message) -> None:
    await message.answer(texts_profile.ERR_USE_BUTTONS)


@router.message(Onboarding.birth_date)
async def expects_date(message: Message) -> None:
    await message.answer(texts_common.ERR_DATE_PARSE)


@router.message(Onboarding.height)
@router.message(Onboarding.target_weight)
@router.message(Onboarding.weight)
async def expects_number(message: Message) -> None:
    await message.answer(texts_profile.ERR_NUMBER)
