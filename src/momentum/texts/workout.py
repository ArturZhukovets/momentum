"""The add-workout flow: body parts, prompts, and the workout card."""

from __future__ import annotations

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
# Add flow
# --------------------------------------------------------------------------

BTN_CARDIO = "🏃 Кардио"
BTN_STRENGTH = "💪 Силовая"
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

WORKOUT_SAVED = "✅ Записал!"


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
