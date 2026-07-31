"""/goal — view the active goal, or start setting one.

The actual goal-type/target-weight questions are asked by
`handlers/onboarding.py` (`_ask_goal_type`), since they run on the shared
`Onboarding.goal_type`/`Onboarding.target_weight` states used mid-onboarding
too.
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from momentum.db import goals as db_goals
from momentum.db import measurements as db_measurements
from momentum.formatters import profile as fmt_profile
from momentum.handlers import onboarding as onboarding_handlers
from momentum.keyboards import profile as kb_profile
from momentum.keyboards.callbacks import ProfileCB
from momentum.texts import profile as texts_profile

router = Router(name="goal")


@router.message(Command("goal"))
async def cmd_goal(message: Message, state: FSMContext) -> None:
    await state.clear()
    goal = await db_goals.get_active_goal(message.from_user.id)
    if goal is None:
        await message.answer(texts_profile.GOAL_EMPTY, reply_markup=kb_profile.new_goal_kb())
        return

    current = await db_measurements.latest_weight(message.from_user.id)
    await message.answer(fmt_profile.goal_card(goal, current))


@router.callback_query(ProfileCB.filter(F.action == "new_goal"))
async def start_goal(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Only reachable while no goal is active — swapping goals comes later."""
    await callback.answer()
    if await db_goals.get_active_goal(callback.from_user.id) is not None:
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await state.update_data(goal_only=True)
    await onboarding_handlers._ask_goal_type(bot, callback.message.chat.id, state, step=None)
