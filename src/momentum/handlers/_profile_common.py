"""Shared parsing helpers and the stale-click catch-all for the profile family.

`router` here must be included *after* `onboarding`, `profile`, `goal`, and
`measure` — `ignore_stale_click` has no state filter, so if it ran first it
would swallow clicks meant for those routers' specific handlers.
"""

from __future__ import annotations

import re
from datetime import date

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from momentum.config import settings
from momentum.keyboards.callbacks import GoalTypeCB, ProfileCB, SexCB, SkipCB
from momentum.services import periods
from momentum.texts import common as texts_common
from momentum.texts import profile as texts_profile

router = Router(name="profile_fallbacks")

# Sanity bounds for the free-text answers — a typo shouldn't poison the stats.
HEIGHT_CM_RANGE = (50.0, 250.0)
WEIGHT_KG_RANGE = (20.0, 400.0)
GIRTH_CM_RANGE = (10.0, 250.0)
AGE_YEARS_RANGE = (10, 100)

# `SkipCB.step` ids: a keyboard left over from an earlier question carries the
# wrong id and is ignored instead of skipping the question now on screen.
STEP_BIRTH_DATE = "birth"
STEP_SEX = "sex"
STEP_HEIGHT = "height"
STEP_GOAL_TYPE = "goal"
STEP_TARGET_WEIGHT = "target"
STEP_WEIGHT = "weight"

_NUMBER_RE = re.compile(r"^\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*[a-zA-Zа-яёА-ЯЁ.]*\s*$")


def _parse_number(text: str | None) -> float | None:
    """Accepts `82`, `82,5`, `82.5`, `82 кг`. Returns None if unparseable."""
    match = _NUMBER_RE.match(text or "")
    return float(match.group(1).replace(",", ".")) if match else None


async def read_number(
    message: Message, bounds: tuple[float, float], out_of_range: str
) -> float | None:
    """Parse a numeric answer, replying with the right complaint if it won't do."""
    value = _parse_number(message.text)
    if value is None:
        await message.answer(texts_profile.ERR_NUMBER)
        return None

    low, high = bounds
    if not low <= value <= high:
        await message.answer(out_of_range)
        return None
    return value


async def read_birth_date(message: Message) -> date | None:
    today = periods.today_in(settings.tz)
    parsed = periods.parse_user_date(message.text, today)

    if parsed is None:
        await message.answer(texts_common.ERR_DATE_PARSE)
        return None
    if parsed > today:
        await message.answer(texts_profile.ERR_BIRTH_DATE_FUTURE)
        return None

    low, high = AGE_YEARS_RANGE
    if not low <= periods.years_since(parsed, today) <= high:
        await message.answer(texts_profile.err_age_range(low, high))
        return None
    return parsed


@router.callback_query(SkipCB.filter())
@router.callback_query(SexCB.filter())
@router.callback_query(GoalTypeCB.filter())
@router.callback_query(ProfileCB.filter())
async def ignore_stale_click(callback: CallbackQuery) -> None:
    """A button from a flow that has since ended — dismiss the spinner quietly."""
    await callback.answer()
