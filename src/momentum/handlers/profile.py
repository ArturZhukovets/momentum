"""/profile — card plus per-field editing.

`users` is written only by the identity middleware; the fields edited here
land in `user_profiles`. See `handlers/onboarding.py` for the first-run
questionnaire that seeds this table, and `handlers/goal.py`/`handlers/
measure.py` for the other profile-family flows.
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from momentum.config import settings
from momentum.db import profiles as db_profiles
from momentum.formatters import profile as fmt_profile
from momentum.handlers._profile_common import HEIGHT_CM_RANGE, read_birth_date, read_number
from momentum.handlers._prompts import drop_prompt_kb, send_prompt
from momentum.keyboards import common as kb_common
from momentum.keyboards import profile as kb_profile
from momentum.keyboards.callbacks import ProfileCB, SexCB
from momentum.services import periods
from momentum.states import EditProfile
from momentum.texts import common as texts_common
from momentum.texts import profile as texts_profile

router = Router(name="profile")


async def _send_profile_card(message: Message, user_id: int) -> None:
    profile = await db_profiles.get_profile(user_id)
    card = fmt_profile.profile_card(profile, periods.today_in(settings.tz))
    await message.answer(card, reply_markup=kb_profile.profile_kb())


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _send_profile_card(message, message.from_user.id)


@router.callback_query(ProfileCB.filter(F.action == "edit_sex"))
async def edit_sex(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(EditProfile.sex)
    await callback.message.answer(texts_profile.ASK_SEX, reply_markup=kb_profile.sex_kb())


@router.callback_query(EditProfile.sex, SexCB.filter())
async def save_sex(callback: CallbackQuery, callback_data: SexCB, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await db_profiles.set_sex(callback.from_user.id, callback_data.value)
    await callback.message.answer(texts_profile.SEX_UPDATED)
    await _send_profile_card(callback.message, callback.from_user.id)


@router.callback_query(ProfileCB.filter(F.action == "edit_birth"))
async def edit_birth_date(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await state.set_state(EditProfile.birth_date)
    await send_prompt(
        bot,
        callback.message.chat.id,
        state,
        texts_profile.ASK_BIRTH_DATE,
        kb_common.cancel_kb(),
    )


@router.message(EditProfile.birth_date, F.text)
async def save_birth_date(message: Message, state: FSMContext, bot: Bot) -> None:
    birth_date = await read_birth_date(message)
    if birth_date is None:
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.clear()
    await db_profiles.set_birth_date(message.from_user.id, birth_date)
    await message.answer(texts_profile.BIRTH_DATE_UPDATED)
    await _send_profile_card(message, message.from_user.id)


@router.callback_query(ProfileCB.filter(F.action == "edit_height"))
async def edit_height(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await state.set_state(EditProfile.height)
    await send_prompt(
        bot, callback.message.chat.id, state, texts_profile.ASK_HEIGHT, kb_common.cancel_kb()
    )


@router.message(EditProfile.height, F.text)
async def save_height(message: Message, state: FSMContext, bot: Bot) -> None:
    height = await read_number(
        message, HEIGHT_CM_RANGE, texts_profile.err_height_range(*HEIGHT_CM_RANGE)
    )
    if height is None:
        return

    await drop_prompt_kb(bot, message.chat.id, state)
    await state.clear()
    await db_profiles.set_height_cm(message.from_user.id, height)
    await message.answer(texts_profile.HEIGHT_UPDATED)
    await _send_profile_card(message, message.from_user.id)


# --------------------------------------------------------------------------
# Fallbacks — registered last, so the specific handlers above always win
# --------------------------------------------------------------------------


@router.message(StateFilter(EditProfile.sex))
async def expects_button(message: Message) -> None:
    await message.answer(texts_profile.ERR_USE_BUTTONS)


@router.message(EditProfile.birth_date)
async def expects_date(message: Message) -> None:
    await message.answer(texts_common.ERR_DATE_PARSE)


@router.message(EditProfile.height)
async def expects_number(message: Message) -> None:
    await message.answer(texts_profile.ERR_NUMBER)
