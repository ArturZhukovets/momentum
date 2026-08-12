# Workout types with per-type field sets

## Idea

Replace binary `kind` (`cardio` | `strength`) with a real **workout type**. Each type owns an
ordered list of skippable fields the FSM asks when logging. Grow to ~10 types without
touching the FSM — only catalog + labels.

Types (DB values; Russian labels in `texts/`):
`running`, `swimming`, `elliptical`, `gym`, `home_workout`.

Field sets:


| type           | fields (in order)                              |
| -------------- | ---------------------------------------------- |
| `running`      | duration_min, distance_km, effort, description |
| `swimming`     | duration_min, distance_km, effort, description |
| `elliptical`   | duration_min, effort, description              |
| `gym`          | body_parts, description                        |
| `home_workout` | body_parts, duration_min, description          |




## 1. Database changes

- Rename `kind` → `workout_type` (TEXT, no DB CHECK; values are `Enum`/`Literal` in Python).
- Add `duration_min` (INT), `distance_km` (FLOAT), `effort` (TEXT). Keep `body_parts`,
`description`.
- Drop `photo_file_id` and the old `kind` CHECK.
- Backfill: `strength` → `gym`, `cardio` → `running`.
- Update ORM (`db/tables.py`) + frozen dataclasses (`db/models.py`);
`WorkoutPoint.kind` → `workout_type`; remove photo.
- `db/workouts.py`: accept/return new fields; still scoped by `user_id`.
- Alembic revision with working `downgrade()` (batch alter for SQLite).



## 2. Services and FSM changes

- New pure catalog `services/workout_types.py`: types, effort values, ordered field specs per
type. FSM field kinds: `int`, `float`, `choice`, `multi_choice`, `text`.
- FSM: `choosing_type` → `field_input` → `choosing_date` (field cursor in FSM data); walk the
catalog generically; no photo branch; keep `_prompts` + `SkipCB` step guard.
- Stats: replace cardio/strength split with per-type counts (e.g. `3 gym, 2 running, 2 swimming`).
Drop `_split_kinds`; update `WeeklyStats`/`MonthlyStats` and report builders.



## 3. Texts

- `texts/workout.py`: Russian label + emoji per type; per-field prompts and validation errors;
replace `KIND_TITLES`; strip photo prompts. `BODY_PART_LABELS` unchanged.
- `texts/reports.py`: wording for the per-type breakdown (drop cardio/strength labels if unused).



## 4. Others

- Keyboards: `KindCB` → `TypeCB (rename)`, add `ChoiceCB`; `type_kb()` + generic `choice_kb(field)`.
- Formatters: workout card/history show type + non-NULL fields (no photo); reports render
per-type counts (only types with count > 0).

