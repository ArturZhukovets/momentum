"""Typed ``CallbackData`` factories for every inline keyboard, plus pagination size."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

PAGE_SIZE = 7


class ActionCB(CallbackData, prefix="act"):
    """Generic flow control: cancel, skip, parts_done."""

    name: str


class TypeCB(CallbackData, prefix="type"):
    value: str  # running | swimming | elliptical | gym | home_workout


class ChoiceCB(CallbackData, prefix="choice"):
    field: str  # FieldSpec.name the choice belongs to
    value: str


class PartCB(CallbackData, prefix="part"):
    value: str  # a body part DB value


class DateCB(CallbackData, prefix="date"):
    value: str  # today | yesterday | custom


class HistCB(CallbackData, prefix="hist"):
    action: str  # page | open
    value: int  # page number, or workout id for `open`
    page: int = 1  # page to return to from a detail card


class WorkoutCB(CallbackData, prefix="wk"):
    action: str  # desc | date | del | del_yes | back
    workout_id: int
    page: int


# Profile / onboarding factories. `SkipCB` carries the step being skipped so a
# keyboard left over from an earlier question can't skip the current one.


class SkipCB(CallbackData, prefix="skip"):
    step: str  # the state name the prompt belongs to


class SexCB(CallbackData, prefix="sex"):
    value: str  # male | female


class GoalTypeCB(CallbackData, prefix="goal"):
    value: str  # lose | gain | maintain | muscle


class ProfileCB(CallbackData, prefix="prof"):
    # show | edit_sex | edit_birth | edit_height | new_goal | body_measure | measure_save
    # | measure_confirm | measure_edit
    action: str


class MeasureFieldCB(CallbackData, prefix="mfield"):
    field: str  # weight_kg | chest_cm | waist_cm | hips_cm | thigh_cm | arm_cm — which to redo


# Admin factories. Distinct `adm_` prefixes so router order never matters, and
# only ids/filters travel in the payload — never names or free text.


class AdminMenuCB(CallbackData, prefix="adm_menu"):
    section: str  # menu | sug | usr | close


class AdminSuggestionCB(CallbackData, prefix="adm_sug"):
    action: str  # list | open | set
    status: str  # active list filter: new | approved | done | rejected | all
    target: str = ""  # new status, `set` only
    request_id: int = 0
    page: int = 1


class AdminUserCB(CallbackData, prefix="adm_usr"):
    action: str  # list | open | week | month
    user_id: int = 0
    page: int = 1  # users list page


class AdminWorkoutCB(CallbackData, prefix="adm_wk"):
    action: str  # list | open
    user_id: int
    workout_id: int = 0
    page: int = 1  # workouts page
    users_page: int = 1  # users list page, to walk back out
