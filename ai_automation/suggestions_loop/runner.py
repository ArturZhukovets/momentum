"""The agentic step and the driver that sequences a full run."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ai_automation.suggestions_loop import config
from ai_automation.suggestions_loop.api import SuggestionsAPI
from ai_automation.suggestions_loop.ledger import Task, TodoLedger


class SpecWriterAgent:
    """Runs one cold `claude -p` process per suggestion, so spec #7 is written with
    exactly as much context as spec #1."""

    AGENT = "task-spec-writer"
    ALLOWED_TOOLS = "Read,Grep,Glob,Write"
    EFFORT = "medium"

    PROMPT = """Write a task specification for suggestion #{task_id}.

Target path (write exactly this one file): {spec_path}

Raw suggestion text (Russian, verbatim):
---
{text}
---

Investigate the codebase before writing. Every file path in the spec must exist."""

    def __init__(
        self,
        root: Path = config.ROOT,
        model: str = config.DEFAULT_MODEL,
        budget_usd: str = config.DEFAULT_BUDGET_USD,
    ) -> None:
        self.root = root
        self.model = model
        self.budget_usd = budget_usd
        self.log_dir = root / ".loop" / "logs"

    def draft(self, task_id: int, spec_path: str, text: str) -> tuple[bool, Path]:
        """Returns (agent exited cleanly, path to its transcript)."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log = self.log_dir / f"{task_id}.log"
        prompt = self.PROMPT.format(task_id=task_id, spec_path=spec_path, text=text)

        with log.open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    prompt,
                    "--agent",
                    self.AGENT,
                    "--model",
                    self.model,
                    "--allowed-tools",
                    self.ALLOWED_TOOLS,
                    "--permission-mode",
                    "acceptEdits",
                    "--max-budget-usd",
                    self.budget_usd,
                    "--effort",
                    self.EFFORT,
                ],
                cwd=self.root,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        return result.returncode == 0, log


class SuggestionsLoop:
    """Facade over api / ledger / agent — one method per CLI command."""

    def __init__(
        self,
        root: Path = config.ROOT,
        model: str = config.DEFAULT_MODEL,
        budget_usd: str = config.DEFAULT_BUDGET_USD,
    ) -> None:
        self.root = root
        self.api = SuggestionsAPI()
        self.ledger = TodoLedger(root)
        self.agent = SpecWriterAgent(root, model=model, budget_usd=budget_usd)
        self.cache = root / ".loop" / "suggestions.json"

    # -- deterministic commands

    async def sync(self) -> None:
        """Fetch → cache raw JSON → upsert ledger entries. Safe to re-run."""
        suggestions = await self.api.fetch_all()

        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_text(
            json.dumps(
                [s.model_dump(mode="json") for s in suggestions], ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )

        added = self.ledger.upsert(suggestions)
        pending = self.ledger.summary()["pending"]
        print(f"synced {len(suggestions)} suggestions; +{added} new; {pending} pending")

    async def show(self) -> None:
        """Print every remote suggestion, bypassing the ledger."""
        for suggestion in await self.api.fetch_all():
            print(f"Suggestion from {suggestion.user_full_name}:\n{suggestion.request_text}\n")
            print("-" * 100)

    def pending(self, limit: int = 0) -> None:
        for task_id in self.ledger.pending_ids(limit):
            print(task_id)

    def spec_path(self, task_id: int) -> None:
        print(self.ledger.get(task_id).spec)

    def suggestion(self, task_id: int) -> None:
        print(self.ledger.request_text(task_id))

    def summary(self) -> None:
        for status, count in self.ledger.summary().items():
            print(f"{status:>9}: {count}")

    def mark_drafted(self, task_id: int) -> None:
        task = self.ledger.mark_drafted(task_id)
        print(f"{task_id} -> drafted ({task.title})")

    def mark_failed(self, task_id: int, reason: str) -> None:
        task = self.ledger.mark_failed(task_id, reason)
        print(
            f"{task_id} -> {task.status} "
            f"(attempt {task.attempts}/{TodoLedger.MAX_ATTEMPTS}): {reason[:120]}"
        )

    # -- the loop itself

    async def run(self, max_tasks: int = config.DEFAULT_MAX_TASKS) -> None:
        """sync → for each pending task: draft, flip status. Drafted specs are reviewed
        and accepted or rejected by hand, not by an automated check."""
        # 1. Create the "docs/task" dir if not exist
        (self.root / TodoLedger.TASKS_DIR).mkdir(parents=True, exist_ok=True)

        print("==> syncing suggestions")

        # 2. Sync tasks list
        await self.sync()

        # 3. Retrieve only ids which are in "pending" status
        ids = self.ledger.pending_ids(max_tasks)
        if not ids:
            print("==> nothing pending, done")
            return

        drafted = failed = 0

        # 4. Handle each task via claude code agent
        for task_id in ids:
            task: Task = self.ledger.get(task_id)
            print(f"==> [{task_id}] drafting {task.spec}")

            ok, log = self.agent.draft(
                task_id=task_id,
                spec_path=task.spec,
                text=self.ledger.request_text(task_id)
            )
            if not ok:
                self.mark_failed(task_id, f"agent run failed, see {log.relative_to(self.root)}")
                failed += 1
                continue

            self.mark_drafted(task_id)
            drafted += 1

        print(f"==> done: {drafted} drafted, {failed} failed")
        self.summary()
