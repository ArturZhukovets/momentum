"""Rendering of the profile card, the goal card with progress, and measurements."""

from __future__ import annotations

from datetime import date

from momentum.db.models import BodyMeasurement, UserGoal, UserProfile
from momentum.services import periods
from momentum.texts import common as texts_common
from momentum.texts import profile as texts_profile


def fmt_number(value: float) -> str:
    """82.5 -> '82,5', 82.0 -> '82' — one decimal at most, Russian comma."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _amount(value: float, unit: str) -> str:
    return f"{fmt_number(value)} {unit}"


def _kg(value: float) -> str:
    return _amount(value, texts_profile.UNIT_KG)


def _cm(value: float) -> str:
    return _amount(value, texts_profile.UNIT_CM)


def _line(label: str, value: str | None) -> str:
    return f"{label}: {value if value else texts_profile.VALUE_UNKNOWN}"


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------


def _age_suffix(birth_date: date, today: date) -> str:
    age = periods.years_since(birth_date, today)
    return f" ({age} {texts_common.years_word(age)})"


def profile_card(profile: UserProfile | None, today: date) -> str:
    sex = texts_profile.sex_label(profile.sex) if profile and profile.sex else None

    birth = None
    if profile and profile.birth_date:
        birth = texts_common.fmt_date(profile.birth_date) + _age_suffix(profile.birth_date, today)

    height = _cm(profile.height_cm) if profile and profile.height_cm else None

    lines = [
        texts_profile.PROFILE_TITLE,
        _line(texts_profile.LABEL_SEX, sex),
        _line(texts_profile.LABEL_BIRTH_DATE, birth),
        _line(texts_profile.LABEL_HEIGHT, height),
    ]
    if not (sex or birth or height):
        lines.append(f"\n{texts_profile.PROFILE_EMPTY_HINT}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Goal
# --------------------------------------------------------------------------


def _progress_lines(goal: UserGoal, current_weight_kg: float | None) -> list[str]:
    """Start -> current -> target, plus how much of the span is behind us.

    Rendered only when all three weights are known and the span is non-zero;
    otherwise there is no meaningful percentage to show.
    """
    start, target = goal.start_weight_kg, goal.target_weight_kg
    if current_weight_kg is None or start is None or target is None or start == target:
        return []

    span = abs(target - start)
    done = abs(current_weight_kg - start)
    left = abs(target - current_weight_kg)
    overshot = (current_weight_kg - start) * (target - start) < 0

    if left == 0:
        return [texts_profile.GOAL_REACHED]

    # Walking away from the target reads as 0%, not as negative progress.
    pct = 0 if overshot else min(round(done / span * 100), 100)
    return [
        texts_profile.goal_progress_line(fmt_number(0 if overshot else done), _kg(span), pct),
        f"{texts_profile.LABEL_GOAL_LEFT}: {_kg(left)}",
    ]


def goal_card(goal: UserGoal, current_weight_kg: float | None) -> str:
    lines = [
        texts_profile.GOAL_TITLE,
        f"{texts_profile.LABEL_GOAL_TYPE}: {texts_profile.goal_type_label(goal.goal_type)}",
    ]

    if goal.start_weight_kg is not None:
        lines.append(f"{texts_profile.LABEL_START_WEIGHT}: {_kg(goal.start_weight_kg)}")
    if goal.target_weight_kg is not None:
        lines.append(f"{texts_profile.LABEL_TARGET_WEIGHT}: {_kg(goal.target_weight_kg)}")
    if goal.target_date is not None:
        lines.append(
            f"{texts_profile.LABEL_TARGET_DATE}: {texts_common.fmt_date(goal.target_date)}"
        )

    if current_weight_kg is None:
        lines.append(f"\n{texts_profile.GOAL_NO_WEIGHT_YET}")
        return "\n".join(lines)

    lines.append(f"{texts_profile.LABEL_CURRENT_WEIGHT}: {_kg(current_weight_kg)}")

    progress = _progress_lines(goal, current_weight_kg)
    if progress:
        lines.append("")
        lines.extend(progress)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------


def measurement_card(measurement: BodyMeasurement) -> str:
    lines = [
        f"{texts_profile.MEASURE_TITLE} — {texts_common.fmt_date(measurement.recorded_on)}",
    ]
    if measurement.weight_kg is not None:
        lines.append(f"{texts_profile.LABEL_WEIGHT}: {_kg(measurement.weight_kg)}")

    circumferences = (
        (texts_profile.LABEL_WAIST, measurement.waist_cm),
        (texts_profile.LABEL_CHEST, measurement.chest_cm),
        (texts_profile.LABEL_HIPS, measurement.hips_cm),
        (texts_profile.LABEL_THIGH, measurement.thigh_cm),
        (texts_profile.LABEL_ARM, measurement.arm_cm),
    )
    lines.extend(f"{label}: {_cm(value)}" for label, value in circumferences if value is not None)
    return "\n".join(lines)
