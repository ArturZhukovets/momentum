---
description: Draft task specs for all pending suggestions (interactive twin of the loop's `run` command)
---

Run the suggestions loop interactively. Same state and same gates as
`uv run python -m ai_automation.suggestions_loop run` — see ai_automation/LOOP.md.

Let `LOOP` stand for `uv run python -m ai_automation.suggestions_loop`.

1. Run `LOOP sync`.
2. Run `LOOP pending --limit 3`. If it prints nothing, report and stop.
3. For each id, in parallel, spawn a `task-spec-writer` subagent. Give it the id, the
   target path from `LOOP spec-path <id>`, and the text from `LOOP suggestion <id>`.
4. For each id whose subagent finished cleanly, run `LOOP mark-drafted <id>`. For each
   whose subagent failed, run `LOOP mark-failed <id> "<failure reason>"`. Specs are
   reviewed and accepted/rejected by hand, not by an automated check.
5. Repeat from step 2 until no pending ids remain.

Do not write task specs yourself and do not edit todo.json by hand — the module owns that
state. Your job is to drive the steps and report what happened.
