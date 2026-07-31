"""Onboarding and profile flows: sex, goal type, skip, profile edit, measure."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from momentum.keyboards.callbacks import GoalTypeCB, ProfileCB, SexCB, SkipCB
from momentum.keyboards.common import CANCEL_BUTTON
from momentum.texts import common as texts_common
from momentum.texts import profile as texts_profile


def _skip_button(step: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=texts_common.BTN_SKIP, callback_data=SkipCB(step=step).pack())


def skip_cancel_kb(step: str, *, cancel: bool = True) -> InlineKeyboardMarkup:
    """The plain «skip / cancel» prompt used by every free-text question.

    `cancel=False` drops the Отмена button — onboarding uses this so a stray
    tap can't abandon the flow; /goal and /measure keep the default.
    """
    rows = [[_skip_button(step)]]
    if cancel:
        rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sex_kb(step: str | None = None, *, cancel: bool = True) -> InlineKeyboardMarkup:
    """`step` is None where skipping makes no sense — editing one field."""
    rows = [
        [
            InlineKeyboardButton(
                text=texts_profile.sex_label(value), callback_data=SexCB(value=value).pack()
            )
            for value in texts_profile.SEXES
        ]
    ]
    if step is not None:
        rows.append([_skip_button(step)])
    if cancel:
        rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def goal_type_kb(step: str | None = None, *, cancel: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value in texts_profile.GOAL_TYPES:
        builder.button(
            text=texts_profile.goal_type_label(value), callback_data=GoalTypeCB(value=value)
        )
    builder.adjust(2)
    if step is not None:
        builder.row(_skip_button(step))
    if cancel:
        builder.row(CANCEL_BUTTON)
    return builder.as_markup()


def start_onboarding_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_profile.BTN_START_ONBOARDING,
                    callback_data=ProfileCB(action="start_onboarding").pack(),
                )
            ]
        ]
    )


def profile_kb() -> InlineKeyboardMarkup:
    """Per-field edit buttons under the profile card."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_profile.BTN_EDIT_SEX,
                    callback_data=ProfileCB(action="edit_sex").pack(),
                ),
                InlineKeyboardButton(
                    text=texts_profile.BTN_EDIT_BIRTH_DATE,
                    callback_data=ProfileCB(action="edit_birth").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts_profile.BTN_EDIT_HEIGHT,
                    callback_data=ProfileCB(action="edit_height").pack(),
                )
            ],
        ]
    )


def new_goal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_profile.BTN_NEW_GOAL,
                    callback_data=ProfileCB(action="new_goal").pack(),
                )
            ]
        ]
    )


def offer_body_measure_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_profile.BTN_BODY_MEASURE,
                    callback_data=ProfileCB(action="body_measure").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_profile.BTN_MEASURE_SAVE,
                    callback_data=ProfileCB(action="measure_save").pack(),
                )
            ],
        ]
    )
