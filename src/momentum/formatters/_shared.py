"""Internal helpers shared by more than one formatter submodule."""

from __future__ import annotations

ROW_LABEL_LIMIT = 60


def truncate(label: str, limit: int = ROW_LABEL_LIMIT) -> str:
    """Shorten a plain-text button label; buttons are not HTML."""
    return label[:limit] + "…" if len(label) > limit + 1 else label
