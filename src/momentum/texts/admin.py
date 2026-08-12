"""Admin panel: menu, suggestion triage, and read-only user browsing."""

from __future__ import annotations

from momentum.texts.common import suggestions_word, users_word

ADMIN_COMMAND_DESCRIPTION = "админ-панель"

ADMIN_MENU_TITLE = "🛠 <b>Админ-панель</b>\nВыбери раздел."
ADMIN_CLOSED = "🛠 Админ-панель закрыта."
ADMIN_DENIED = "Нет доступа."
ADMIN_UNKNOWN_ACTION = "Действие больше недоступно."

BTN_ADMIN_SUGGESTIONS = "💡 Предложения"
BTN_ADMIN_USERS = "👥 Пользователи"
BTN_ADMIN_CLOSE = "✖️ Закрыть"
BTN_ADMIN_TO_MENU = "‹ В меню"
BTN_ADMIN_TO_LIST = "‹ К списку"
BTN_ADMIN_TO_USERS = "‹ К пользователям"
BTN_ADMIN_TO_USER = "‹ К пользователю"

# Suggestions ---------------------------------------------------------------

SUGGESTION_FILTER_ALL = "all"

SUGGESTION_FILTER_LABELS: dict[str, str] = {
    "new": "🆕 Новые",
    "approved": "👍 Одобренные",
    "done": "✅ Сделанные",
    "rejected": "🚫 Отклонённые",
    SUGGESTION_FILTER_ALL: "📋 Все",
}

SUGGESTION_STATUS_LABELS: dict[str, str] = {
    "new": "🆕 новое",
    "approved": "👍 одобрено",
    "done": "✅ сделано",
    "rejected": "🚫 отклонено",
}

SUGGESTION_ACTION_LABELS: dict[str, str] = {
    "new": "🆕 В новые",
    "approved": "👍 Одобрить",
    "done": "✅ Сделано",
    "rejected": "🚫 Отклонить",
}


def suggestion_filter_label(value: str) -> str:
    return SUGGESTION_FILTER_LABELS.get(value, value)


def suggestion_status_label(value: str) -> str:
    return SUGGESTION_STATUS_LABELS.get(value, value)


def suggestion_action_label(value: str) -> str:
    return SUGGESTION_ACTION_LABELS.get(value, value)


LABEL_SUGGESTION = "💡 <b>Предложение</b>"
LABEL_STATUS = "Статус"
LABEL_AUTHOR = "Автор"
LABEL_TELEGRAM_ID = "Telegram ID"
LABEL_SENT_AT = "Отправлено"
LABEL_REGISTERED = "Регистрация"
LABEL_WORKOUTS_COUNT = "Тренировок"

ADMIN_SUGGESTION_NOT_FOUND = "Предложение не найдено."
ADMIN_STATUS_UPDATED = "Статус обновлён."


def admin_suggestions_header(status_filter: str, page: int, pages: int, total: int) -> str:
    return (
        f"💡 <b>Предложения</b> — {suggestion_filter_label(status_filter)}\n"
        f"{total} {suggestions_word(total)}, страница {page} из {pages}"
    )


def admin_suggestions_empty(status_filter: str) -> str:
    return f"💡 <b>Предложения</b> — {suggestion_filter_label(status_filter)}\nЗдесь пока пусто."


# Users ---------------------------------------------------------------------

ADMIN_NO_NAME = "без имени"
ADMIN_USERS_EMPTY = "👥 <b>Пользователи</b>\nПока никто не зарегистрирован."
ADMIN_USER_NOT_FOUND = "Пользователь не найден."
ADMIN_HISTORY_EMPTY = "У пользователя пока нет тренировок."


def admin_users_header(page: int, pages: int, total: int) -> str:
    return f"👥 <b>Пользователи</b> — {total} {users_word(total)}\nСтраница {page} из {pages}"
