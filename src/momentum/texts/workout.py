"""The add-workout flow: body parts, prompts, and the workout card."""

from __future__ import annotations

from momentum.services.workout_types import BODY_PARTS, FULL_BODY

# --------------------------------------------------------------------------
# Labels — DB values (English) mapped to Russian with emoji
# --------------------------------------------------------------------------

BODY_PART_LABELS: dict[str, str] = {
    "chest": "🫁 Грудь",
    "back": "🔙 Спина",
    "legs": "🦵 Ноги",
    "shoulders": "🤸 Плечи",
    "arms": "💪 Руки",
    "core": "🧘 Пресс/кор",
    FULL_BODY: "🔥 Всё тело",
}

TYPE_LABELS: dict[str, str] = {
    "running": "🏃 Бег",
    "swimming": "🏊 Плавание",
    "elliptical": "🌀 Эллипсоид",
    "gym": "💪 Зал",
    "home_workout": "🏠 Домашняя тренировка",
}

# Keep the old name until formatters/history catch up in a later step.
KIND_TITLES = TYPE_LABELS

EFFORT_LABELS: dict[str, str] = {
    "easy": "🟢 Легко",
    "moderate": "🟡 Средне",
    "hard": "🔴 Тяжело",
}

FIELD_PROMPTS: dict[str, str] = {
    "duration_min": "Сколько минут длилась тренировка?",
    "distance_km": "Какая дистанция в километрах? (например, 5 или 5,5)",
    "effort": (
        "Как ощущалась нагрузка?\n"
        "• Легко — мог спокойно говорить\n"
        "• Средне — дышал тяжелее, но держал темп\n"
        "• Тяжело — было трудно поддерживать разговор"
    ),
    "description": (
        "Расскажи, как прошла тренировка.\n\n"
        "💡 Можно коротко: над чем работал, что получилось, что было тяжело.\n"
        "Можно более подробно, с полным описанием упражнений и их повторений.\n"
        "Чем живее описание — тем точнее я разберу твои тренировки "
        "и подскажу в отчётах, куда двигаться дальше.\n"
        "(Нечего писать — просто пропусти этот шаг)"
    ),
    "body_parts": "Что качал? Можно выбрать несколько.",
}

ERR_DURATION = "Введи целое число минут от 1 до 600 — или нажми «⏭ Пропустить»."
ERR_DISTANCE = "Введи дистанцию в км (например, 5 или 5,5) — или нажми «⏭ Пропустить»."
ASK_PARTS_EMPTY = "Сначала выбери хотя бы одну группу мышц — или нажми «⏭ Пропустить»."


def body_part_label(part: str) -> str:
    return BODY_PART_LABELS.get(part, part)


def body_parts_line(parts: tuple[str, ...] | list[str]) -> str:
    """Body parts in the canonical order, comma-separated."""
    ordered = [p for p in BODY_PARTS if p in parts]
    return ", ".join(body_part_label(p) for p in ordered)


def type_label(workout_type: str) -> str:
    return TYPE_LABELS.get(workout_type, workout_type)


def choice_label(field: str, value: str) -> str:
    if field == "effort":
        return EFFORT_LABELS.get(value, value)
    return value


def field_prompt(field: str) -> str:
    return FIELD_PROMPTS[field]


# --------------------------------------------------------------------------
# Add flow
# --------------------------------------------------------------------------

BTN_DONE = "✅ Готово"
BTN_TODAY = "Сегодня"
BTN_YESTERDAY = "Вчера"
BTN_OTHER_DATE = "📅 Другая дата"

ASK_TYPE = "Выбери тип тренировки:"
ASK_DATE = "Когда была тренировка?"
ASK_CUSTOM_DATE = "Введи дату в формате ДД.ММ.ГГГГ (например, 05.07.2026)."

WORKOUT_SAVED = "✅ Записал!"


def weekly_nudge(done: int, goal: int) -> str:
    return f"На этой неделе: {done} из {goal} 🎯"


# --------------------------------------------------------------------------
# Workout card
# --------------------------------------------------------------------------

CARD_NO_DESCRIPTION = "<i>без описания</i>"
