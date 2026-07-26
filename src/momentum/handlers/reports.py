"""/week and /month — the same text the scheduler broadcasts."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from momentum import texts
from momentum.config import settings
from momentum.services import periods, reports

router = Router(name="reports")


@router.message(Command("week"))
@router.message(F.text == texts.BTN_WEEK)
async def cmd_week(message: Message) -> None:
    today = periods.today_in(settings.tz)
    await message.answer(await reports.build_weekly_text(message.from_user.id, today))


@router.message(Command("month"))
@router.message(F.text == texts.BTN_MONTH)
async def cmd_month(message: Message) -> None:
    today = periods.today_in(settings.tz)
    await message.answer(await reports.build_monthly_text(message.from_user.id, today))
