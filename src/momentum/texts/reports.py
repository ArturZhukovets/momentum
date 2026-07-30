"""/week, /month, and the scheduled broadcast."""

from __future__ import annotations

from momentum.texts.common import weeks_word

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
