"""Report text builders + the fan-out send used by the scheduler."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from momentum.config import settings
from momentum.db import goals as db_goals
from momentum.db import measurements as db_measurements
from momentum.db import profiles as db_profiles
from momentum.db import users as db_users
from momentum.db import workouts as db_workouts
from momentum.db.models import UserProfile, WorkoutStatRow
from momentum.formatters import reports as fmt_reports
from momentum.services import periods, stats
from momentum.services.energy import ProfileField, build_energy, missing_profile_fields
from momentum.services.measurements import (
    ReportBody,
    build_period_change,
    kg_left,
    latest_weight_kg,
    period_tone,
)
from momentum.services.pace import build_pace

log = logging.getLogger(__name__)

SEND_DELAY = 0.05


async def build_weekly_text(user_id: int, ref: date, *, read_only: bool = False) -> str:
    """Weekly report for the week containing `ref` — workouts plus goal/measurements/energy.

    ``read_only`` (the admin preview) renders without spending the one-time nudge.
    """
    # Wider than the calendar week: streak walks back up to 52 weeks, so we load
    # that history in one query. The formatter still shows only this Mon–Sun.
    stats_start, stats_end = stats.weekly_range(ref)
    workouts_for_stats = await db_workouts.list_workouts_for_stats(user_id, stats_start, stats_end)
    workout_stats = stats.build_weekly_stats(workouts_for_stats, ref, settings.WEEKLY_GOAL)
    period_start, period_end = periods.week_bounds(ref)
    body = await _report_body(
        user_id, ref, period_start, period_end, workouts_for_stats, read_only=read_only
    )
    return fmt_reports.weekly_report(workout_stats, body)


async def build_monthly_text(user_id: int, ref: date, *, read_only: bool = False) -> str:
    """Monthly report for the month containing `ref` — workouts plus goal/measurements/energy.

    ``read_only`` (the admin preview) renders without spending the one-time nudge.
    """
    # This month + previous month, so the "vs last month" line needs no extra query.
    stats_start, stats_end = stats.monthly_range(ref)
    workouts_for_stats = await db_workouts.list_workouts_for_stats(user_id, stats_start, stats_end)
    month_start, month_end = periods.month_bounds(ref)
    body_parts = await db_workouts.body_part_counts(user_id, month_start, month_end)
    workout_stats = stats.build_monthly_stats(workouts_for_stats, body_parts, ref)
    body = await _report_body(
        user_id, ref, month_start, month_end, workouts_for_stats, read_only=read_only
    )
    return fmt_reports.monthly_report(workout_stats, body)


async def _report_body(
    user_id: int,
    ref: date,
    start: date,
    end: date,
    workouts: list[WorkoutStatRow],
    *,
    read_only: bool,
) -> ReportBody:
    """Active goal, in-period measurement change (pre-period rows as baseline), pace and energy.

    Loads every measurement up to ``end`` with no ``start`` bound, so deltas can
    use the last value before the period. Whether anything was recorded inside
    the window is decided by ``build_period_change``; the pace trims its own
    window from the same rows, and the energy takes the latest weight from them.
    ``workouts`` is the stats projection already loaded; the energy trims it to
    the period.
    """
    goal = await db_goals.get_active_goal(user_id)
    rows = await db_measurements.list_measurements(user_id, end=end)
    profile = await db_profiles.get_profile(user_id)
    change = build_period_change(rows, start, end)
    weight_kg = latest_weight_kg(rows)
    # Spends the one-time nudge here, before sending: a failed send loses it for good.
    profile_nudge = await _profile_nudge(user_id, profile, weight_kg, read_only=read_only)
    return ReportBody(
        change=change,
        goal=goal,
        tone=period_tone(change, goal),
        kg_left=kg_left(change, goal),
        pace=build_pace(rows, goal, end),
        energy=build_energy(profile, weight_kg, goal, workouts, start, end, ref),
        profile_nudge=profile_nudge,
    )


async def _profile_nudge(
    user_id: int, profile: UserProfile | None, weight_kg: float | None, *, read_only: bool
) -> tuple[ProfileField, ...]:
    """Missing profile answers to ask for — once per user, and only when they alone hide energy.

    Without a weight the report already asks for /measure, so the nudge waits.
    """
    missing = missing_profile_fields(profile)
    if not missing or weight_kg is None or read_only:
        return ()
    return missing if await db_users.claim_profile_nudge(user_id) else ()


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
                # Resend the same text: rebuilding would drop a nudge the first build spent.
                await bot.send_message(user.user_id, text)
                sent += 1
            except Exception:
                log.exception("Retry failed for %s", user.user_id)
        except Exception:
            log.exception("Failed to send %s report to %s", kind, user.user_id)

        await asyncio.sleep(SEND_DELAY)

    log.info("Broadcast %s finished: %d/%d sent", kind, sent, len(subscribers))
