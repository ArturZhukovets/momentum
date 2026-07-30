"""Rendering of admin user-browsing cards (HTML parse mode)."""

from __future__ import annotations

from html import escape

from momentum.db.models import UserBrief
from momentum.formatters._shared import truncate
from momentum.texts import admin as texts_admin
from momentum.texts import common as texts_common


def _display_name(user: UserBrief) -> str:
    return (
        (user.first_name or "").strip()
        or (user.username or "").strip()
        or texts_admin.ADMIN_NO_NAME
    )


def user_title(user: UserBrief) -> str:
    """One-line header shown above another user's history or report."""
    handle = f" (@{escape(user.username)})" if user.username else ""
    return f"👤 <b>{escape(_display_name(user))}</b>{handle}"


def user_card(user: UserBrief) -> str:
    return "\n".join(
        [
            user_title(user),
            f"{texts_admin.LABEL_TELEGRAM_ID}: <code>{user.user_id}</code>",
            f"{texts_admin.LABEL_REGISTERED}: {texts_common.fmt_date(user.created_at.date())}",
            f"{texts_admin.LABEL_WORKOUTS_COUNT}: {user.workout_count}",
        ]
    )


def user_row_label(user: UserBrief) -> str:
    handle = f" @{user.username}" if user.username else ""
    return truncate(
        f"{_display_name(user)}{handle} · {user.user_id} · "
        f"{user.workout_count} {texts_common.workouts_word(user.workout_count)}"
    )
