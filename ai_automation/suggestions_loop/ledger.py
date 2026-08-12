"""Read/write `todo.json` — the loop's only state. Nothing else opens that file."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ai_automation.suggestions_loop import config

if TYPE_CHECKING:
    from ai_automation.suggestions_loop.api import SuggestionItem

TaskStatus = Literal["pending", "drafted", "accepted", "rejected", "blocked"]


@dataclass
class Task:
    """One ledger entry. `id` is the remote suggestion id — the idempotency key."""

    id: int
    status: TaskStatus
    title: str
    spec: str
    source: dict[str, Any] = field(default_factory=dict)
    synced_at: str | None = None
    drafted_at: str | None = None
    attempts: int = 0
    last_error: str | None = None


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class TodoLedger:
    """The ledger. Constructed with a repo root, so tests can point it at a temp dir."""

    VERSION = 1
    STATUSES: tuple[TaskStatus, ...] = ("pending", "drafted", "accepted", "rejected", "blocked")
    MAX_ATTEMPTS = 3
    TASKS_DIR = "docs/tasks"

    # Enough for readable slugs; anything unmapped becomes a dash.
    TRANSLIT = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }  # fmt: skip

    def __init__(self, root: Path = config.ROOT) -> None:
        self.root = root
        self.path = root / "todo.json"

    # -- naming helpers

    @classmethod
    def slugify(cls, text: str, max_len: int = 48) -> str:
        out: list[str] = []
        for ch in text.lower():
            if ch in cls.TRANSLIT:
                out.append(cls.TRANSLIT[ch])
            elif ch.isalnum() and ch.isascii():
                out.append(ch)
            else:
                out.append("-")
        slug = re.sub(r"-+", "-", "".join(out)).strip("-")
        return slug[:max_len].rstrip("-") or "task"

    @classmethod
    def spec_path_for(cls, task_id: int, text: str) -> str:
        return f"{cls.TASKS_DIR}/{task_id:03d}-{cls.slugify(text)}.md"

    @staticmethod
    def title_for(text: str, max_len: int = 70) -> str:
        one_line = " ".join(text.split())
        return one_line if len(one_line) <= max_len else one_line[: max_len - 1].rstrip() + "…"

    # -- persistence

    def load(self) -> list[Task]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("version") != self.VERSION:
            raise SystemExit(f"todo.json version {data.get('version')} != expected {self.VERSION}")
        return [Task(**t) for t in data["tasks"]]

    def save(self, tasks: list[Task]) -> None:
        for task in tasks:
            if task.status not in self.STATUSES:
                raise SystemExit(f"task {task.id}: invalid status {task.status!r}")
        payload = {
            "version": self.VERSION,
            "tasks": [asdict(t) for t in sorted(tasks, key=lambda t: t.id)],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # -- queries

    def get(self, task_id: int) -> Task:
        for task in self.load():
            if task.id == task_id:
                return task
        raise SystemExit(f"no todo.json entry for id {task_id}")

    def update(self, task_id: int, **changes: Any) -> Task:
        tasks = self.load()
        for task in tasks:
            if task.id != task_id:
                continue
            for key, value in changes.items():
                setattr(task, key, value)
            self.save(tasks)
            return task
        raise SystemExit(f"no todo.json entry for id {task_id}")

    def pending_ids(self, limit: int = 0) -> list[int]:
        """Actionable pending ids — tasks that burned their attempts are hidden,
        so the driver's stop condition stays a simple "is this list empty"."""
        ids = sorted(
            t.id for t in self.load() if t.status == "pending" and t.attempts < self.MAX_ATTEMPTS
        )
        return ids[:limit] if limit else ids

    def summary(self) -> dict[str, int]:
        tasks = self.load()
        return {s: sum(1 for t in tasks if t.status == s) for s in self.STATUSES}

    def request_text(self, task_id: int) -> str:
        text = self.get(task_id).source.get("request_text")
        if not text:
            raise SystemExit(f"task {task_id} has no source.request_text")
        return text

    # -- mutations

    def upsert(self, suggestions: list[SuggestionItem]) -> int:
        """Append one entry per suggestion that isn't in the ledger yet. Returns the
        number added. Only suggestions the admin approved upstream enter; `new` ones are
        still awaiting approval, `done`/`rejected` ones are settled."""
        tasks = self.load()
        known = {t.id for t in tasks}
        added = 0

        for suggestion in suggestions:
            if suggestion.id in known or suggestion.status != config.APPROVED_STATUS:
                continue
            tasks.append(
                Task(
                    id=suggestion.id,
                    status="pending",
                    title=self.title_for(suggestion.request_text),
                    spec=self.spec_path_for(suggestion.id, suggestion.request_text),
                    source={
                        "user_full_name": suggestion.user_full_name,
                        "created_at": suggestion.created_at.isoformat(),
                        "request_text": suggestion.request_text,
                    },
                    synced_at=utc_now(),
                )
            )
            added += 1

        self.save(tasks)
        return added

    def mark_drafted(self, task_id: int) -> Task:
        """pending -> drafted, adopting the English title the spec actually got."""
        task = self.get(task_id)
        if task.status != "pending":
            raise SystemExit(f"task {task_id} is {task.status}, not pending — refusing to flip")

        first = (self.root / task.spec).read_text(encoding="utf-8").lstrip().splitlines()[0]
        title = first[2:].strip() if first.startswith("# ") else task.title

        return self.update(
            task_id, status="drafted", title=title, drafted_at=utc_now(), last_error=None
        )

    def mark_failed(self, task_id: int, reason: str) -> Task:
        """Record a failed attempt; park the task as `blocked` once attempts run out."""
        attempts = self.get(task_id).attempts + 1
        status = "blocked" if attempts >= self.MAX_ATTEMPTS else "pending"
        return self.update(
            task_id,
            attempts=attempts,
            last_error=reason[:2000] or "unspecified failure",
            status=status,
        )
