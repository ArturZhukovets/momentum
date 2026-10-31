"""Deterministic check of a model-written comment against the facts it was shown.

Pure. The facts are already rounded the way the report prints them, so a number
passes when it equals a fact up to sign (the text carries the direction in words)
or is that fact rounded to a whole number. «0,4» and «0.4» are the same number.
A number followed by a unit (``kg``, ``cm``, ``kcal``, ``pct``) must match a fact
in that unit — a unit is read off the fact's key — so a workout count can't
vouch for kilograms. Dates pass only as ``DD.MM`` / ``DD.MM.YYYY`` of a fact date.

A direction word a few words before a kg or cm number has to agree with the sign
of the fact that number cites: «снизился» against a gain does not. Number words
(«три», «две») do not pass — the facts can't vouch for them. «один» and «одна»
are not in that list.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from momentum.texts.reports import (
    COMMENT_DOWN_STEMS,
    COMMENT_NUMBER_WORD_STEMS,
    COMMENT_UNIT_STEMS,
    COMMENT_UNIT_WORDS,
    COMMENT_UP_STEMS,
)

# 2–4 sentences fit comfortably; anything longer ignored the prompt or ran on.
MAX_COMMENT_CHARS = 700

# «вес снизился на 0,4 кг»: the direction word sits a few words before the number.
# The closest stem is the one about this number, not an earlier clause.
_DIRECTION_WORDS = 5

_WORD = re.compile(r"[^\W\d_]+")

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
    # Sign (+1 / -1 / 0) of each kg/cm magnitude. Several facts can share one.
    signs: defaultdict[str, defaultdict[float, set[int]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(set))
    )
    whole_signs: defaultdict[str, defaultdict[int, set[int]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(set))
    )


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
    contradictions = direction_contradictions(comment, facts)
    if contradictions:
        found.append(f"direction contradicts the facts: {'; '.join(contradictions)}")
    spelled = spelled_number_words(comment)
    if spelled:
        found.append(f"numbers spelled as words: {', '.join(spelled)}")
    return found


def unsupported_numbers(text: str, facts: Mapping[str, Any]) -> list[str]:
    allowed = _Allowed()
    _collect(facts, None, allowed)
    return [
        match.group(0).strip()
        for match in _NUMBER.finditer(text)
        if not _supported(match["number"], _unit(match["word"]), allowed)
    ]


def direction_contradictions(text: str, facts: Mapping[str, Any]) -> list[str]:
    """Kg/cm phrases whose direction word agrees with none of the facts of that number.

    Only a stem within a few words before the number counts, and only the closest
    one — an earlier clause is about an earlier number. No stem, no claim.
    «больше» and «меньше» are not stems. A number the facts don't contain is left
    to ``unsupported_numbers``.
    """
    allowed = _Allowed()
    _collect(facts, None, allowed)
    found: list[str] = []
    for match in _NUMBER.finditer(text):
        unit = _unit(match["word"])
        if unit not in ("kg", "cm"):
            continue
        directed = _closest_direction(_words_before(text, match.start()))
        if directed is None:
            continue
        word, sign = directed
        fact_signs = _fact_signs(match["number"], unit, allowed)
        if fact_signs is None or sign in fact_signs:
            continue
        found.append(f"{word} {match.group(0).strip()}")
    return found


def spelled_number_words(text: str) -> list[str]:
    """Number-word stems in ``text``.

    A stem anywhere fails, including before ``тренировк`` («три тренировки»).
    «один» and «одна» are not stems.
    """
    found: list[str] = []
    seen: set[str] = set()
    for match in _WORD.finditer(text.lower()):
        word = match.group(0)
        if word in seen or not _is_number_word(word):
            continue
        seen.add(word)
        found.append(word)
    return found


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
        rounded = round(magnitude, 1)
        allowed.numbers[unit].add(rounded)
        # Both neighbours of an exact half: «2,5» may honestly become «2» or «3».
        wholes = {math.floor(magnitude + 0.5), math.ceil(magnitude - 0.5)}
        allowed.wholes[unit].update(wholes)
        if unit in ("kg", "cm"):
            sign = _sign(value)
            allowed.signs[unit][rounded].add(sign)
            for whole in wholes:
                allowed.whole_signs[unit][whole].add(sign)


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


def _words_before(text: str, end: int) -> list[str]:
    return [match.group(0).lower() for match in _WORD.finditer(text[:end])][-_DIRECTION_WORDS:]


def _closest_direction(words: list[str]) -> tuple[str, int] | None:
    """The direction stem nearest the number, as ``(word, sign)``. Down is -1."""
    for word in reversed(words):
        if any(word.startswith(stem) for stem in COMMENT_DOWN_STEMS):
            return word, -1
        if any(word.startswith(stem) for stem in COMMENT_UP_STEMS):
            return word, 1
    return None


def _fact_signs(number: str, unit: str, allowed: _Allowed) -> set[int] | None:
    """Signs of the kg/cm facts ``number`` may cite, or None when it cites none."""
    parts = _SEPARATOR.split("".join(number.split()))
    if len(parts) > 2:
        return None
    value = float(".".join(parts))
    signs: set[int] = set()
    matched = False
    rounded = round(value, 1)
    if rounded in allowed.numbers[unit]:
        matched = True
        signs |= allowed.signs[unit][rounded]
    if value.is_integer() and int(value) in allowed.wholes[unit]:
        matched = True
        signs |= allowed.whole_signs[unit][int(value)]
    return signs if matched else None


def _is_number_word(word: str) -> bool:
    return any(word.startswith(stem) for stem in COMMENT_NUMBER_WORD_STEMS)


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _as_date(parts: list[str]) -> tuple[int, ...] | None:
    """``["15", "11"]`` → ``(15, 11)``, ``["15", "11", "26"]`` → ``(15, 11, 2026)``."""
    if len(parts) not in (2, 3) or len(parts[0]) > 2 or len(parts[1]) != 2:
        return None
    day, month = int(parts[0]), int(parts[1])
    if len(parts) == 2:
        return day, month
    year = int(parts[2])
    return day, month, year + 2000 if year < 100 else year
