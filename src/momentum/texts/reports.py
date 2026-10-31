"""/week, /month, and the scheduled broadcast."""

from __future__ import annotations

from momentum.db.models import ReportKind
from momentum.texts.common import plural, weeks_word, workouts_word

WEEKLY_TITLE = "📊 <b>Отчёт за неделю</b>"
MONTHLY_TITLE = "🗓 <b>Отчёт за месяц</b>"
COACH_COMMENT_TITLE = "💬 <b>Комментарий тренера</b>"

# How a coach comment spells a unit right after a number, mapped to `guard` unit names:
# the guard matches that number only against facts in the same unit. Abbreviations
# match as whole words (so «см» is not «смена»), the long forms as stems.
COMMENT_UNIT_WORDS: dict[str, str] = {
    "кг": "kg",
    "кило": "kg",
    "см": "cm",
    "ккал": "kcal",
    "%": "pct",
}
COMMENT_UNIT_STEMS: dict[str, str] = {
    "килограмм": "kg",
    "сантиметр": "cm",
    "калори": "kcal",
    "процент": "pct",
}
# Stems of the words a comment spells a kg/cm change's direction with, a few words
# before the number («вес снизился на 0,4 кг»). The guard rejects a direction that
# contradicts the sign of the fact with that number. «больше»/«меньше» are left out:
# they compare («меньше плана») as often as they move.
COMMENT_DOWN_STEMS: tuple[str, ...] = (
    "сброс",
    "сбрасыва",
    "сниз",
    "сниж",
    "ушл",
    "ушёл",
    "ушел",
    "уход",
    "минус",
    "уменьш",
    "похуде",
    "потеря",
    "легче",
)
COMMENT_UP_STEMS: tuple[str, ...] = (
    "набра",
    "набир",
    "выро",
    "вырас",
    "прибав",
    "плюс",
    "увелич",
    "тяжелее",
)
# Number words (stems) the guard can't check against the facts, so a comment must use
# digits: «две тренировки», «три кг» are rejected. «один»/«одна» stay allowed — «ещё
# одна тренировка» is ordinary phrasing, not a count taken from the facts.
COMMENT_NUMBER_WORD_STEMS: tuple[str, ...] = (
    "полтор",
    "два",
    "две",
    "двух",
    "двум",
    "три",
    "трёх",
    "трех",
    "трём",
    "трем",
    "четыр",
    "пят",
    "шест",
    "семь",
    "семи",
    "семн",
    "восем",
    "восьм",
    "девят",
    "десят",
    "одиннадцат",
)
# Counted like a unit when it follows a number word.
COMMENT_WORKOUT_STEM = "тренировк"

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

_TONE_HOLDING: dict[ReportKind, str] = {
    "week": "✨ За неделю вес почти не сдвинулся — ровно то, что нужно, чтобы держать форму.",
    "month": "✨ За месяц вес почти не сдвинулся — ровно то, что нужно, чтобы держать форму.",
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


def tone_holding(kind: ReportKind) -> str:
    """Maintain goal: the weight stayed inside its band this period."""
    return _TONE_HOLDING[kind]


def tone_setback(kind: ReportKind) -> str:
    return _TONE_SETBACK[kind]


# Pace line — `actual`/`planned` are signed and formatted, in kg per month.


def pace_ahead(actual: str, planned: str) -> str:
    return f"🚀 Идёшь быстрее плана: {actual} кг в месяц при плане {planned} кг."


def pace_on_track(actual: str, planned: str) -> str:
    return f"✅ Идёшь в графике: {actual} кг в месяц при плане {planned} кг."


def pace_behind(actual: str, planned: str) -> str:
    return (
        f"🐢 Пока отстаёшь от плана: {actual} кг в месяц при плане {planned} кг. "
        "Это не провал — темп выравнивается, если держать режим."
    )


def pace_no_plan(actual: str) -> str:
    return f"🧭 Текущий темп: {actual} кг в месяц."


PACE_STALLED = (
    "⏸ Последние недели вес стоит на месте. "
    "Если так и дальше — стоит пересмотреть питание или нагрузку."
)


def pace_away(actual: str) -> str:
    return (
        f"↩️ Последние недели вес идёт в обратную от цели сторону: {actual} кг в месяц. "
        "Стоит пересмотреть питание или нагрузку."
    )


def pace_unsafe(actual: str) -> str:
    return (
        f"⚠️ Вес уходит слишком быстро: {actual} кг в месяц. "
        "Так уходят вода и мышцы, а не жир — стоит сбавить темп."
    )


PACE_HOLDING = "⚖️ Вес держится ровно — форма под контролем."


def pace_drifting(actual: str) -> str:
    return (
        f"⚖️ Вес смещается: {actual} кг в месяц. "
        "Стоит присмотреться к питанию и нагрузке, чтобы удержать форму."
    )


def pace_eta(line: str, eta: str) -> str:
    """Append the projected date (already formatted) to a pace sentence."""
    return f"{line} Если темп сохранится, цель — примерно к {eta}."


def no_measurements(kind: ReportKind) -> str:
    return _NO_MEASUREMENTS[kind]


# Energy block — kcal figures arrive rounded and formatted, `rate` signed in kg per
# month. «около»/«~» state a fact: MET and Mifflin both spread by a couple hundred kcal.

_ENERGY_PERIOD: dict[ReportKind, str] = {"week": "За неделю", "month": "За месяц"}
_COUNTED_WORKOUTS_PLURAL = (
    "записанной тренировке",
    "записанным тренировкам",
    "записанным тренировкам",
)
_UNTIMED_WORKOUTS_PLURAL = (
    "записанной тренировки",
    "записанных тренировок",
    "записанных тренировок",
)

# Accusative, in `energy.PROFILE_FIELDS` terms.
_PROFILE_FIELD_NAMES: dict[str, str] = {
    "birth_date": "дату рождения",
    "sex": "пол",
    "height_cm": "рост",
}


def energy_burn(daily_burn: str, from_workouts: str | None) -> str:
    if from_workouts is None:
        return f"🔥 Расход — около {daily_burn} ккал в день."
    return f"🔥 Расход — около {daily_burn} ккал в день, из них ~{from_workouts} дают тренировки."


def energy_target(rate: str, target: str) -> str:
    return f"🍽 Для {rate} кг в месяц ориентир по питанию — около {target} ккал в день."


def energy_target_maintain(target: str) -> str:
    return f"🍽 Чтобы вес держался, ориентир по питанию — около {target} ккал в день."


def energy_below_floor(rate: str) -> str:
    return (
        f"⚠️ При темпе {rate} кг в месяц норма питания получается слишком низкой, "
        "поэтому число не показываю."
    )


def energy_workouts(kind: ReportKind, kcal: str, counted: int, untimed: int) -> str:
    """Period burn over workouts with a duration; the untimed ones are named, not guessed."""
    basis = f"по {counted} {plural(counted, _COUNTED_WORKOUTS_PLURAL)}"
    if untimed:
        basis += f"; {untimed} {workouts_word(untimed)} без длительности не в счёт"
    return f"⚡ {_ENERGY_PERIOD[kind]} на тренировках ~{kcal} ккал ({basis})."


def energy_workouts_untimed(kind: ReportKind, untimed: int) -> str:
    return (
        f"⚡ {_ENERGY_PERIOD[kind]} расход на тренировках не посчитан: "
        f"у {untimed} {plural(untimed, _UNTIMED_WORKOUTS_PLURAL)} нет длительности."
    )


def profile_nudge(fields: tuple[str, ...]) -> str:
    """The one-time ask for the profile answers that hide the energy block."""
    names = [_PROFILE_FIELD_NAMES[field] for field in fields]
    listed = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} и {names[-1]}"
    return f"💡 Если указать в /profile {listed}, в отчёте появится расчёт калорий."
