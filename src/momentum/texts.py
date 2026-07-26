"""Every user-facing string lives here — nothing is hardcoded in handlers.

Code, identifiers, comments and DB values stay in English; only the string
*contents* are Russian.
"""

from __future__ import annotations

from datetime import date

# --------------------------------------------------------------------------
# Body parts — DB values (English) mapped to Russian labels with emoji
# --------------------------------------------------------------------------

FULL_BODY = "full_body"

BODY_PARTS: tuple[str, ...] = (
    "chest",
    "back",
    "legs",
    "shoulders",
    "arms",
    "core",
    FULL_BODY,
)

BODY_PART_LABELS: dict[str, str] = {
    "chest": "🫁 Грудь",
    "back": "🔙 Спина",
    "legs": "🦵 Ноги",
    "shoulders": "🤸 Плечи",
    "arms": "💪 Руки",
    "core": "🧘 Пресс/кор",
    FULL_BODY: "🔥 Всё тело",
}


def body_part_label(part: str) -> str:
    return BODY_PART_LABELS.get(part, part)


def body_parts_line(parts: tuple[str, ...] | list[str]) -> str:
    """Body parts in the canonical order, comma-separated."""
    ordered = [p for p in BODY_PARTS if p in parts]
    return ", ".join(body_part_label(p) for p in ordered)


# --------------------------------------------------------------------------
# Russian grammar / date helpers
# --------------------------------------------------------------------------

WEEKDAYS = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)

MONTHS_NOMINATIVE = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)

WORKOUTS_PLURAL = ("тренировка", "тренировки", "тренировок")
WEEKS_PLURAL = ("неделя", "недели", "недель")


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """Russian plural form for `n`: (1 тренировка, 2 тренировки, 5 тренировок)."""
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return forms[1]
    return forms[2]


def workouts_word(n: int) -> str:
    return plural(n, WORKOUTS_PLURAL)


def weeks_word(n: int) -> str:
    return plural(n, WEEKS_PLURAL)


def fmt_date(d: date) -> str:
    """05.07.2026"""
    return d.strftime("%d.%m.%Y")


def fmt_date_short(d: date) -> str:
    """05.07"""
    return d.strftime("%d.%m")


def fmt_weekday(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def fmt_month_year(d: date) -> str:
    """Июль 2026"""
    return f"{MONTHS_NOMINATIVE[d.month - 1]} {d.year}"


# --------------------------------------------------------------------------
# Menu / commands
# --------------------------------------------------------------------------

BTN_ADD = "➕ Добавить тренировку"
BTN_HISTORY = "📜 История"
BTN_WEEK = "📊 Неделя"
BTN_MONTH = "🗓 Месяц"

COMMAND_DESCRIPTIONS: tuple[tuple[str, str], ...] = (
    ("start", "начать"),
    ("add", "добавить тренировку"),
    ("history", "история"),
    ("week", "отчёт за неделю"),
    ("month", "отчёт за месяц"),
    ("suggest", "предложить улучшение"),
    ("reports_on", "включить авто-отчёты"),
    ("reports_off", "выключить авто-отчёты"),
    ("cancel", "отмена"),
    ("help", "помощь"),
)


def start_greeting(name: str | None) -> str:
    who = f", {name}" if name else ""
    return (
        f"Привет{who}! 👋\n\n"
        "Я <b>Momentum</b> — помогу вести дневник тренировок.\n"
        "Записывай тренировку сразу после зала, а я посчитаю статистику "
        "и буду присылать отчёты за неделю и месяц.\n\n"
        "Жми <b>➕ Добавить тренировку</b> или /add."
    )


HELP = (
    "<b>Momentum — дневник тренировок</b>\n\n"
    "<b>Команды</b>\n"
    "/add — добавить тренировку\n"
    "/history — история тренировок (можно редактировать и удалять)\n"
    "/week — отчёт за текущую неделю\n"
    "/month — отчёт за текущий месяц\n"
    "/suggest — предложить улучшение\n"
    "/reports_on — включить авто-отчёты\n"
    "/reports_off — выключить авто-отчёты\n"
    "/cancel — отменить текущее действие\n"
    "/help — эта справка\n\n"
    "<b>Как это работает</b>\n"
    "🏃 Кардио — можно приложить фото-подтверждение.\n"
    "💪 Силовая — отмечаешь, какие группы мышц качал.\n\n"
    "Отчёты приходят автоматически: за неделю — в понедельник, "
    "за месяц — первого числа."
)

# --------------------------------------------------------------------------
# Add flow
# --------------------------------------------------------------------------

BTN_CARDIO = "🏃 Кардио"
BTN_STRENGTH = "💪 Силовая"
BTN_CANCEL = "✖️ Отмена"
BTN_SKIP = "⏭ Пропустить"
BTN_DONE = "✅ Готово"
BTN_TODAY = "Сегодня"
BTN_YESTERDAY = "Вчера"
BTN_OTHER_DATE = "📅 Другая дата"

ASK_KIND = "Что за тренировка?"
ASK_CARDIO_PHOTO = "Пришли фото-подтверждение 📸"
ASK_PHOTO_AGAIN = "Жду именно фото 📸 — или нажми «⏭ Пропустить»."
ASK_DESCRIPTION = "Опиши тренировку (или пропусти)."
ASK_PARTS = "Что качал? Можно выбрать несколько."
ASK_PARTS_EMPTY = "Сначала выбери хотя бы одну группу мышц."
ASK_DATE = "Когда была тренировка?"
ASK_CUSTOM_DATE = "Введи дату в формате ДД.ММ.ГГГГ (например, 05.07.2026)."

ERR_DATE_FUTURE = "Дата не может быть в будущем"
ERR_DATE_PARSE = "Не понял дату. Формат: 05.07.2026"
ERR_TEXT_EXPECTED = "Жду текст сообщением."

CANCELLED = "Отменено"
NOTHING_TO_CANCEL = "Нечего отменять."

WORKOUT_SAVED = "✅ Записал!"


# --------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------

ASK_SUGGESTION = "Что ты хотел бы улучшить или изменить в боте? Напиши одним сообщением."
ERR_SUGGESTION_EMPTY = "Предложение не может быть пустым. Напиши пожелание текстом."
SUGGESTION_SAVED = "✅ Спасибо! Предложение сохранено."


def weekly_nudge(done: int, goal: int) -> str:
    return f"На этой неделе: {done} из {goal} 🎯"


# --------------------------------------------------------------------------
# Workout card
# --------------------------------------------------------------------------

KIND_TITLES = {
    "cardio": "🏃 Кардио",
    "strength": "💪 Силовая тренировка",
}

CARD_NO_DESCRIPTION = "<i>без описания</i>"

# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------

WEEKLY_TITLE = "📊 <b>Отчёт за неделю</b>"
MONTHLY_TITLE = "🗓 <b>Отчёт за месяц</b>"

WEEKLY_EMPTY = "На этой неделе тренировок не было. Начнём новую серию? 💪"
MONTHLY_EMPTY = "В этом месяце тренировок не было. Самое время начать! 💪"

REPORTS_ENABLED = "🔔 Авто-отчёты включены."
REPORTS_DISABLED = "🔕 Авто-отчёты выключены."

LABEL_TOTAL = "Всего тренировок"
LABEL_STRENGTH = "💪 Силовые"
LABEL_CARDIO = "🏃 Кардио"
LABEL_PREV_WEEK = "Прошлая неделя"
LABEL_PREV_MONTH = "Прошлый месяц"
LABEL_DIFF = "Разница"
LABEL_STREAK = "Серия"
LABEL_MONTH_TO_DATE = "В этом месяце"
LABEL_WEEKLY_AVG = "В среднем в неделю"
LABEL_BODY_PARTS = "Что качал"

DIFF_FROM_ZERO = "было 0"
DIFF_NO_CHANGE = "без изменений"


def streak_line(weeks: int) -> str:
    return f"{LABEL_STREAK}: {weeks} {weeks_word(weeks)} подряд с выполненной целью"
