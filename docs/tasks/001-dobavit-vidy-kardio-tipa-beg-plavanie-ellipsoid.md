# Add cardio types (running, swimming, elliptical, walking)

## Idea
> Добавить виды кардио типа
> Бег, плавание, эллипсоид, ходьба

("Add cardio types like running, swimming, elliptical, walking.") The user wants to tag a
cardio workout with what kind of cardio it was, not just log a bare "cardio" entry.

## Verdict
Relevant: yes.
Already implemented: no — `workouts.kind` only distinguishes `'cardio'` vs `'strength'`
(`src/momentum/db/schema.sql:12`); there is no sub-type for cardio anywhere in the schema,
FSM, or texts.
Feasible: yes, with the same "optional tag table" pattern already used for strength body
parts (`workout_body_parts`), which keeps the change purely additive and avoids `ALTER
TABLE` on the existing `workouts` table (SQLite `ADD COLUMN` isn't safely re-runnable, and
`CLAUDE.md` requires idempotent `schema.sql`).

## Current state
- `src/momentum/states.py` — `AddWorkout` FSM: `choosing_kind` → (cardio) `cardio_photo` →
  `cardio_description`, or (strength) `strength_parts` → `strength_description` → both join
  at `choosing_date` → `custom_date`.
- `src/momentum/handlers/add_workout.py` — `choose_kind()` branches straight from
  `KindCB` into `AddWorkout.cardio_photo` for cardio, with no intermediate step.
  `_finish()` calls `db_workouts.add_workout(...)` with `kind`, `performed_on`,
  `description`, `photo_file_id`, `body_parts`.
- `src/momentum/db/schema.sql` — `workouts` table has no cardio sub-type column;
  `workout_body_parts` is a separate tag table keyed by `workout_id`, used only for
  `kind='strength'`.
- `src/momentum/db/workouts.py` — `add_workout()`, `_workout_from_row()`, `get_workout()`,
  `list_workouts()` build `Workout` rows and attach `body_parts` from the tag table; no
  equivalent exists for cardio.
- `src/momentum/db/models.py` — `Workout` dataclass has `body_parts: tuple[str, ...] = ()`
  but no cardio-type field.
- `src/momentum/texts/workout.py` — `BODY_PARTS`/`BODY_PART_LABELS`/`body_part_label()`/
  `body_parts_line()` are the pattern to mirror; `KIND_TITLES` gives the generic "🏃 Кардио"
  title used in the card regardless of sub-type.
- `src/momentum/keyboards/workout.py` — `kind_kb()`, `skip_cancel_kb()`, `parts_kb()`,
  `date_kb()` are the existing keyboard builders; `parts_kb()` is the multi-select pattern,
  `skip_cancel_kb()` the single-button skip pattern.
- `src/momentum/keyboards/callbacks.py` — `KindCB`, `PartCB`, `ActionCB` are the relevant
  existing factories.
- `src/momentum/formatters/workout.py` — `workout_card()` renders kind title, date, body
  parts line (if any), description. `history_row_label()` renders body parts (or
  description) after the date/icon.
- `src/momentum/handlers/history.py` — edit flow (`WorkoutCB` `desc`/`date`/`del`/`del_yes`)
  only lets the user change description or date after saving; body parts are **not**
  editable post-save, and there is no precedent for editing them — the plan below follows
  that same precedent for the cardio type.

## Implementation plan
1. **`src/momentum/db/schema.sql`** — add a new tag table, following the
   `workout_body_parts` pattern but 1:1 per workout (a workout has at most one cardio
   type):
   ```sql
   CREATE TABLE IF NOT EXISTS workout_cardio_type (
       workout_id  INTEGER PRIMARY KEY REFERENCES workouts(id) ON DELETE CASCADE,
       cardio_type TEXT    NOT NULL CHECK (cardio_type IN
                            ('running','walking','swimming','elliptical'))
   );
   ```
   A separate table (rather than a new `workouts.cardio_type` column) keeps the change a
   plain `CREATE TABLE IF NOT EXISTS`, which is safely re-runnable every boot; adding a
   column to the existing `workouts` table would need a one-time `ALTER TABLE` that is not
   idempotent. The row is present only when the user picked a type (skippable, matching
   `body_parts`), so old workouts and skips just have no row.

2. **`src/momentum/db/models.py`** — add `cardio_type: str | None = None` to the `Workout`
   dataclass, after `body_parts`.

3. **`src/momentum/db/workouts.py`**:
   - `add_workout()`: add `cardio_type: str | None = None` kwarg; after inserting the
     workout row, if `cardio_type` is set, `INSERT INTO workout_cardio_type (workout_id,
     cardio_type) VALUES (?, ?)`.
   - `_workout_from_row()`: add a `cardio_type: str | None = None` parameter, pass through
     to `Workout(...)`.
   - `get_workout()`: after fetching `body_parts`, also `SELECT cardio_type FROM
     workout_cardio_type WHERE workout_id = ?` and pass the value (or `None`) into
     `_workout_from_row`.
   - `list_workouts()`: after the existing `workout_body_parts` batch query, add a matching
     batch query against `workout_cardio_type` for the same `ids`, build a
     `dict[int, str]`, and pass `cardio_type=types_by_id.get(r["id"])` into
     `_workout_from_row`.

4. **`src/momentum/keyboards/callbacks.py`** — add
   ```python
   class CardioTypeCB(CallbackData, prefix="ctype"):
       value: str  # running | walking | swimming | elliptical
   ```
   next to `KindCB`/`PartCB`.

5. **`src/momentum/texts/workout.py`** — mirror the body-parts block with a cardio-types
   block:
   - `CARDIO_TYPES: tuple[str, ...] = ("running", "walking", "swimming", "elliptical")`
   - `CARDIO_TYPE_LABELS: dict[str, str]` — e.g. `"running": "🏃 Бег"`, `"walking": "🚶
     Ходьба"`, `"swimming": "🏊 Плавание"`, `"elliptical": "🌀 Эллипсоид"`.
   - `cardio_type_label(value: str) -> str` mirroring `body_part_label`.
   - `ASK_CARDIO_TYPE = "Какой вид кардио?"` new prompt string, placed near
     `ASK_CARDIO_PHOTO`.

6. **`src/momentum/states.py`** — add `cardio_type = State()` to `AddWorkout`, between
   `choosing_kind` and `cardio_photo`.

7. **`src/momentum/keyboards/workout.py`** — add `cardio_type_kb() -> InlineKeyboardMarkup`:
   a 2×2 grid of the four `CARDIO_TYPES` (via `CardioTypeCB`), a "⏭ Пропустить" row
   (`ActionCB(name="skip")`, reusing the existing skip convention) and the cancel row —
   same shape as `parts_kb()`/`skip_cancel_kb()`.

8. **`src/momentum/handlers/add_workout.py`**:
   - `choose_kind()`: for the cardio branch, instead of jumping straight to
     `AddWorkout.cardio_photo`, set `AddWorkout.cardio_type` and `edit_prompt(callback,
     state, texts_workout.ASK_CARDIO_TYPE, kb_workout.cardio_type_kb())`.
   - New handler `choose_cardio_type(callback, callback_data: CardioTypeCB, state)` on
     `AddWorkout.cardio_type` + `CardioTypeCB.filter()`: `state.update_data(cardio_type=
     callback_data.value)`, then `edit_prompt` into the photo prompt (extract the current
     inline body of the old cardio branch — `ASK_CARDIO_PHOTO` + `skip_cancel_kb()` — into
     a small `_ask_cardio_photo(callback_or_bot, ...)` helper reused by both this handler
     and the skip handler below) and `state.set_state(AddWorkout.cardio_photo)`.
   - New handler `skip_cardio_type(callback, state, bot)` on `AddWorkout.cardio_type` +
     `ActionCB.filter(F.name == "skip")`: same transition, without storing `cardio_type`
     (leaves it absent from FSM data, so `_finish` treats it as `None`).
   - `_finish()`: read `cardio_type = data.get("cardio_type") if kind == "cardio" else
     None` and pass it to `db_workouts.add_workout(...)`.

9. **`src/momentum/formatters/workout.py`** — `workout_card()`: after the kind title line
   and before/alongside the date line, if `workout.cardio_type`, append a line such as
   `f"🏷 {texts_workout.cardio_type_label(workout.cardio_type)}"` (pick an icon distinct
   from the `🎯` used for body parts). `history_row_label()`: when `workout.kind ==
   "cardio"` and `workout.cardio_type` is set, append the short label (icon-stripped, same
   `.split(" ", 1)[-1]` trick used for body parts) instead of falling through to the
   description branch.

10. Do **not** add cardio-type editing to `handlers/history.py` — body parts have no edit
    path today either (only `desc`/`date`/`del` on `WorkoutCB`), so cardio type follows the
    same precedent: set once at creation, immutable afterwards, matching existing scope.

## Data & schema changes
- New table `workout_cardio_type(workout_id INTEGER PRIMARY KEY REFERENCES workouts(id) ON
  DELETE CASCADE, cardio_type TEXT NOT NULL CHECK (...))` in `src/momentum/db/schema.sql`,
  added via `CREATE TABLE IF NOT EXISTS` so re-applying on every boot stays safe. No changes
  to the existing `workouts` table or any other table.

## User-facing copy
`src/momentum/texts/workout.py` needs:
- `ASK_CARDIO_TYPE` — "Какой вид кардио?" (asked right after picking "🏃 Кардио").
- `CARDIO_TYPE_LABELS` — four short Russian labels with emoji, e.g. "🏃 Бег", "🚶 Ходьба",
  "🏊 Плавание", "🌀 Эллипсоид" (exact emoji choice is cosmetic, keep one per type, distinct
  from `BODY_PART_LABELS`' icons to avoid visual confusion in the card).

## Acceptance criteria
- [ ] `/add` → "🏃 Кардио" now shows a "Какой вид кардио?" step with four type buttons plus
      "⏭ Пропустить" and cancel.
- [ ] Picking a type, then finishing the flow (photo/skip → description/skip → date) saves
      the workout; its detail card (`/history` → open) shows the chosen type.
- [ ] Skipping the type step saves the workout exactly as before (no type shown on the
      card), so existing behaviour for users who don't care is unchanged.
- [ ] History list rows (`/history` page view) show the cardio type for workouts that have
      one, instead of falling back to the description.
- [ ] Strength-workout flow is untouched: no cardio-type prompt appears, body-parts flow
      unaffected.
- [ ] Old workouts saved before this change still open and render fine (no `cardio_type`
      row for them → card just omits the line, same as today).
- [ ] `sqlite3 data/momentum.db ".schema workout_cardio_type"` shows the new table after a
      restart; re-running `uv run python -m momentum` a second time does not error.

## Additional suggestions
- Consider surfacing a cardio-type breakdown in `/month` the way `MonthlyStats.body_parts`
  already ranks strength body parts (`src/momentum/services/stats.py`,
  `src/momentum/db/workouts.py:body_part_counts`) — a `cardio_type_counts()` query plus a
  `MonthlyStats.cardio_types` field would parallel the existing pattern closely. Left out of
  this plan to keep the change scoped to logging + display, since it touches the pure
  `services/stats.py` layer and both report builders.
- If it turns out the user regularly does cardio that doesn't fit any of the four types,
  the "⏭ Пропустить" skip already covers "other" (no type shown) rather than forcing a
  fifth generic "other" bucket — cheaper than adding an `'other'` enum value.

## Risks & open questions
- **Icon choice**: which emoji per type is subjective; used a reasonable set (🏃 🚶 🏊 🌀) but
  this is easy to bikeshed and has no functional impact — flagged in "User-facing copy"
  as picked-not-fixed.
- **Ambiguous naming**: "эллипсоид" literally means "ellipsoid" but colloquially refers to
  an elliptical trainer (орбитрек/эллиптический тренажёр) — used `elliptical` as the DB
  value and "🌀 Эллипсоид" as the label to match the user's own wording verbatim.
- Extra FSM step for cardio slightly lengthens the fastest "log a cardio workout" path
  (one more tap before the photo prompt); mitigated by making it skippable, same as every
  other optional step in this flow.

## Effort
S (< 1h) — one new small tag table plus one new FSM step following two existing patterns
(`workout_body_parts` for storage, `skip_cancel_kb`/`parts_kb` for the keyboard); no changes
to stats, reports, or the edit flow.
