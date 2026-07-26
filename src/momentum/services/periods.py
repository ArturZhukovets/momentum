"""Timezone-aware week/month boundary maths. Pure — no aiogram, no DB."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_DATE_RE = re.compile(r"^\s*(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\s*$")


def today_in(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


# --------------------------------------------------------------------------
# Weeks (Mon–Sun)
# --------------------------------------------------------------------------


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_bounds(d: date) -> tuple[date, date]:
    start = week_start(d)
    return start, start + timedelta(days=6)


def shift_weeks(start: date, weeks: int) -> date:
    return start + timedelta(weeks=weeks)


def prev_week_bounds(d: date) -> tuple[date, date]:
    return week_bounds(week_start(d) - timedelta(days=7))


# --------------------------------------------------------------------------
# Months
# --------------------------------------------------------------------------


def month_bounds(d: date) -> tuple[date, date]:
    last_day = monthrange(d.year, d.month)[1]
    return d.replace(day=1), d.replace(day=last_day)


def prev_month_bounds(d: date) -> tuple[date, date]:
    return month_bounds(d.replace(day=1) - timedelta(days=1))


def weeks_touched(start: date, end: date) -> int:
    """Number of distinct Mon-anchored calendar weeks the range overlaps."""
    first = week_start(start)
    last = week_start(end)
    return ((last - first).days // 7) + 1


# --------------------------------------------------------------------------
# User input
# --------------------------------------------------------------------------


def parse_user_date(text: str, today: date) -> date | None:
    """Parse DD.MM.YYYY or DD.MM (current year). Returns None if unparseable."""
    match = _DATE_RE.match(text or "")
    if not match:
        return None

    day_s, month_s, year_s = match.groups()
    day, month = int(day_s), int(month_s)

    if year_s is None:
        year = today.year
    else:
        year = int(year_s)
        if year < 100:
            year += 2000

    try:
        return date(year, month, day)
    except ValueError:
        return None
