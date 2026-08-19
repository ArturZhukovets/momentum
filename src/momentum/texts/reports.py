"""/week, /month, and the scheduled broadcast."""

from __future__ import annotations

from typing import Literal

from momentum.texts.common import weeks_word

ReportKind = Literal["week", "month"]

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

# Collection order: weight, chest, waist, hips, thigh, arm — same as /measure.
FACT_FIELDS: tuple[str, ...] = (
    "weight_kg",
    "chest_cm",
    "waist_cm",
    "hips_cm",
    "thigh_cm",
    "arm_cm",
)

FACT_BULLET = "•"
DELTA_GOOD = "🟢"
DELTA_BAD = "🔴"

TONE_REACHED = (
    "🏆 Цель по весу достигнута. Можно выдохнуть и зафиксировать это в /goal, "
    "когда будешь готов к следующей."
)

_NO_MEASUREMENTS: dict[ReportKind, str] = {
    "week": (
        "На этой неделе замеров не было, поэтому в отчёте только тренировки. "
        "Если записывать вес хотя бы раз в неделю через /measure, здесь появится, "
        "как тело движется к цели."
    ),
    "month": (
        "В этом месяце замеров не было, поэтому в отчёте только тренировки. "
        "Если записывать вес хотя бы раз в неделю через /measure, здесь появится, "
        "как тело движется к цели."
    ),
}

_TONE_SETBACK: dict[ReportKind, str] = {
    "week": (
        "ℹ️ Небольшая просадка — вес так и гуляет, это не откат всей работы. "
        "Главное не бросать замеры; на следующей неделе будет с чем сравнить."
    ),
    "month": (
        "ℹ️ Небольшая просадка — вес так и гуляет, это не откат всей работы. "
        "Главное не бросать замеры; в следующем месяце будет с чем сравнить."
    ),
}


def streak_line(weeks: int) -> str:
    return f"{LABEL_STREAK}: {weeks} {weeks_word(weeks)} подряд с выполненной целью"


def goal_line(goal_type: str, target: str | None) -> str:
    """Anchor line: where we're going, without live weight or percents."""
    if goal_type == "lose":
        if target is None:
            return "🎯 Цель — сбросить вес."
        return f"🎯 Цель — сбросить вес до {target} кг."
    if goal_type == "gain":
        if target is None:
            return "🎯 Цель — набрать вес."
        return f"🎯 Цель — набрать вес до {target} кг."
    if goal_type == "muscle":
        if target is None:
            return "🎯 Цель — набрать мышцы."
        return f"🎯 Цель — набрать мышцы, ориентир по весу {target} кг."
    if goal_type == "maintain":
        if target is None:
            return "🎯 Цель — держать форму."
        return f"🎯 Цель — держать форму около {target} кг."
    return ""


def marked_delta(signed: str, good: bool | None) -> str:
    """Prefix a signed delta with a red/green mark, or leave it plain."""
    if good is True:
        return f"{DELTA_GOOD} {signed}"
    if good is False:
        return f"{DELTA_BAD} {signed}"
    return signed


def field_phrase(label: str, value: str, unit: str, delta: str | None) -> str:
    """One list row: '• Вес — 82,5 кг (−0,5 кг с 10.08)'."""
    amount = f"{value} {unit}"
    if delta is None:
        return f"{FACT_BULLET} {label} — {amount}"
    return f"{FACT_BULLET} {label} — {amount} {delta}"


def facts_line(kind: ReportKind, fields: str) -> str:
    heading = "На этой неделе:" if kind == "week" else "В этом месяце:"
    return f"{heading}\n{fields}"


def tone_progress(kind: ReportKind, left: str | None) -> str:
    """Closer-to-goal sentence; ``left`` is already formatted, without the unit."""
    if kind == "week":
        if left is None:
            return "✨ Ты ближе, чем неделю назад. Так держать."
        return f"✨ Осталось {left} кг — ты ближе, чем неделю назад. Так держать."
    if left is None:
        return "✨ За месяц ты заметно ближе к цели. Так держать."
    return f"✨ Осталось {left} кг — за месяц ты заметно ближе к цели. Так держать."


def tone_setback(kind: ReportKind) -> str:
    return _TONE_SETBACK[kind]


def no_measurements(kind: ReportKind) -> str:
    return _NO_MEASUREMENTS[kind]
