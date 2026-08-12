"""Onboarding, profile, goal and body-measurement copy."""

from __future__ import annotations

# --------------------------------------------------------------------------
# Enum values (DB, English) mapped to Russian labels with emoji
# --------------------------------------------------------------------------

SEXES: tuple[str, ...] = ("male", "female")

SEX_LABELS: dict[str, str] = {
    "male": "♂️ Мужской",
    "female": "♀️ Женский",
}

GOAL_TYPES: tuple[str, ...] = ("lose", "gain", "maintain", "muscle")

GOAL_TYPE_LABELS: dict[str, str] = {
    "lose": "📉 Сбросить вес",
    "gain": "📈 Набрать вес",
    "muscle": "💪 Набрать мышцы",
    "maintain": "⚖️ Держать форму",
}


def sex_label(value: str) -> str:
    return SEX_LABELS.get(value, value)


def goal_type_label(value: str) -> str:
    return GOAL_TYPE_LABELS.get(value, value)


# --------------------------------------------------------------------------
# Units and empty values
# --------------------------------------------------------------------------

UNIT_KG = "кг"
UNIT_CM = "см"

VALUE_UNKNOWN = "<i>не указано</i>"

# --------------------------------------------------------------------------
# Onboarding
# --------------------------------------------------------------------------

ONBOARDING_OFFER = (
    "Начнём? 🚀\n"
    "Соберём стартовую информацию и наметим цель, к которой будем идти.\n"
    "Любой вопрос можно пропустить."
)

BTN_START_ONBOARDING = "🚀 Поехали"

ASK_BIRTH_DATE = "Когда ты родился? Формат ДД.ММ.ГГГГ (например, 05.07.1990)."
ASK_SEX = "Укажи пол."
ASK_HEIGHT = "Какой у тебя рост в сантиметрах? (например, 178)"
ASK_GOAL_TYPE = "К чему идём?"
ASK_TARGET_WEIGHT = "Какой вес хочешь получить? В килограммах (например, 75)."
ASK_CURRENT_WEIGHT = "Сколько весишь сейчас? В килограммах (например, 82,5)."

ONBOARDING_DONE = (
    "Готово, спасибо! 🎉\n\n"
    "Вот что теперь под рукой:\n"
    "👤 Глянуть или поправить данные профиля — /profile\n"
    "🎯 Посмотреть цель и как далеко до неё — /goal\n"
    "⚖️ Записать новый замер веса или записать замеры частей тела — /measure\n\n"
    "А теперь погнали тренироваться — /add 💪"
)

# --------------------------------------------------------------------------
# Profile card
# --------------------------------------------------------------------------

PROFILE_TITLE = "👤 <b>Профиль</b>"
PROFILE_EMPTY_HINT = "Профиль пока пустой — заполни, что не жалко 🙂"

LABEL_SEX = "Пол"
LABEL_BIRTH_DATE = "Дата рождения"
LABEL_HEIGHT = "Рост"

BTN_EDIT_SEX = "♂️♀️ Пол"
BTN_EDIT_BIRTH_DATE = "🎂 Дата рождения"
BTN_EDIT_HEIGHT = "📏 Рост"

SEX_UPDATED = "✅ Пол обновлён."
BIRTH_DATE_UPDATED = "✅ Дата рождения обновлена."
HEIGHT_UPDATED = "✅ Рост обновлён."

# --------------------------------------------------------------------------
# Goal card
# --------------------------------------------------------------------------

GOAL_TITLE = "🎯 <b>Цель</b>"
GOAL_EMPTY = "Цели пока нет. Поставим?"

BTN_NEW_GOAL = "🎯 Поставить цель"

LABEL_GOAL_TYPE = "Тип"
LABEL_START_WEIGHT = "Старт"
LABEL_TARGET_WEIGHT = "Цель"
LABEL_CURRENT_WEIGHT = "Сейчас"
LABEL_TARGET_DATE = "Срок"
LABEL_GOAL_PROGRESS = "Пройдено"
LABEL_GOAL_LEFT = "Осталось"

GOAL_SAVED = "✅ Цель сохранена."
GOAL_REACHED = "🏆 Цель достигнута!"
GOAL_NO_WEIGHT_YET = "Нет ни одного замера веса — добавь через /measure."


def goal_progress_line(done: str, span: str, pct: int) -> str:
    return f"{LABEL_GOAL_PROGRESS}: {done} из {span} ({pct}%)"


# --------------------------------------------------------------------------
# Measurements
# --------------------------------------------------------------------------

MEASURE_TITLE = "📏 <b>Замер</b>"

MEASURE_ALREADY_TODAY = (
    "Замер на сегодня уже есть, следующий замер можно сделать только завтра!"
    "\n\nВот что записано:"
)

ASK_MEASURE_WEIGHT = "Укажи свой текущий вес в килограммах (например, 82,5)."
ASK_CHEST = "Укажи обхват груди в сантиметрах (например, 90)"
ASK_WAIST = "Укажи обхват талии в сантиметрах (например, 70)"
ASK_HIPS = "Укажи обхват ягодиц в сантиметрах (например, 95)"
ASK_THIGH = "Укажи обхват одного бедра в сантиметрах (например, 55)"
ASK_ARM = "Укажи обхват руки в сантиметрах (например, 30)"

OFFER_BODY_MEASURE = (
    "Отлично! Записал текущий вес.\nХочешь замерить обхваты? "
    "Замеры помогут отслеживать прогресс даже если вес стоит на месте."
)

BTN_BODY_MEASURE = "📐 Да, хочу замерить"
BTN_MEASURE_SAVE = "➡️ Нет, сохраним только вес"

MEASURE_GUIDE = (
    "Для начала, небольшой гайд как правильно измерять обхваты:\n\n"
    "📏 Меряем сантиметровой лентой, ответ — число в сантиметрах "
    "(можно с дробной частью, например 27,5)\n\n"
    "Грудь — в самом широком месте, талию — в самом узком\n\n"
    "Ягодицы, бедро и руку — в самой широкой части\n\n"
    "❗️ Важно каждый раз мерить в одном и том же месте — так легче отследить прогресс\n\n"
    "❗️ Замеры желательно делать раз в неделю, утром и натощак"
)

MEASURE_REVIEW_HINT = "Проверь, всё ли верно, перед сохранением:"

BTN_MEASURE_CONFIRM = "✅ Всё верно, сохранить"
BTN_MEASURE_EDIT = "✏️ Изменить"

MEASURE_EDIT_PROMPT = "Что поправить?"

LABEL_WEIGHT = "Вес"
LABEL_WAIST = "Талия"
LABEL_CHEST = "Грудь"
LABEL_HIPS = "Ягодицы"
LABEL_THIGH = "Бедро"
LABEL_ARM = "Рука"

# Order mirrors the collection order (weight -> chest -> waist -> hips -> thigh -> arm)
# so the review card and the "what to fix" keyboard both read top-to-bottom consistently.
MEASURE_FIELDS: tuple[str, ...] = (
    "weight_kg",
    "chest_cm",
    "waist_cm",
    "hips_cm",
    "thigh_cm",
    "arm_cm",
)

MEASURE_FIELD_LABELS: dict[str, str] = {
    "weight_kg": LABEL_WEIGHT,
    "chest_cm": LABEL_CHEST,
    "waist_cm": LABEL_WAIST,
    "hips_cm": LABEL_HIPS,
    "thigh_cm": LABEL_THIGH,
    "arm_cm": LABEL_ARM,
}


def measure_field_label(value: str) -> str:
    return MEASURE_FIELD_LABELS.get(value, value)


MEASURE_SAVED = "✅ Ваши параметры:"
MEASURE_EMPTY = "Ни одного значения — записывать нечего."

# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

ERR_NUMBER = "Жду число — например, 82,5"
ERR_BIRTH_DATE_FUTURE = "Дата рождения не может быть в будущем."
ERR_USE_BUTTONS = "Выбери вариант кнопкой ниже 👇"


def _err_range(what: str, low: float, high: float, unit: str) -> str:
    return f"{what} — от {low:g} до {high:g} {unit}. Проверь значение."


def err_height_range(low: float, high: float) -> str:
    return _err_range("Рост бывает", low, high, UNIT_CM)


def err_weight_range(low: float, high: float) -> str:
    return _err_range("Вес бывает", low, high, UNIT_KG)


def err_measure_range(low: float, high: float) -> str:
    return _err_range("Обхват бывает", low, high, UNIT_CM)


def err_age_range(low: int, high: int) -> str:
    return f"Год рождения выглядит странно — жду возраст от {low} до {high} лет."
