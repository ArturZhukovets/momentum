"""APScheduler cron jobs driving the automatic report broadcasts.

Job bodies are wrapped so that any exception is logged and never propagates
into the scheduler (which would otherwise drop the job).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from momentum.config import settings
from momentum.services import periods, reports

log = logging.getLogger(__name__)


async def run_weekly(bot: Bot) -> None:
    """Monday morning: report on the week that just ended."""
    try:
        ref = periods.today_in(settings.tz) - timedelta(days=1)
        await reports.broadcast(bot, "weekly", ref)
    except Exception:
        log.exception("Weekly broadcast failed")


async def run_monthly(bot: Bot) -> None:
    """First of the month: report on the month that just ended."""
    try:
        today = periods.today_in(settings.tz)
        ref = today.replace(day=1) - timedelta(days=1)
        await reports.broadcast(bot, "monthly", ref)
    except Exception:
        log.exception("Monthly broadcast failed")


def build_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.APP_TZ)

    scheduler.add_job(
        run_weekly,
        trigger="cron",
        day_of_week="mon",
        hour=settings.REPORT_HOUR,
        minute=0,
        args=(bot,),
        id="weekly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_monthly,
        trigger="cron",
        day=1,
        hour=settings.REPORT_HOUR,
        minute=0,
        args=(bot,),
        id="monthly_report",
        replace_existing=True,
    )

    log.info(
        "Scheduler configured: weekly Mon %02d:00, monthly 1st %02d:00 (%s)",
        settings.REPORT_HOUR,
        settings.REPORT_HOUR,
        settings.APP_TZ,
    )
    return scheduler
