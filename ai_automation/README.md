# Running the suggestions loop

See [LOOP.md](LOOP.md) for the design. This is just the run book.

## Setup

```bash
export INTERNAL_API_KEY=...    # required, or put it in .env at repo root
```

Optional overrides (env or flags): `MODEL` (default `sonnet`), `BUDGET_USD` (default
`1.50`), `MAX_TASKS` (default `5`).

## Option 1 — one-shot CLI

```bash
uv run python -m ai_automation.suggestions_loop run                # sync + draft up to 5 pending
uv run python -m ai_automation.suggestions_loop run --max-tasks 15  # raise the cap once you trust it
```

Other commands for inspecting/repairing `todo.json` without running the agent:

```bash
uv run python -m ai_automation.suggestions_loop sync            # fetch + upsert ledger only
uv run python -m ai_automation.suggestions_loop show             # print every remote suggestion
uv run python -m ai_automation.suggestions_loop summary          # counts by status
uv run python -m ai_automation.suggestions_loop pending [--limit N] # see tasks ids with status "pending" 
uv run python -m ai_automation.suggestions_loop suggestion <id>   # raw request text
```

Then review each `docs/tasks/NNN-*.md` spec by hand and flip its `status` in `todo.json`
to `accepted` or `rejected`.

## Option 2 — interactive twin (inside a Claude Code session)

```
/suggestions-loop
```

Same commands, same state, but you watch the agent draft each spec and can steer it.
Self-terminating variant:

```
/goal run /suggestions-loop until `uv run python -m ai_automation.suggestions_loop pending` prints nothing, or stop after 15 turns
```



## Option 3 — scheduled

`run` is idempotent and cron-ready (keyed on remote suggestion `id`), but no schedule is
wired up yet — see LOOP.md §8 before adding one.