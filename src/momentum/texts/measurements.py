"""Read-only /show_measures screen: current snapshot plus recent sessions."""

from __future__ import annotations

TITLE_EMOJI = "📏"
TITLE = "Замеры"
EMPTY = "Пока нет ни одного замера — запиши через /measure."

SNAPSHOT_TITLE = "Актуальные"
RECENT_TITLE = "Последние замеры"

UNIT_KG = "кг"
UNIT_CM = "см"

CELL_EMPTY = "—"

LABEL_DATE = "Дата"
LABEL_WEIGHT = "Вес"
LABEL_WAIST = "Талия"
LABEL_CHEST = "Грудь"
LABEL_HIPS = "Ягодицы"
LABEL_THIGH = "Бедро"
LABEL_ARM = "Рука"

FIELD_LABELS: dict[str, str] = {
    "weight_kg": LABEL_WEIGHT,
    "waist_cm": LABEL_WAIST,
    "chest_cm": LABEL_CHEST,
    "hips_cm": LABEL_HIPS,
    "thigh_cm": LABEL_THIGH,
    "arm_cm": LABEL_ARM,
}

FIELD_UNITS: dict[str, str] = {
    "weight_kg": UNIT_KG,
    "waist_cm": UNIT_CM,
    "chest_cm": UNIT_CM,
    "hips_cm": UNIT_CM,
    "thigh_cm": UNIT_CM,
    "arm_cm": UNIT_CM,
}

TABLE_HEADERS: tuple[str, ...] = (
    LABEL_DATE,
    LABEL_WEIGHT,
    LABEL_WAIST,
    LABEL_CHEST,
    LABEL_HIPS,
    LABEL_THIGH,
)


def snapshot_heading(when: str | None) -> str:
    if when is None:
        return SNAPSHOT_TITLE
    return f"{SNAPSHOT_TITLE} — {when}"


def delta_suffix(delta: str, unit: str, previous_on: str) -> str:
    return f"({delta} {unit} с {previous_on})"
