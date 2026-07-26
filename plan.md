Ready for review
Select text to add comments on the plan
Momentum — Telegram workout-tracking bot
Context
/Users/artur/work/personal_projects/momentum is empty. We're building Momentum from scratch: a personal Telegram bot that replaces a manual workout log. The user sends a workout right after finishing it (cardio with a photo proof, or strength with body parts), the bot stores it in SQLite, and it pushes weekly and monthly progress reports automatically.

Only the Momentum half of the provided notes is in scope — the "Interview Agent" idea is a separate project and is not implemented here.

Decisions confirmed with the user:

aiogram 3 with webhook on https://89-125-51-9.sslip.io, plus a polling mode for local dev.
Open to any Telegram user; every user's data is isolated by user_id.
Cardio photos stored as Telegram file_id only (no disk storage).
Fixed WEEKLY_GOAL + APP_TZ in config; APScheduler drives the weekly/monthly sends.
Extras in scope: Dockerfile + docker-compose, and edit/delete of a logged workout.
No git init, no test suite.
TLS/ingress is handled by nginx already running on the server (not containerised — that box serves other sites too). Compose only publishes the bot's port on loopback.
⚠️ Язык интерфейса — русский
Every user-facing string is in Russian: commands' replies, button labels, FSM prompts, validation errors, workout cards, weekly/monthly reports, /help, and the Telegram command menu registered via set_my_commands. Code, identifiers, comments, log messages and DB values stay in English. All Russian copy lives in one module, src/momentum/texts.py (plain module-level constants + small format_* helpers), so nothing is hardcoded inside handlers. Dates render as DD.MM.YYYY, weekdays/months use Russian names, and counts use correct plural forms (1 тренировка / 2 тренировки / 5 тренировок) via a small plural(n, ("тренировка", "тренировки", "тренировок")) helper in texts.py.

Stack
Concern	Choice
Runtime	Python 3.13, fully async
Package manager	uv (pyproject.toml + uv.lock)
Bot	aiogram>=3.15 (native FSM, aiohttp webhook server built in)
DB	aiosqlite + hand-written SQL (3 small tables — an ORM is overhead here)
Scheduling	apscheduler>=3.10 AsyncIOScheduler
Config	python-dotenv (load_dotenv()) + pydantic-settings for typing/validation
TLS / webhook ingress	Caddy container (automatic Let's Encrypt for the sslip.io host)
Layout
momentum/
├── pyproject.toml            # uv project, deps, ruff config
├── .env.example
├── .gitignore
├── README.md
├── Dockerfile
├── docker-compose.yml
├── deploy/nginx-momentum.conf   # reference snippet to copy into the server's nginx
├── data/                     # bind-mounted; holds momentum.db
└── src/momentum/
    ├── __main__.py           # entrypoint: asyncio.run(main())
    ├── config.py             # Settings (pydantic-settings)
    ├── app.py                # build Dispatcher, start polling OR webhook, wire scheduler
    ├── states.py             # FSM StatesGroup for the add/edit flows
    ├── texts.py              # ALL Russian user-facing copy + plural() helper
    ├── keyboards.py          # all reply + inline keyboards, callback_data factories
    ├── formatters.py         # render workout cards + weekly/monthly report text (uses texts.py)
    ├── db/
    │   ├── schema.sql
    │   ├── engine.py         # aiosqlite connection, PRAGMA setup, migrate-on-start
    │   └── repo.py           # all queries (users, workouts, body_parts)
    ├── services/
    │   ├── periods.py        # tz-aware week/month boundary maths (pure)
    │   ├── stats.py          # WeeklyStats / MonthlyStats builders (pure)
    │   └── reports.py        # fan-out send of reports to all subscribed users
    ├── scheduler.py          # APScheduler cron jobs -> services.reports
    └── handlers/
        ├── common.py         # /start /help /cancel, main menu, user upsert middleware
        ├── add_workout.py    # the FSM add flow
        ├── history.py        # /history, pagination, detail card, edit + delete
        └── reports.py        # /week /month on-demand
Data model (db/schema.sql)
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,      -- telegram id
    username      TEXT,
    first_name    TEXT,
    reports_on    INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS workouts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    kind          TEXT    NOT NULL CHECK (kind IN ('cardio','strength')),
    performed_on  TEXT    NOT NULL,          -- 'YYYY-MM-DD', local date
    description   TEXT    NOT NULL DEFAULT '',
    photo_file_id TEXT,                      -- cardio only
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_workouts_user_date ON workouts(user_id, performed_on);

CREATE TABLE IF NOT EXISTS workout_body_parts (
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    body_part  TEXT    NOT NULL,
    PRIMARY KEY (workout_id, body_part)
);
engine.py opens one shared aiosqlite connection and applies three settings before use:

PRAGMA journal_mode=WAL — write-ahead logging. Instead of the default rollback journal (which takes an exclusive lock for every write and blocks readers), committed pages are appended to a momentum.db-wal sidecar file and folded into the main DB later. Readers and the writer stop blocking each other, which matters when the scheduler's report broadcast overlaps with a user logging a workout. Cost: two extra files (-wal, -shm) next to the DB.
PRAGMA foreign_keys=ON — SQLite ignores REFERENCES unless this is enabled per connection; without it the ON DELETE CASCADE on workout_body_parts silently does nothing.
row_factory = aiosqlite.Row — not a pragma; makes rows subscriptable by column name.
Then it executes schema.sql on startup (idempotent — that is the whole migration story for now).

Body parts enum (services/keyboards shared constant): stored in DB as chest, back, legs, shoulders, arms, core, full_body; displayed in Russian with emoji (🫁 Грудь, 🔙 Спина, 🦵 Ноги, 🤸 Плечи, 💪 Руки, 🧘 Пресс/кор, 🔥 Всё тело). Picking full_body clears the others; picking any other clears full_body.

Bot UX (весь текст — на русском)
Main menu (persistent reply keyboard): ➕ Добавить тренировку · 📜 История · 📊 Неделя · 🗓 Месяц.

Commands registered in the Telegram menu with Russian descriptions: /start — начать, /add — добавить тренировку, /history — история, /week — отчёт за неделю, /month — отчёт за месяц, /reports_off|/reports_on — авто-отчёты, /cancel — отмена, /help — помощь.

Add flow (FSM AddWorkout)
choosing_kind — inline: 🏃 Кардио / 💪 Силовая / ✖️ Отмена.
Cardio → cardio_photo: «Пришли фото-подтверждение 📸», waits for a photo message (takes the largest PhotoSize.file_id); non-photo input gets a nudge; ⏭ Пропустить allows a photo-less entry. → cardio_description: «Опиши тренировку» (⏭ Пропустить allowed).
Strength → strength_parts: «Что качал? Можно выбрать несколько» — inline multi-select grid, selected items get a ✅ prefix, the keyboard is edited in place on every toggle; ✅ Готово (blocked while empty) / ✖️ Отмена. → strength_description.
choosing_date — inline: Сегодня / Вчера / 📅 Другая дата; "Другая" moves to custom_date and parses DD.MM.YYYY or DD.MM (current year); future dates are rejected with «Дата не может быть в будущем», unparseable input with «Не понял дату. Формат: 05.07.2026».
Insert workout (+ body parts) in one transaction, reply with the rendered workout card and a one-line nudge «На этой неделе: 2 из 3 🎯». State cleared.
/cancel and every ✖️ Отмена button clear state from any step («Отменено»).

History & editing
/history or 📜 История → page of the 7 most recent workouts, newest first, with ‹ Назад / Вперёд › inline pagination (callback_data factory hist:page:<n>).
Each row is a button hist:open:<workout_id> → detail card (photo sent as a photo message when a file_id exists) with ✏️ Описание · 📅 Дата · 🗑 Удалить · ‹ Назад.
Edit uses a small EditWorkout FSM (awaiting_description / awaiting_date) carrying the workout id in FSMContext data; date parsing is the same helper as the add flow.
Delete asks for confirmation (Да, удалить / Отмена) before DELETE FROM workouts (body parts cascade). Every repo call is scoped by user_id so ids can't be poked cross-user.
On-demand reports
/week and /month render the exact same text the scheduler sends.

Stats (services/periods.py + services/stats.py)
Pure functions over dates + a list of rows — no aiogram/DB imports, so they are trivially testable and reusable by both the command handlers and the scheduler.

Weeks are Mon–Sun in APP_TZ; months are calendar months in APP_TZ.
WeeklyStats: total, cardio count, strength count, previous-week total, absolute diff, percent diff (guarding division by zero → show +N (new)), month-to-date total, streak.
streak = number of consecutive weeks, walking backwards from the most recently completed week, whose total ≥ WEEKLY_GOAL; the current week is included in the count when it already meets the goal. One query pulls the last ~52 weeks of dates and buckets them in memory.
MonthlyStats: total, weekly average (total / weeks_touched), cardio/strength split with percentages, body-part distribution (top parts by count), previous-month total + diff.
formatters.py renders these into the report text (HTML parse mode) — same structure as the original spec, translated:

📊 Отчёт за неделю
06.07 – 12.07

Всего тренировок: 5

💪 Силовые: 3
🏃 Кардио: 2

Прошлая неделя: 4
Разница: +1 (+25%)

Серия: 3 недели подряд с выполненной целью

В этом месяце: 18 тренировок
Users with zero workouts in the period get a short «На этой неделе тренировок не было. Начнём новую серию? 💪» variant instead of a wall of zeros.

Scheduling (scheduler.py + services/reports.py)
AsyncIOScheduler(timezone=APP_TZ) started alongside the bot, two cron triggers:

weekly — day_of_week='mon', hour=REPORT_HOUR → report for the week that just ended.
monthly — day=1, hour=REPORT_HOUR → report for the month that just ended.
reports.broadcast(kind) selects users with reports_on=1, builds stats per user, and sends sequentially with a small asyncio.sleep(0.05) between sends; TelegramForbiddenError (user blocked the bot) flips reports_on=0 instead of crashing the job. Jobs are wrapped so any exception is logged, never propagated into the scheduler.

/reports_off and /reports_on toggle the flag.

Config (config.py, .env.example)
Secrets live only in .env (git-ignored; .env.example is the committed template). config.py calls python-dotenv's load_dotenv(Path(__file__).parents[2] / ".env") at import time — so real env vars set by Docker/systemd always win over the file — and then builds a Settings(BaseSettings) model that validates and types the values. A single module-level settings = Settings() is imported everywhere; nothing else reads os.environ directly, and BOT_TOKEN/WEBHOOK_SECRET are SecretStr so they can't leak into logs.

BOT_TOKEN=
BOT_MODE=polling                  # polling | webhook
WEBHOOK_BASE=https://89-125-51-9.sslip.io
WEBHOOK_PATH=/tg/<random-secret-segment>
WEBHOOK_SECRET=                   # X-Telegram-Bot-Api-Secret-Token
WEB_HOST=0.0.0.0
WEB_PORT=8080
DB_PATH=data/momentum.db
APP_TZ=Europe/Belgrade            # confirm your tz
WEEKLY_GOAL=3
REPORT_HOUR=9
LOG_LEVEL=INFO
app.py branches on BOT_MODE: polling calls dp.start_polling after delete_webhook; webhook registers SimpleRequestHandler on an aiohttp app, calls bot.set_webhook( WEBHOOK_BASE + WEBHOOK_PATH, secret_token=...) on startup and delete_webhook on shutdown.

Deployment
Dockerfile — python:3.13-slim, COPY --from=ghcr.io/astral-sh/uv:latest, uv sync --frozen --no-dev into /app/.venv, non-root user, CMD ["uv","run","python","-m","momentum"].

docker-compose.yml — a single bot service (nginx is host-side, outside compose):

services:
  bot:
    build: .
    env_file: .env
    ports:
      - "127.0.0.1:8080:8080"     # loopback only — nginx on the host proxies to it
    volumes:
      - ./data:/app/data
    restart: unless-stopped
Host nginx — deploy/nginx-momentum.conf is a reference snippet to drop into /etc/nginx/sites-available/ on the server (certs via the existing certbot setup: certbot --nginx -d 89-125-51-9.sslip.io):

server {
    listen 443 ssl;
    server_name 89-125-51-9.sslip.io;

    ssl_certificate     /etc/letsencrypt/live/89-125-51-9.sslip.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/89-125-51-9.sslip.io/privkey.pem;

    location /tg/ {                       # must match WEBHOOK_PATH prefix
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
    }
}
Notes: aiogram verifies WEBHOOK_SECRET from that header, so the header must be forwarded (nginx drops underscored headers by default, but this one is dash-separated and passed explicitly above); Telegram only accepts ports 443/80/88/8443, so nginx must serve 443. If the cert isn't ready, set BOT_MODE=polling and the bot works unchanged — no code differs between the modes.

Build order
uv init scaffolding, pyproject.toml, deps, .env.example, .gitignore, README.md.
config.py, db/schema.sql, db/engine.py, db/repo.py.
texts.py — Russian copy + plural() + Russian date/month helpers (written first so every later handler pulls strings from it rather than inlining them).
app.py + __main__.py + handlers/common.py — /start upserts the user, main menu renders, set_my_commands with Russian descriptions.
keyboards.py, states.py, handlers/add_workout.py — full cardio + strength flows.
services/periods.py, services/stats.py, formatters.py, handlers/reports.py.
handlers/history.py — list, pagination, detail, edit, delete.
scheduler.py, services/reports.py, wired into app.py lifecycle.
Dockerfile, docker-compose.yml, deploy/nginx-momentum.conf, README run instructions.
Verification
Local (polling) — BOT_MODE=polling in .env, then uv run python -m momentum:

/start → menu appears; sqlite3 data/momentum.db "select * from users" shows the row.
Add cardio with a photo + text → confirmation card; re-add with Skip on both steps.
Add strength, toggle several body parts (check full_body mutual exclusion), Done, description, pick Other date → enter 05.07.2026 and a future date (must be rejected).
select * from workouts; select * from workout_body_parts; matches what was entered.
/history → paginate, open a detail card (photo renders), edit description, change date, delete with confirmation; verify each in SQLite.
Every message seen so far is in Russian, with correct plural forms — check 1/2/5 workouts and 1/2/5 weeks of streak; no stray English leaks from handlers.
/week and /month render the spec format. Seed a couple of weeks of rows via sqlite3 INSERTs to exercise the diff / percentage / streak branches, including the zero-previous-week case.
Temporarily register the cron jobs with a +1 minute trigger to confirm the scheduled broadcast fires and the text matches /week.
Server (webhook) — set BOT_MODE=webhook, docker compose up -d --build:

curl -I https://89-125-51-9.sslip.io/tg/<path> from outside → reaches the container (405/401 from aiogram is fine; 502 means the proxy or the port binding is wrong).
nginx -t && systemctl reload nginx after installing the snippet; certbot cert present.
curl -sS https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo → correct URL, pending_update_count: 0, empty last_error_message.
Send /start from Telegram and confirm the update lands in docker compose logs -f bot.
docker compose restart bot → data persists (the ./data bind mount).