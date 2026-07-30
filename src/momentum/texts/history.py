"""/history — list, detail card, edit and delete."""

from __future__ import annotations

from momentum.texts.common import workouts_word

HISTORY_EMPTY = "Пока нет ни одной тренировки. Добавь первую — /add 💪"
BTN_PREV_PAGE = "‹ Назад"
BTN_NEXT_PAGE = "Вперёд ›"
BTN_BACK = "‹ Назад"
BTN_EDIT_DESCRIPTION = "✏️ Описание"
BTN_EDIT_DATE = "📅 Дата"
BTN_DELETE = "🗑 Удалить"
BTN_DELETE_YES = "Да, удалить"

ASK_NEW_DESCRIPTION = "Введи новое описание."
ASK_NEW_DATE = "Введи новую дату в формате ДД.ММ.ГГГГ."
ASK_DELETE_CONFIRM = "Удалить эту тренировку?"

DESCRIPTION_UPDATED = "✅ Описание обновлено."
DATE_UPDATED = "✅ Дата обновлена."
WORKOUT_DELETED = "🗑 Тренировка удалена."
WORKOUT_NOT_FOUND = "Тренировка не найдена."


def history_header(page: int, pages: int, total: int) -> str:
    return f"📜 <b>История</b> — {total} {workouts_word(total)}\nСтраница {page} из {pages}"
