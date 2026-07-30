"""Report text builders + the fan-out send used by the scheduler."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from momentum.config import settings
from momentum.db import users as db_users
from momentum.db import workouts as db_workouts
from momentum.formatters import reports as fmt_reports
from momentum.services import periods, stats

log = logging.getLogger(__name__)

SEND_DELAY = 0.05


async def build_weekly_text(user_id: int, ref: date) -> str:
    """Weekly report for the week containing `ref`."""
    start, end = stats.weekly_range(ref)
    points = await db_workouts.points_between(user_id, start, end)
    return fmt_reports.weekly_report(stats.build_weekly_stats(points, ref, settings.WEEKLY_GOAL))


async def build_monthly_text(user_id: int, ref: date) -> str:
    """Monthly report for the month containing `ref`."""
    start, end = stats.monthly_range(ref)
    points = await db_workouts.points_between(user_id, start, end)
    month_start, month_end = periods.month_bounds(ref)
    body_parts = await db_workouts.body_part_counts(user_id, month_start, month_end)
    return fmt_reports.monthly_report(stats.build_monthly_stats(points, body_parts, ref))


async def broadcast(bot: Bot, kind: str, ref: date) -> None:
    """Send the weekly/monthly report to every subscribed user.

    Sends are sequential with a small delay; a user who blocked the bot is
    unsubscribed rather than allowed to break the run.
    """
    build = build_weekly_text if kind == "weekly" else build_monthly_text
    subscribers = await db_users.list_subscribers()
    log.info("Broadcasting %s report for %s to %d user(s)", kind, ref, len(subscribers))

    sent = 0
    for user in subscribers:
        try:
            text = await build(user.user_id, ref)
            await bot.send_message(user.user_id, text)
            sent += 1
        except TelegramForbiddenError:
            log.info("User %s blocked the bot — disabling reports", user.user_id)
            await db_users.set_reports_on(user.user_id, False)
        except TelegramRetryAfter as exc:
            log.warning("Rate limited, sleeping %ss before one retry", exc.retry_after)
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.send_message(user.user_id, await build(user.user_id, ref))
                sent += 1
            except Exception:
                log.exception("Retry failed for %s", user.user_id)
        except Exception:
            log.exception("Failed to send %s report to %s", kind, user.user_id)

        await asyncio.sleep(SEND_DELAY)

    log.info("Broadcast %s finished: %d/%d sent", kind, sent, len(subscribers))
