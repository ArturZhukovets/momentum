# Add optional cardio metrics (duration, steps, calories)

## Idea
> Виды кардио:
> Бег, ходьба, эллипсоид
> Или пропустить этот шаг с добавлением вида (вести только тем кому интересно)
>
> Вводить количество минут, шагов и потраченных калорий (или пропустить этот шаг (оставить
> только выбранный вид кардио, если нечем отследить это))

("Cardio types: running, walking, elliptical — or skip that step (only for people who care
to tag it). Enter minutes, steps and calories burned — or skip that step too (keep just the
chosen cardio type if there's nothing to track it with).") Two asks in one idea: (1) tag a
cardio workout with a type, (2) optionally log duration/steps/calories for it.

## Verdict
Relevant: yes.
Already implemented: partly. The cardio-type half of this idea is **already fully specced**
in `docs/tasks/001-dobavit-vidy-kardio-tipa-beg-plavanie-ellipsoid.md` (not yet built — no
`cardio_type` anywhere in `src/momentum/db/schema.sql` today). This plan does not repeat
that spec; it covers only the second half — minutes/steps/calories — which has no existing
plan or code anywhere (no duration/steps/calories column, state, or text in the codebase).
Feasible: yes, with the same additive "optional 1:1 tag table" pattern task 001 already uses
for `workout_cardio_type`, keeping `schema.sql` idempotent and the existing `workouts` table
untouched.

## Current state
- `src/momentum/db/schema.sql` — `workouts` has `kind`, `performed_on`, `description`,
  `photo_file_id`, `created_at`; no numeric metrics of any kind. `workout_body_parts` is the
  existing pattern for an optional per-workout tag table (composite PK, `ON DELETE CASCADE`).
- `src/momentum/states.py` — `AddWorkout`: `choosing_kind` → (cardio) `cardio_photo` →
  `cardio_description`, or (strength) `strength_parts` → `strength_description` → both join
  at `choosing_date` → `custom_date`. No metrics step exists.
- `src/momentum/handlers/add_workout.py` — `cardio_photo()` / `cardio_photo_skip()` both call
  `_ask_description()` directly after the photo step; that is the insertion point for a new
  metrics step. `_finish()` reads all FSM data and calls `db_workouts.add_workout(...)`.
- `src/momentum/db/workouts.py` — `add_workout()` inserts the workout row then, if
  `body_parts`, batch-inserts into `workout_body_parts` in the same call. `get_workout()` and
  `list_workouts()` each fetch and attach `body_parts` after loading the base row(s) — the
  pattern a metrics table would mirror.
- `src/momentum/db/models.py` — `Workout` is a frozen dataclass with `body_parts: tuple[str,
  ...] = ()` as its only "extra" field; no numeric metrics field.
- `src/momentum/texts/workout.py` — `ASK_DESCRIPTION = "Опиши тренировку (или пропусти)."` is
  the closest existing prompt: free text, single skip button, no separate per-field skip.
- `src/momentum/keyboards/workout.py` — `skip_cancel_kb()` is the existing single-button-skip
  keyboard (Skip + Cancel), already used for both the photo and description steps.
- `src/momentum/formatters/workout.py` — `workout_card()` renders kind title, date, body
  parts (if any), description — the place a new metrics line belongs.
- `src/momentum/handlers/history.py` — post-save editing only covers `WorkoutCB` `desc` and
  `date`; body parts have no edit path. There is no precedent for editing tag-table data
  after save.

## Implementation plan
1. **`src/momentum/db/schema.sql`** — add a new 1:1 optional tag table, following the
   `workout_cardio_type` shape from task 001 but with three nullable numeric columns instead
   of one enum:
   ```sql
   CREATE TABLE IF NOT EXISTS workout_cardio_metrics (
       workout_id   INTEGER PRIMARY KEY REFERENCES workouts(id) ON DELETE CASCADE,
       duration_min INTEGER CHECK (duration_min IS NULL OR duration_min > 0),
       steps        INTEGER CHECK (steps IS NULL OR steps > 0),
       calories     INTEGER CHECK (calories IS NULL OR calories > 0)
   );
   ```
   `CREATE TABLE IF NOT EXISTS` keeps re-applying safe on every boot, per `CLAUDE.md`. A row
   is written only when at least one metric was captured — matching the "skip = no row" idea
   already used for `workout_body_parts` and (planned) `workout_cardio_type`.

2. **`src/momentum/services/cardio_metrics.py`** (new, pure — no aiogram/DB imports, mirrors
   `services/periods.py`) — a small free-text parser:
   ```python
   @dataclass(frozen=True)
   class CardioMetrics:
       duration_min: int | None = None
       steps: int | None = None
       calories: int | None = None

       def is_empty(self) -> bool:
           return self.duration_min is None and self.steps is None and self.calories is None

   def parse_cardio_metrics(text: str) -> CardioMetrics: ...
   ```
   `parse_cardio_metrics` extracts up to three integers from free text using order-independent
   regexes keyed by Russian unit words/abbreviations, e.g. `\d+\s*мин`, `\d+\s*шаг`, `\d+\s*
   ккал` (case-insensitive, tolerant of "минут"/"минуты"/"мин", "шагов"/"шаги"/"шаг",
   "ккал"/"калори[йяи]"). A number with no recognized unit is ignored rather than guessed —
   simplest rule that avoids silently misreading which field is which. If nothing matches,
   returns an all-`None` `CardioMetrics` (`is_empty()` true) rather than raising, so unparsable
   text degrades to "no metrics" instead of blocking the flow.

3. **`src/momentum/db/models.py`** — add `duration_min: int | None = None`, `steps: int |
   None = None`, `calories: int | None = None` to the `Workout` dataclass, after `body_parts`
   (and after `cardio_type` if task 001 lands first).

4. **`src/momentum/db/workouts.py`**:
   - `add_workout()`: add a `cardio_metrics: CardioMetrics | None = None` kwarg (import from
     `momentum.services.cardio_metrics`). After inserting the workout row, if `cardio_metrics`
     is given and not `cardio_metrics.is_empty()`, `INSERT INTO workout_cardio_metrics
     (workout_id, duration_min, steps, calories) VALUES (?, ?, ?, ?)`.
   - `_workout_from_row()`: add `duration_min`, `steps`, `calories` parameters (each
     `int | None = None`), pass through to `Workout(...)`.
   - `get_workout()`: after the existing `body_parts` fetch, `SELECT duration_min, steps,
     calories FROM workout_cardio_metrics WHERE workout_id = ?`; pass the row's values (or all
     `None` if no row) into `_workout_from_row`.
   - `list_workouts()`: after the existing `workout_body_parts` batch query, add a matching
     batch query `SELECT workout_id, duration_min, steps, calories FROM
     workout_cardio_metrics WHERE workout_id IN (...)` over the same `ids`, build a `dict[int,
     tuple[int | None, int | None, int | None]]`, and pass the three values into
     `_workout_from_row` per row (default all-`None` when absent).

5. **`src/momentum/states.py`** — add `cardio_metrics = State()` to `AddWorkout`, between
   `cardio_photo` and `cardio_description`.

6. **`src/momentum/texts/workout.py`** — add near `ASK_DESCRIPTION`:
   - `ASK_CARDIO_METRICS` — asks for minutes/steps/calories in one free-text message, any
     subset, in any order, with a short example so the parser's expected units are clear.
   - A short cardio-metrics line builder, e.g. `cardio_metrics_line(workout) -> str | None`,
     returning `None` when all three are absent, else something like `"⏱ 30 мин · 👣 5000
     шагов · 🔥 250 ккал"` built from whichever fields are set (omit absent ones, join with
     " · ").

7. **`src/momentum/handlers/add_workout.py`**:
   - Change `cardio_photo()` and `cardio_photo_skip()` to call a new `_ask_cardio_metrics(bot,
     chat_id, state)` instead of `_ask_description()` directly. `_ask_cardio_metrics()` sets
     `AddWorkout.cardio_metrics` and `send_prompt(..., texts_workout.ASK_CARDIO_METRICS,
     kb_workout.skip_cancel_kb())` — reusing the existing skip/cancel keyboard, no new
     keyboard builder needed.
   - New handler `cardio_metrics_text(message, state, bot)` on `AddWorkout.cardio_metrics +
     F.text`: `drop_prompt_kb`, run `parse_cardio_metrics(message.text)`, `state.update_data
     (cardio_metrics=parsed)` (aiogram's `MemoryStorage` keeps the dataclass instance as-is in
     the in-process dict), then call `_ask_description(bot, message.chat.id, state)`.
   - New handler `cardio_metrics_invalid(message)` on `AddWorkout.cardio_metrics` (no
     `F.text`) mirroring `description_invalid`: replies `texts_common.ERR_TEXT_EXPECTED`,
     state unchanged — catches a stray photo/sticker while this step is active.
   - New handler `cardio_metrics_skip(callback, state, bot)` on `AddWorkout.cardio_metrics +
     ActionCB.filter(F.name == "skip")` mirroring `skip_description`: clears the keyboard,
     does **not** set `cardio_metrics` in FSM data (absent key ⇒ `None` ⇒ no row later), calls
     `_ask_description`.
   - `_finish()`: read `cardio_metrics = data.get("cardio_metrics") if kind == "cardio" else
     None` and pass it to `db_workouts.add_workout(...)`.

8. **`src/momentum/formatters/workout.py`** — `workout_card()`: after the body-parts line (and
   after the cardio-type line, if task 001 has landed), if `texts_workout.cardio_metrics_line
   (workout)` is not `None`, append it as its own line, before the description line.

9. Do **not** add metrics editing to `handlers/history.py` — body parts (and, per task 001,
   cardio type) have no post-save edit path either; metrics follow the same precedent: set
   once at creation, immutable afterwards.

## Data & schema changes
New table `workout_cardio_metrics(workout_id INTEGER PRIMARY KEY REFERENCES workouts(id) ON
DELETE CASCADE, duration_min INTEGER CHECK(...), steps INTEGER CHECK(...), calories INTEGER
CHECK(...))` in `src/momentum/db/schema.sql`, added via `CREATE TABLE IF NOT EXISTS` so
re-applying on every boot stays safe. No changes to the existing `workouts` table or any
other table.

## User-facing copy
`src/momentum/texts/workout.py` needs:
- `ASK_CARDIO_METRICS` — a prompt like "Сколько минут, шагов и калорий? Пиши в любом порядке
  и составе, например: 30 мин, 5000 шагов, 250 ккал (или пропусти)." — must make clear any
  subset is fine (a user with only a step counter should be able to type just steps).
- The metrics line built by `cardio_metrics_line()` — Russian labels for minutes/steps/
  calories with distinct icons (e.g. ⏱ / 👣 / 🔥) so it reads as a compact single line in the
  workout card, distinct from the 🎯 body-parts line and any 🏷 cardio-type line from task 001.

## Acceptance criteria
- [ ] `/add` → "🏃 Кардио" → photo step (or its skip) now leads to a "Сколько минут, шагов и
      калорий?" prompt with Skip + Cancel buttons.
- [ ] Typing e.g. "30 мин, 5000 шагов" saves duration and steps, leaves calories unset, and
      moves on to the description step exactly as before.
- [ ] Typing only one metric (e.g. "250 ккал") saves only that one.
- [ ] Pressing Skip saves the workout with no `workout_cardio_metrics` row at all — identical
      behaviour to today, no metrics line on the card.
- [ ] Typing text with no recognizable unit (e.g. "не знаю") does not error and does not block
      the flow — it behaves like skip (no metrics saved) and moves on to description.
- [ ] The saved workout's detail card (`/history` → open) shows the metrics line only when at
      least one metric is present, formatted as e.g. "⏱ 30 мин · 👣 5000 шагов".
- [ ] Strength-workout flow is completely untouched: no metrics prompt appears, body-parts
      flow unaffected.
- [ ] Old workouts saved before this change still open and render fine (no
      `workout_cardio_metrics` row for them → card just omits the line).
- [ ] `sqlite3 data/momentum.db ".schema workout_cardio_metrics"` shows the new table after a
      restart; running `uv run python -m momentum` a second time does not error.

## Additional suggestions
- Keep this plan independent of task 001's cardio-type step in build order: if both land, the
  natural flow is `choosing_kind → cardio_type → cardio_photo → cardio_metrics →
  cardio_description → choosing_date`; nothing here depends on `cardio_type` existing, since
  the new step is only inserted relative to `cardio_photo`/`cardio_description`.
- Consider skipping the metrics step's own prompt entirely and only asking for it once the
  user has answered "yes I track this" at least once before (e.g. remember whether their last
  few cardio workouts had metrics) — left out here to keep the change additive and stateless,
  but worth a follow-up if the extra tap annoys users who never track metrics.
- A single free-text step (chosen here) is simpler than three sequential skippable prompts
  (one per metric) and matches the idea's wording ("пропустить этот шаг", singular). The
  trade-off: a user must remember the expected units/format instead of being walked through
  each field. If real usage shows people struggle with the free-text format, three short
  `SkipCB`-style prompts (mirroring `Measure`'s per-field flow in `states.py` / `handlers/
  measure.py`) is the fallback design.

## Risks & open questions
- **Ambiguous grouping**: the raw idea says "пропустить этот шаг" (singular) for all three
  metrics together, which this plan takes as "one shared, freely-skippable step" rather than
  three independently skippable fields. If the real intent was per-field skipping, the
  three-prompt fallback noted above is the alternative.
- **Parser fragility**: regex-based unit extraction from free text can misparse unusual
  phrasing (e.g. "полчаса" instead of "30 мин"); treated as acceptable given the idea's own
  fallback ("если нечем отследить это") — a failed parse degrades to no metrics, never to an
  error that blocks saving the workout.
- Extra FSM step for cardio slightly lengthens the fastest "log a cardio workout" path;
  mitigated by making it fully skippable, same as every other optional step in this flow.

## Effort
S (< 1h) — one new small tag table, one pure parser module, and one new FSM step following
existing patterns (`workout_body_parts` for storage, `skip_cancel_kb`/`ASK_DESCRIPTION` for
the prompt shape); no changes to stats, reports, or the edit flow.
