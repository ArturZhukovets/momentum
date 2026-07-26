# Momentum

Personal Telegram bot for tracking workouts. You log a workout right after
finishing it — cardio with a photo proof, or strength with body parts — and the
bot stores it in SQLite and pushes weekly and monthly progress reports.

The bot's interface is entirely in Russian; the codebase is in English.

## Stack

| Concern        | Choice                                     |
| -------------- | ------------------------------------------ |
| Runtime        | Python 3.13, fully async                   |
| Packaging      | uv (`pyproject.toml` + `uv.lock`)          |
| Bot            | aiogram 3 (native FSM, aiohttp webhook)    |
| DB             | aiosqlite + hand-written SQL               |
| Scheduling     | APScheduler `AsyncIOScheduler`             |
| Config         | python-dotenv + pydantic-settings          |
| TLS / ingress  | nginx on the host (already running)        |

## Layout

```
src/momentum/
├── __main__.py        entrypoint
├── config.py          Settings (pydantic-settings)
├── app.py             Dispatcher, polling/webhook, lifecycle
├── states.py          FSM state groups
├── texts.py           ALL Russian copy + plural()/date helpers
├── keyboards.py       keyboards + callback_data factories
├── formatters.py      workout cards + report text
├── scheduler.py       cron jobs
├── db/                schema.sql, engine.py, repo.py
├── services/          periods.py, stats.py, reports.py
└── handlers/          common, add_workout, history, reports
```

`services/periods.py` and `services/stats.py` are pure — dates and rows in,
dataclasses out — so the on-demand commands and the scheduled broadcast share
exactly the same logic.

## Local run (polling)

```bash
cp .env.example .env      # fill in BOT_TOKEN, keep BOT_MODE=polling
uv sync
uv run python -m momentum
```

The DB is created at `data/momentum.db` on first start; `schema.sql` is applied
idempotently on every boot (that is the whole migration story for now).

Inspect it with:

```bash
sqlite3 data/momentum.db "select * from workouts;"
```

## Server run (webhook)

Set in `.env`:

```
BOT_MODE=webhook
WEBHOOK_BASE=https://89-125-51-9.sslip.io
WEBHOOK_PATH=/tg/<random-secret-segment>
WEBHOOK_SECRET=<random string>
```

```bash
docker compose up -d --build
```

Compose publishes the port on loopback only. Install the host nginx snippet
from [deploy/nginx-momentum.conf](deploy/nginx-momentum.conf) — its `location`
prefix must match `WEBHOOK_PATH` — then:

```bash
nginx -t && systemctl reload nginx
curl -sS "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"
```

Expect the right URL, `pending_update_count: 0`, and no `last_error_message`.
If the certificate isn't ready yet, set `BOT_MODE=polling` — no code differs
between the two modes.

## Configuration

| Variable         | Default             | Notes                                    |
| ---------------- | ------------------- | ---------------------------------------- |
| `BOT_TOKEN`      | —                   | required, `SecretStr`                    |
| `BOT_MODE`       | `polling`           | `polling` \| `webhook`                   |
| `WEBHOOK_BASE`   | —                   | webhook mode only                        |
| `WEBHOOK_PATH`   | `/tg/momentum`      | keep the random segment secret           |
| `WEBHOOK_SECRET` | —                   | `X-Telegram-Bot-Api-Secret-Token`        |
| `WEB_HOST`       | `0.0.0.0`           |                                          |
| `WEB_PORT`       | `8080`              |                                          |
| `DB_PATH`        | `data/momentum.db`  | relative paths resolve to the repo root  |
| `APP_TZ`         | `Europe/Belgrade`   | weeks and months are computed in this tz |
| `WEEKLY_GOAL`    | `3`                 | drives the nudge and the streak counter  |
| `REPORT_HOUR`    | `9`                 | local hour for both broadcasts           |
| `LOG_LEVEL`      | `INFO`              |                                          |

## Behaviour notes

- Weeks are Mon–Sun in `APP_TZ`; months are calendar months.
- **Streak** = consecutive weeks meeting `WEEKLY_GOAL`, walking backwards from
  the current week. The current week counts only once it already meets the
  goal, so an in-progress week never breaks a live streak.
- Cardio photos are stored as Telegram `file_id` only — nothing is written to
  disk.
- Every workout query is scoped by `user_id`, so ids can't be poked cross-user.
- FSM state lives in memory: a restart mid-flow drops an unfinished entry.
  Saved workouts are unaffected.
- Reports go only to users with `reports_on = 1`; a user who blocks the bot is
  unsubscribed automatically instead of breaking the broadcast.
