"""Rendering of the read-only /show_measures screen (HTML parse mode)."""

from __future__ import annotations

from aiogram.utils.formatting import Bold, Pre, Text, as_list, as_section

from momentum.db.models import BodyMeasurement
from momentum.formatters.profile import fmt_number
from momentum.services.measurements import (
    FIELDS,
    FieldSnapshot,
    MeasurementField,
    MeasurementSnapshot,
)
from momentum.texts import common as texts_common
from momentum.texts import measurements as texts_measurements

RECENT_LIMIT = 7
TABLE_FIELDS: tuple[MeasurementField, ...] = (
    "weight_kg",
    "waist_cm",
    "chest_cm",
    "hips_cm",
    "thigh_cm",
)


def measures_screen(snapshot: MeasurementSnapshot, sessions: list[BodyMeasurement]) -> str:
    """Current per-field values, then a compact table of the newest sessions."""
    title = Text(texts_measurements.TITLE_EMOJI, " ", Bold(texts_measurements.TITLE))
    current_fields = [
        (field, value) for field in FIELDS if (value := getattr(snapshot, field)) is not None
    ]
    if not current_fields:
        return as_list(title, texts_measurements.EMPTY, sep="\n\n").as_html()

    blocks = [title, _current_values_section(current_fields)]
    recent_sessions = sessions[:RECENT_LIMIT]
    if recent_sessions:
        blocks.append(_recent_sessions_section(recent_sessions))
    return as_list(*blocks, sep="\n\n").as_html()


def _current_values_section(fields: list[tuple[MeasurementField, FieldSnapshot]]) -> Text:
    recorded_on_dates = {snap.recorded_on for _, snap in fields}
    shared_date = next(iter(recorded_on_dates)) if len(recorded_on_dates) == 1 else None
    heading = texts_measurements.snapshot_heading(
        texts_common.fmt_date_short(shared_date) if shared_date else None
    )
    lines = [
        _current_value_line(field, snap, show_date=shared_date is None) for field, snap in fields
    ]
    return as_section(Bold(heading), as_list(*lines))


def _current_value_line(field: MeasurementField, snap: FieldSnapshot, *, show_date: bool) -> str:
    label = texts_measurements.FIELD_LABELS[field]
    amount = f"{fmt_number(snap.value)} {texts_measurements.FIELD_UNITS[field]}"
    line = f"{label}: {amount}"
    if show_date:
        line += f" · {texts_common.fmt_date_short(snap.recorded_on)}"
    if snap.delta is not None and snap.previous_on is not None:
        line += " " + texts_measurements.delta_suffix(
            _signed_delta(snap.delta),
            texts_measurements.FIELD_UNITS[field],
            texts_common.fmt_date_short(snap.previous_on),
        )
    return line


def _signed_delta(value: float) -> str:
    formatted = fmt_number(abs(value))
    if value > 0:
        return f"+{formatted}"
    if value < 0:
        return f"−{formatted}"
    return formatted


def _recent_sessions_section(sessions: list[BodyMeasurement]) -> Text:
    rows = [list(texts_measurements.TABLE_HEADERS)]
    for session in sessions:
        row = [texts_common.fmt_date_short(session.recorded_on)]
        for field in TABLE_FIELDS:
            value: float | None = getattr(session, field)
            row.append(fmt_number(value) if value is not None else texts_measurements.CELL_EMPTY)
        rows.append(row)

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    table = "\n".join(
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows
    )
    return as_section(Bold(texts_measurements.RECENT_TITLE), Pre(table))
