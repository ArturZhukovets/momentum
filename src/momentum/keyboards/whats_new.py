"""«Что нового» — buttons to flip to the other versions' notes."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from momentum.keyboards.callbacks import WhatsNewCB
from momentum.texts import whats_new as texts_whats_new


def versions_kb(versions: Sequence[str], shown: str) -> InlineKeyboardMarkup | None:
    """One button per other version, two per row; ``None`` when there is nothing else."""
    others = [v for v in versions if v != shown]
    if not others:
        return None

    builder = InlineKeyboardBuilder()
    for v in others:
        builder.add(
            InlineKeyboardButton(
                text=texts_whats_new.older_label(v),
                callback_data=WhatsNewCB(version=v).pack(),
            )
        )
    builder.adjust(2)
    return builder.as_markup()
