"""Rendering of admin suggestion-triage cards (HTML parse mode)."""

from __future__ import annotations

from html import escape

from momentum.db.models import ImprovementRequest
from momentum.formatters._shared import truncate
from momentum.texts import admin as texts_admin
from momentum.texts import common as texts_common


def suggestion_card(request: ImprovementRequest) -> str:
    """Detail view. Author name and request text are attacker-controlled."""
    return "\n".join(
        [
            f"{texts_admin.LABEL_SUGGESTION} #{request.id}",
            f"{texts_admin.LABEL_STATUS}: {texts_admin.suggestion_status_label(request.status)}",
            f"{texts_admin.LABEL_SENT_AT}: {texts_common.fmt_datetime(request.created_at)}",
            f"{texts_admin.LABEL_AUTHOR}: {escape(request.user_full_name)}",
            f"{texts_admin.LABEL_TELEGRAM_ID}: <code>{request.user_id}</code>",
            "",
            escape(request.request_text),
        ]
    )


def suggestion_row_label(request: ImprovementRequest) -> str:
    preview = " ".join(request.request_text.split())
    author = request.user_full_name.strip() or texts_admin.ADMIN_NO_NAME
    date_part = texts_common.fmt_date_short(request.created_at.date())
    return truncate(f"#{request.id} · {date_part} · {author} · {preview}")
