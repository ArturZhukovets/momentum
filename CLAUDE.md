# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Momentum is a personal Telegram bot for tracking workouts (cardio with a photo, or
strength with body parts), on aiogram 3 + aiosqlite + APScheduler. Fully async, Python
3.13, packaged with `uv`. **User-facing copy is entirely Russian; code is English** — all
Russian strings live only in the `texts/` package, never inline them.

## Commands

```bash
uv sync                       # create .venv, install deps + the local package (editable)
uv run python -m momentum     # run the bot (mode comes from .env BOT_MODE)
uv run ruff check .           # lint (set: E,F,I,UP,B,SIM, py313)
uv run ruff format .          # format (line length 100)
sqlite3 data/momentum.db "select * from workouts;"   # inspect the DB
```

No test suite exists. Server (webhook) run is `docker compose up -d --build` behind host
nginx; see [README.md](README.md) for the webhook/TLS setup and full env-var table.

## Architecture

Entrypoint: `python -m momentum` → `__main__.py` → `app.main()` → config → `init_db()` →
build Bot + Dispatcher + scheduler → polling or webhook. **Polling and webhook run
identical handler code**; only `app.py`'s transport differs, selected by `BOT_MODE`.

- **`services/periods.py` + `services/stats.py` are pure** — dates/rows in, dataclasses
  out, zero aiogram/DB imports. Deliberate: the on-demand `/week` `/month` commands
  (`handlers/reports.py`) and the scheduled broadcast (`scheduler.py` →
  `services/reports.py`) share this logic exactly. Keep date math and stats here, pure.
- **`services/reports.py`** is the impure layer: fetch rows, call builders, fan out sends.
  `broadcast()` is sequential; a user who blocked the bot raises `TelegramForbiddenError`
  and is auto-unsubscribed (`reports_on = 0`) instead of breaking the run.
- **`db/` holds ALL SQL** (hand-written, no ORM), split by resource (`users.py`,
 `workouts.py`, `suggestions.py`, `profiles.py`, `goals.py`, `measurements.py`), returning
 frozen dataclasses from `db/models.py` (`Workout`, `WorkoutPoint`, `UserRow`, `UserBrief`,
 `ImprovementRequest`, `UserProfile`, `UserGoal`, `BodyMeasurement`). Every user-owned
 query is scoped by `user_id` so ids can't be poked cross-user — preserve this on any new
 query. Nothing outside `db/` touches SQL or the shared connection directly.
- **`users` is written only by `common.UserMiddleware`** (Telegram identity). Anything the
 bot *asks* the user goes to `user_profiles` / `user_goals` / `body_measurements` — keep
 that split.
- **`db/engine.py`** owns one shared aiosqlite connection via `conn()`. Three per-conn
  PRAGMAs all matter: `journal_mode=WAL`, `foreign_keys=ON` (**required** or
  `ON DELETE CASCADE` is silently ignored), `row_factory = Row`.
- **`config.py`** loads `.env` at import and exposes one `settings` object — always import
  it, nothing else reads `os.environ`. Real env vars override `.env`.
- **`texts/`, `keyboards/`, `formatters/`, and `db/` are packages, not single files** —
  each is split into per-resource submodules (e.g. a `workout` one, a `history` one, an
  `admin` one) instead of one flat module holding every resource. Nothing re-exports
  submodules through `__init__.py`; call sites import the specific submodule they need
  directly, e.g. `from momentum.texts import workout as texts_workout`.

### Handlers & flows

Handlers are aiogram `Router`s registered in `build_dispatcher()`: `common`,
`add_workout`, `profile`, `history`, `reports`. `common.UserMiddleware` is an **outer**
middleware so the `users` row exists (upserted, in-process cached) before any
handler/filter runs.

The add-workout FSM (`states.AddWorkout`, `MemoryStorage`) branches cardio→photo vs.
strength→body-parts, then description→date→save. `handlers/_prompts.py` is shared by every
FSM flow: `send_prompt`/`edit_prompt` stash the prompt message id and `drop_prompt_kb`
detaches the inline keyboard after a text reply so stale keyboards can't be re-clicked —
follow this when adding steps. FSM state is in-memory: a restart mid-flow drops an
unfinished entry (saved rows are unaffected).

`handlers/profile.py` holds the onboarding FSM plus `/profile` `/goal` `/measure`.
`common.cmd_start` greets and then delegates to `profile.start_onboarding` **only when no
`user_profiles` row exists** — that row (even all-nulls) is the "already onboarded" marker,
so every question stays skippable. Onboarding writes nothing until its last step, then
saves profile + first weight + goal together; the goal steps are shared with `/goal`,
switched by the `goal_only` FSM data key.

Typed `CallbackData` factories live in `keyboards/callbacks.py` (`ActionCB`,
`KindCB`, `PartCB`, `DateCB`, `HistCB`, `WorkoutCB`, `SkipCB`, `SexCB`, `GoalTypeCB`,
`ProfileCB`); `HistCB`/`WorkoutCB` carry `page` for back-navigation and `SkipCB` carries the
`step` it belongs to, so a leftover keyboard can't skip the question now on screen.
`ActionCB(name="cancel")` is handled once in `common.cb_cancel` for all flows.

## Conventions & gotchas

- Migrations = `schema.sql` applied idempotently (`CREATE ... IF NOT EXISTS`) every boot;
 no migration tool, so keep re-applying safe.
- Dates stored as `'YYYY-MM-DD'` local-date **text**, converted at the `db/` boundary
 (`ISO_DATE`, `to_date`/`to_date_opt`/`from_date_opt` in `db/models.py`). `kind` is
 constrained to `'cardio'|'strength'` in schema, `sex` and `goal_type` likewise.
- One active goal per user, enforced by the partial index `ux_user_goals_active`; inserting
 a second raises `IntegrityError`, so callers check `get_active_goal` first. Archiving and
 swapping goals is deliberately not implemented yet.
- Measurements are append-only history (several rows per day are fine). `latest_weight`
 skips rows that hold only circumferences.
- Cardio photos stored as the Telegram `file_id` only — nothing hits disk.
- Weeks are Mon–Sun in `APP_TZ`; months are calendar. **Streak** = consecutive weeks
  meeting `WEEKLY_GOAL` walking back from now, where the in-progress week counts only once
  it already meets the goal (see `stats._streak`).
- Every module uses `from __future__ import annotations`.
