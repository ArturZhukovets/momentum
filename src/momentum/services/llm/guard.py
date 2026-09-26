"""Deterministic check of a model-written comment: every number in it must come from the facts.

Pure. The facts are already rounded the way the report prints them, so a number
passes when it equals a fact up to sign (the text carries the direction in words)
or is that fact rounded to a whole number. «0,4» and «0.4» are the same number.
A number followed by a unit (``kg``, ``cm``, ``kcal``, ``pct``) must match a fact
in that unit — a unit is read off the fact's key — so a workout count can't
vouch for kilograms. Dates pass only as ``DD.MM`` / ``DD.MM.YYYY`` of a fact date.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from momentum.texts.reports import COMMENT_UNIT_STEMS, COMMENT_UNIT_WORDS

# 2–4 sentences fit comfortably; anything longer ignored the prompt or ran on.
MAX_COMMENT_CHARS = 700

# Thousands grouped by a (narrow/no-break) space first — «2 150» — then plain «0,4», «15.11.2026»;
# the word right after it, if any, may be its unit.
_NUMBER = re.compile(
    r"(?P<number>\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?(?!\d)|\d+(?:[.,]\d+)*)"
    r"\s?(?P<word>%|[^\W\d_]+)?"
)
_SEPARATOR = re.compile(r"[.,]")


@dataclass
class _Allowed:
    """Fact magnitudes by unit (``None`` — unitless counts); dates as (day, month[, year])."""

    numbers: defaultdict[str | None, set[float]] = field(default_factory=lambda: defaultdict(set))
    wholes: defaultdict[str | None, set[int]] = field(default_factory=lambda: defaultdict(set))
    dates: set[tuple[int, ...]] = field(default_factory=set)


def problems(comment: str | None, facts: Mapping[str, Any]) -> list[str]:
    """Why ``comment`` can't go out — empty when it passes. ``facts`` is what the model saw."""
    if not comment:
        return ["empty"]
    found: list[str] = []
    if len(comment) > MAX_COMMENT_CHARS:
        found.append(f"too long: {len(comment)} chars, at most {MAX_COMMENT_CHARS}")
    unsupported = unsupported_numbers(comment, facts)
    if unsupported:
        found.append(f"numbers not in the facts: {'; '.join(unsupported)}")
    return found


def unsupported_numbers(text: str, facts: Mapping[str, Any]) -> list[str]:
    allowed = _Allowed()
    _collect(facts, None, allowed)
    return [
        match.group(0).strip()
        for match in _NUMBER.finditer(text)
        if not _supported(match["number"], _unit(match["word"]), allowed)
    ]


def _collect(value: Any, unit: str | None, allowed: _Allowed) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _collect(item, _unit_of(str(key)) or unit, allowed)
    elif isinstance(value, date):
        allowed.dates.update({(value.day, value.month), (value.day, value.month, value.year)})
    elif isinstance(value, int | float):
        magnitude = abs(value)
        allowed.numbers[unit].add(round(magnitude, 1))
        # Both neighbours of an exact half: «2,5» may honestly become «2» or «3».
        allowed.wholes[unit].update({math.floor(magnitude + 0.5), math.ceil(magnitude - 0.5)})


def _unit_of(key: str) -> str | None:
    """The unit a fact key carries: ``pct``, ``*kcal*``, ``*_cm``, ``*kg*`` — else none."""
    if key == "pct":
        return "pct"
    if "kcal" in key:
        return "kcal"
    if key.endswith("_cm"):
        return "cm"
    if "kg" in key:
        return "kg"
    return None


def _unit(word: str | None) -> str | None:
    if word is None:
        return None
    word = word.lower()
    if word in COMMENT_UNIT_WORDS:
        return COMMENT_UNIT_WORDS[word]
    return next((unit for stem, unit in COMMENT_UNIT_STEMS.items() if word.startswith(stem)), None)


def _supported(number: str, unit: str | None, allowed: _Allowed) -> bool:
    parts = _SEPARATOR.split("".join(number.split()))
    if unit is None and "." in number and _as_date(parts) in allowed.dates:
        return True
    if len(parts) > 2:
        return False
    value = float(".".join(parts))
    pools = [unit] if unit is not None else list(allowed.numbers)
    return any(
        round(value, 1) in allowed.numbers[pool]
        or (value.is_integer() and int(value) in allowed.wholes[pool])
        for pool in pools
    )


def _as_date(parts: list[str]) -> tuple[int, ...] | None:
    """``["15", "11"]`` → ``(15, 11)``, ``["15", "11", "26"]`` → ``(15, 11, 2026)``."""
    if len(parts) not in (2, 3) or len(parts[0]) > 2 or len(parts[1]) != 2:
        return None
    day, month = int(parts[0]), int(parts[1])
    if len(parts) == 2:
        return day, month
    year = int(parts[2])
    return day, month, year + 2000 if year < 100 else year
