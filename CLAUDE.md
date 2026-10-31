# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Momentum is a personal Telegram bot for tracking workouts, body measurements and a
weight goal, on aiogram 3 + SQLAlchemy 2.0 (async, aiosqlite) + Alembic + APScheduler.
Fully async, Python 3.13, packaged with `uv`. **User-facing copy is entirely Russian;
code is English** — Russian strings live only in `texts/` (LLM prompts in `prompts/`), never
inline.

No test suite exists.

## Commands

```bash
uv sync                       # venv + deps + local package (editable)
uv run python -m momentum     # run the bot (transport from .env BOT_MODE)
uv run ruff check .           # lint (E,F,I,UP,B,SIM, py313)
uv run ruff format .          # format (line length 100)

uv run alembic revision --autogenerate -m "..."   # after editing db/tables.py
uv run alembic upgrade head                       # the bot also does this at boot
sqlite3 data/momentum.db "select * from workouts;"

python -m ai_automation.suggestions_loop run      # suggestions → task specs
```

Server (webhook) run is `docker compose up -d --build` behind host nginx; see
[README.md](README.md) for the webhook/TLS setup and the full env-var table.

## Architecture

`python -m momentum` → `app.main()`: config → migrate → `init_db()` → Bot + Dispatcher +
scheduler → polling or webhook. **Both transports run identical handler code**; only
`app.py` differs, selected by `BOT_MODE`.

### Layers

- **`db/` holds ALL queries**, SQLAlchemy Core `select()`/`insert()`/`update()` against
  the ORM models, one module per resource. Nothing outside `db/` builds a query or
  touches a session. **Every user-owned query is scoped by `user_id`** so ids can't be
  poked cross-user — preserve this on any new query.
- **Two model layers, deliberately.** `db/tables.py` = declarative ORM models (what
  Alembic autogenerates from, what queries are built against); `db/models.py` = frozen
  dataclasses (what `db/` *returns*). Each `db/` module has a `_from_row` mapper across
  the boundary, so nothing above `db/` can hit a detached instance or a lazy load. The
  names collide: `db/` modules do `from momentum.db import tables` and spell it
  `tables.Workout`.
- **`services/periods.py`, `stats.py`, `measurements.py`, `pace.py`, `energy.py`,
  `workout_types.py` are pure** — dates/rows in, dataclasses out, zero aiogram/DB-session
  imports. That's what lets the on-demand `/week` `/month` (`handlers/reports.py`) and the
  scheduled broadcast (`scheduler.py` → `services/reports.py`) share exactly the same logic.
  Keep date math and stats here, pure. The coach comment is `services/llm/` (no DB); a guard
  miss or an API error leaves the report without a comment, and the broadcast continues.
- **`services/reports.py`** is the impure layer: fetch rows, call builders, fan out.
  `broadcast()` is sequential; a user who blocked the bot raises `TelegramForbiddenError`
  and is auto-unsubscribed (`reports_on = 0`) instead of breaking the run.
- **`db/engine.py`** owns the async engine and session factory. Sessions are **per
  db-function** (`async with new_session() as s:`), not global, not middleware. Both
  PRAGMAs are re-applied on every pooled connection via a `connect` hook, not once at
  startup — `foreign_keys=ON` is per connection (**required**, or `ON DELETE CASCADE` is
  silently ignored) and `journal_mode=WAL` likewise.
- **`config.py`** loads `.env` at import and exposes one `settings` object — always
  import it; nothing else reads `os.environ`.
- **`texts/`, `keyboards/`, `formatters/`, `db/`, `handlers/` are packages split per
  resource**, and nothing is re-exported through `__init__.py`. Import the submodule you
  need: `from momentum.texts import workout as texts_workout`.

### Handlers & flows

Routers are registered in order in `app.build_dispatcher()` — **the order is load-bearing**
(admin before the FSM routers so `/admin` works mid-flow; `_profile_common` last because it
has no state filter). `common.UserMiddleware` is an **outer** middleware so the `users` row
exists before any handler or filter runs.

- Add-workout is a **generic FSM**: `services/workout_types.py` is the pure catalog, and
  the FSM walks `fields_for(type)`. Adding a workout type means extending that module plus
  its Russian labels in `texts/` — not touching the FSM.
- `handlers/_prompts.py` is shared by every FSM flow: `send_prompt`/`edit_prompt` stash the
  prompt message id and `drop_prompt_kb` detaches the inline keyboard after a text reply so
  a stale keyboard can't be re-clicked. Follow this when adding steps.
- Profile family is split: `onboarding.py`, `profile.py`, `goal.py`, `measure.py`, with
  `_profile_common.py` for the shared steps. `common.cmd_start` delegates to onboarding
  **only when no `user_profiles` row exists** — that row (even all-nulls) is the
  "already onboarded" marker, so every question stays skippable. Onboarding writes nothing
  until its last step, then saves profile + first weight + goal together.
- Typed `CallbackData` factories live in `keyboards/callbacks.py`. `HistCB`/`WorkoutCB`
  carry `page` for back-navigation; `SkipCB` carries the `step` it belongs to, so a
  leftover keyboard can't skip the question now on screen.
  `ActionCB(name="cancel")` is handled once in `common.cb_cancel` for all flows.
- FSM state is in-memory (`MemoryStorage`): a restart mid-flow drops an unfinished entry;
  saved rows are unaffected.
- Admin access is decided **only** by `ADMIN_USER_IDS` (`auth.IsAdmin`), checked on every
  message *and* callback. Everything an admin sees of another user is read-only.

### Internal HTTP API

`api/` mounts an aiohttp subapp at `/api` on the same web app as the webhook, behind an
`X-API-Key` middleware (`INTERNAL_API_KEY`). It exposes improvement suggestions so
`ai_automation/suggestions_loop/` can pull `approved` ones, run a cold `claude -p`
`task-spec-writer` agent per suggestion, and write Russian task specs into `docs/tasks/`,
tracking state in `todo.json`.

## Conventions & gotchas

- **Alembic owns the schema.** Edit `db/tables.py` → `alembic revision --autogenerate` →
  read the generated file before committing. `db/migrate.py` runs `upgrade head` from
  `app.main()`, so a plain `docker compose up` migrates itself.
- `env.py` passes **`render_as_batch=True`** — SQLite can't `ALTER` most things.
- **Every database is built by Alembic, never by hand or `create_all`.** Batch mode
  rebuilds a table from its *reflected* DDL, and SQLAlchemy's SQLite reflector can't read
  `ON DELETE` from inline `REFERENCES ... ON DELETE CASCADE` — only from a table-level
  `FOREIGN KEY`, which is what the migrations emit. A table created any other way silently
  loses its cascade on the first batch migration. `--autogenerate` against unchanged
  models must produce an empty migration; anything else is real drift.
- Dates are `Date` columns (`'YYYY-MM-DD'`), so `db/` hands out real `date` objects.
  **`created_at`/`updated_at` are `Text`, not `DateTime`** — they hold `now_iso()` output,
  which SQLAlchemy's SQLite `DateTime` can't parse; `_from_row` calls `to_datetime`.
  `sex`, `goal_type` and suggestion `status` are constrained by `CheckConstraint`.
- `users` is written **only** by `common.UserMiddleware` (Telegram identity). Anything the
  bot *asks* goes to `user_profiles` / `user_goals` / `body_measurements` — keep that split.
  A one-time notice is a row in `user_notices` (`db/notices.py`), not a new column on `users`.
- One active goal per user, enforced by the partial index `ux_user_goals_active`; a second
  insert raises `IntegrityError`, so callers check `get_active_goal` first. Archiving and
  swapping goals is deliberately not implemented.
- Measurements are append-only history (several rows per day are fine); `latest_weight`
  skips rows holding only circumferences.
- Weeks are Mon–Sun in `APP_TZ`; months are calendar. **Streak** = consecutive weeks
  meeting `WEEKLY_GOAL` walking back from now, where the in-progress week counts only once
  it already meets the goal (`stats._streak`).
- Every module uses `from __future__ import annotations`.
- `docs/` holds explainers worth reading before the change they describe: `routing.md` and
  `fsm.md` before routing or the FSM, `db-rebuild.md` before a schema rebuild,
  `releases/v0.2.0.md` before report pace, calories, or the coach comment. Divergences that
  doc lists are intentional.
- **Releases.** Every user-visible change ships as a version. **Before the commit**, bump the
  version in `pyproject.toml` (then `uv lock`) and add a short Russian section on top of
  [CHANGELOG.md](CHANGELOG.md); its header holds the versioning rules (feature → minor,
  fix → patch). Put the bump, lockfile and changelog in the same commit as the change, or in a
  release commit right on top of it. A long write-up, if any, goes to `docs/releases/vX.Y.Z.md`
  and the changelog links to it. Then tag the release commit with an annotated `vX.Y.Z` tag
  (`git tag -a vX.Y.Z -m "vX.Y.Z"`) and push the branch and the tag:
  `git push origin main && git push origin vX.Y.Z`. A release is not done until the tag is on
  `origin`.
