"""FSM state groups for the add and edit flows."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddWorkout(StatesGroup):
    choosing_kind = State()

    cardio_photo = State()
    cardio_description = State()

    strength_parts = State()
    strength_description = State()

    choosing_date = State()
    custom_date = State()


class EditWorkout(StatesGroup):
    awaiting_description = State()
    awaiting_date = State()
