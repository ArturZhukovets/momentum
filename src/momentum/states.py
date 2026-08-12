"""FSM state groups for interactive bot flows."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddWorkout(StatesGroup):
    choosing_type = State()
    field_input = State()
    choosing_date = State()
    custom_date = State()


class EditWorkout(StatesGroup):
    awaiting_description = State()
    awaiting_date = State()


class Suggestion(StatesGroup):
    awaiting_text = State()


class Onboarding(StatesGroup):
    """First-run questionnaire. Every step can be skipped."""

    birth_date = State()
    sex = State()
    height = State()

    # Also entered from /goal when the user has no active goal yet.
    goal_type = State()
    target_weight = State()

    weight = State()


class Measure(StatesGroup):
    """/measure — weight first, then the circumferences on request."""

    weight = State()
    offering_body = State()

    chest = State()
    waist = State()
    hips = State()
    thigh = State()
    arm = State()

    review = State()
    choosing_field = State()


class EditProfile(StatesGroup):
    sex = State()
    birth_date = State()
    height = State()
