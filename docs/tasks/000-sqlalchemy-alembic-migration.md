# Move to SQLAlchemy 2.0 + Alembic

Prerequisite for [001](001-dobavit-vidy-kardio-tipa-beg-plavanie-ellipsoid.md) (workout types).
Pure infrastructure change: **no user-facing behaviour changes**, no new tables, no new
columns. The bot must behave identically before and after.

## Key decisions
1. **Async all the way** — `sqlite+aiosqlite://`. `aiosqlite` stays as a dependency, now as
   SQLAlchemy's driver rather than the direct API.
2. **ORM models and the frozen dataclasses coexist.** New `db/tables.py` holds the
   declarative models; `db/models.py` keeps the frozen dataclasses (`Workout`, `UserRow`, …)
   as what `db/` *returns*. Everything above `db/` — formatters, services, handlers — keeps
   consuming plain frozen dataclasses, so nothing outside `db/` changes, `services/` stays
   pure, and no detached-instance / lazy-load surprises leak into aiogram handlers. The cost
   is one `_from_row`-style mapper per resource, which `db/workouts.py` already has.
3. **Session per db-function**, not a global connection or a handler middleware. Each
   function does `async with session_factory() as s:` and commits — identical call signatures,
   so no caller changes. A session middleware would enable multi-statement transactions across
   a handler; nothing needs that today.
4. **Alembic owns the schema.** `schema.sql` and `executescript` on boot are deleted.
5. **The existing DB is stamped, not rebuilt.** It already has every table.

## Plan
1. **Deps** — `pyproject.toml`: add `sqlalchemy[asyncio]>=2.0`, `alembic>=1.13`. Keep
   `aiosqlite`. `uv sync`.
2. **`db/tables.py`** — `class Base(DeclarativeBase)` + one model per existing table, matching
   the current schema *exactly* (see gotchas). Keep the CHECK constraints as
   `CheckConstraint(...)` in `__table_args__`, and the partial index `ux_user_goals_active` as
   an `Index(..., sqlite_where=...)`.
3. **`db/engine.py`** — replace the global connection with
   `create_async_engine(f"sqlite+aiosqlite:///{settings.db_file}")` and
   `async_sessionmaker(engine, expire_on_commit=False)`. Re-apply both PRAGMAs via a
   `@event.listens_for(engine.sync_engine, "connect")` hook — `foreign_keys=ON` is per
   connection and pooled connections each need it, or `ON DELETE CASCADE` silently stops
   working. `journal_mode=WAL` likewise. `init_db()` keeps its name and now just builds the
   engine.
4. **Alembic init** — `uv run alembic init -t async alembic` at the repo root.
   In `env.py`: `target_metadata = Base.metadata`, take the URL from `momentum.config.settings`
   (not from `alembic.ini`), and pass **`render_as_batch=True`** to `context.configure` — SQLite
   can't `ALTER` most things, and batch mode is what makes task 001's rename possible at all.
5. **Baseline revision** — `alembic revision --autogenerate -m "baseline"`. Then diff it
   against the real schema (`sqlite3 data/momentum.db .schema`) until autogenerate produces
   *nothing* on a second run against the live DB. This is the step that catches model/schema
   drift; don't skip it.
6. **Stamp production** — back up `data/momentum.db`, then `alembic stamp head` on it (the
   tables exist already; upgrading would try to recreate them). Fresh installs run
   `alembic upgrade head` normally.
7. **Rewrite the six `db/` modules** — `users.py`, `workouts.py`, `suggestions.py`,
   `profiles.py`, `goals.py`, `measurements.py` — as `select()` / `insert()` / `update()`,
   still returning frozen dataclasses. **Every user-owned query keeps its `user_id` filter.**
   `~800` lines total, mostly mechanical.
8. **Run migrations at startup** — small `db/migrate.py` calling Alembic's `command.upgrade`
   API from `app.main()` before `init_db()`. Personal single-instance bot, so at-boot is fine
   and keeps the Docker deploy a plain `docker compose up`.
9. **Docker** — make sure `alembic/` and `alembic.ini` are copied into the image and not
   excluded by `.dockerignore`.
10. **`CLAUDE.md`** — rewrite the `db/` bullet: "hand-written SQL, no ORM" and "one shared
    aiosqlite connection via `conn()`" are both now false. Document the ORM-model /
    frozen-dataclass split and the Alembic workflow.

## Gotchas to check while writing the models
- **`created_at` is not a `DateTime`.** It's stored as `now_iso()` output —
  `2026-08-07T10:00:00+02:00`. SQLAlchemy's SQLite `DateTime` writes and expects a different
  format and will fail to parse these. Declare the column as `String` and keep converting in
  the mapper (`to_datetime`), or add a one-off data migration. String is the cheap correct
  choice.
- **`performed_on` / `birth_date` / `recorded_on` *are* fine as `Date`** — SQLAlchemy stores
  `'YYYY-MM-DD'`, byte-identical to what's there now.
- **`reports_on` / `is_active`** map cleanly to `Boolean` over the existing INTEGER 0/1.
- `workouts.id` is `INTEGER PRIMARY KEY AUTOINCREMENT` — set
  `sqlite_autoincrement=True` in `__table_args__` or autogenerate will want to drop it.
- `description` / `note` columns are `NOT NULL DEFAULT ''` — keep the server default, not just
  a Python-side one, or the baseline diff won't be clean.

## Acceptance criteria
- [ ] `alembic revision --autogenerate` against the live DB produces an **empty** migration.
- [ ] `alembic upgrade head` on an empty file creates a schema identical to today's.
- [ ] Every bot flow works unchanged: `/add`, `/history` (+ edit/delete), `/week`, `/month`,
      `/profile`, `/goal`, `/measure`, onboarding, admin, the scheduled broadcast.
- [ ] Deleting a user cascades to workouts, body parts, profile, goals, measurements —
      proves the `foreign_keys=ON` event hook actually fires on pooled connections.
- [ ] `uv run ruff check .` clean.

## Effort
L (a day) — step 7 is ~800 lines of mechanical rewriting, and step 5 is fiddly. Steps 1–4 are
quick. Do it on a branch with a DB backup.
