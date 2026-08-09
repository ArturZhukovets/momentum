# Workout types with per-type field sets

## Idea
Replace the binary `kind` (`cardio` | `strength`) with a real **workout type**, and let each
type define its own set of questions the bot asks when logging.

Types for now (English DB values, Russian labels in `texts/`):
`running`, `swimming`, `elliptical`, `gym`, `home_workout` — designed to grow to ~10 without
touching the FSM.

Each type owns an ordered list of fields. `gym` asks body parts + description; `running` asks
duration, distance and effort. Every field beyond the type itself stays skippable.

## Key design decisions
1. **`workouts.kind` → `workouts.workout_type`.** Not `type` — it shadows the Python builtin
   in the dataclass/kwargs. A plain column with a CHECK constraint, **not** a lookup table:
   the per-type field specs live in Python anyway, so a table would be a second source of
   truth plus a join, and would still not describe the flow.
2. **Category is derived, not stored.** Weekly/monthly stats split cardio vs strength
   (`services/stats._split_kinds`). Keep that working by mapping type → category in the
   catalog, not by adding a second column.
3. **A type catalog drives the FSM.** One registry declares, per type, its ordered field
   specs; the add-workout FSM walks that list generically instead of hardcoding a
   cardio/strength branch. Adding type #6…#10 = one catalog entry + one small Alembic
   revision widening the CHECK.
4. **Per-type values are typed nullable columns on `workouts`**, not a key/value table. The
   whole field vocabulary is four columns shared across types — see below.

## Storage: why columns, not a key/value table
The field vocabulary is small and closed: `duration_min`, `distance_m`, `effort`, `avg_hr`.
Different types ask for different subsets, but they are the *same* four fields. Four nullable
columns beat an EAV table on every axis that matters here — values stay typed and
CHECK-constrained, and "total distance this month" is `SUM(distance_m)` instead of a
`CAST` over text rows. The catalog decides which columns a given type asks about; unasked
columns stay NULL.

`distance_m` in metres for both running and swimming — one column, formatted as km for
running at display time.

Body parts keep their existing `workout_body_parts` tag table (genuinely many-per-workout).

An EAV table would only win if the field set became large, sparse, or user-defined. If that
happens later, add `workout_attributes(workout_id, key, value)` then — it composes fine
alongside the typed columns.

## Proposed field sets
| type | fields (in order) |
|---|---|
| `running` | duration_min, distance_m, effort, description, photo |
| `swimming` | duration_min, distance_m, effort, description |
| `elliptical` | duration_min, effort, description |
| `gym` | body_parts, description |
| `home_workout` | body_parts, duration_min, description |

Field kinds the FSM must render: `int`, `choice` (effort: лёгкая / средняя / высокая),
`multi_choice` (body parts, exists), `text`, `photo`.

`effort` is a 3-button perceived-intensity pick rather than a pulse number: no watch, no
typing. `avg_hr` stays available as an extra optional `int` field for types where a heart-rate
monitor is actually worn — added to a type's list, not replacing `effort`.

## Plan
1. **Alembic revision** — rename `kind` → `workout_type` with the new CHECK; add
   `duration_min`, `distance_m`, `avg_hr` (INTEGER NULL) and `effort` (TEXT NULL, CHECK).
   SQLite needs `op.batch_alter_table` for the rename and the CHECK change (Alembic rebuilds
   the table). Backfill in the same revision — see the open question below. Write a working
   `downgrade()`.
2. **ORM models** — update the `Workout` model with the renamed + new columns; keep the
   frozen dataclasses at the `db/` boundary if that split survives the SQLAlchemy move.
   `WorkoutPoint.kind` → `workout_type`.
3. **Type catalog** — new pure module (e.g. `services/workout_types.py`): type values,
   type → category, and the ordered field specs per type. No aiogram/DB imports, so it stays
   importable from texts/keyboards/formatters and testable on its own.
4. **Texts** — `texts/workout.py`: Russian label + emoji per type, per-field prompts and
   validation errors; replace `KIND_TITLES`; `BODY_PART_LABELS` unchanged.
5. **DB layer** — `db/workouts.py`: `add_workout` takes the new fields; reads populate them.
   Keep every user-owned query scoped by `user_id`.
6. **FSM** — `states.AddWorkout`: replace the cardio/strength branches with generic
   `choosing_type` → `field_input` → `choosing_date`, driven by a field cursor in FSM data.
   `handlers/add_workout.py` renders the current field spec via the `_prompts` helpers and
   advances; keep `drop_prompt_kb` and the `SkipCB`-carries-its-step guard.
7. **Keyboards** — `callbacks.py`: `KindCB` → `TypeCB`, add `ChoiceCB` for `choice` fields.
   `keyboards/workout.py`: `type_kb()` over the catalog, generic `choice_kb(field)`.
8. **Formatters** — card renders the type title then one line per non-NULL field;
   `history_row_label` uses the type icon + short label.
9. **Stats** — `services/stats.py`: `_split_kinds` splits via the catalog's category map.
   Report copy unchanged.

## Acceptance criteria
- [ ] `/add` offers the five types; each asks exactly its own fields, all skippable.
- [ ] Saved card and `/history` rows show the type and every entered field.
- [ ] `/week` and `/month` cardio/strength counts still work, now via the category map.
- [ ] `alembic upgrade head` migrates an existing DB; old workouts open and render fine.
- [ ] `alembic downgrade -1` restores the previous schema without data loss beyond the new
      columns.
- [ ] Adding a sixth type = catalog entry + labels + a CHECK-widening revision, nothing else.

## Open questions
- **Backfill for existing rows.** `strength` → `gym` is safe. `cardio` → ? Old rows don't
  record which cardio it was. Either add an `other` type as the landing bucket, or pick
  `running` if that's what the history actually is. Blocks step 1.
- Whether to keep the cardio photo step now that types carry richer data.

## Effort
M (2–4h), assuming SQLAlchemy + Alembic are already in place. The FSM rewrite is the bulk;
the catalog makes steps 4–9 mechanical.
