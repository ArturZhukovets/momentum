"""argparse wiring. Translates argv into one `SuggestionsLoop` call and nothing more."""

from __future__ import annotations

import argparse
import asyncio

from ai_automation.suggestions_loop import config
from ai_automation.suggestions_loop.runner import SuggestionsLoop


class CLI:
    """`python -m ai_automation.suggestions_loop <command> [args]`."""

    def __init__(self) -> None:
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="python -m ai_automation.suggestions_loop",
            description="the suggestions → task-spec loop",
        )
        parser.add_argument("--model", default=config.DEFAULT_MODEL)
        parser.add_argument("--budget-usd", default=config.DEFAULT_BUDGET_USD)
        sub = parser.add_subparsers(dest="command", required=True)

        sub.add_parser("sync", help="fetch suggestions and upsert ledger entries")
        sub.add_parser("show", help="print every remote suggestion")
        sub.add_parser("summary", help="count ledger entries by status")

        p_pending = sub.add_parser("pending", help="print actionable pending ids")
        p_pending.add_argument("--limit", type=int, default=0)

        p_spec = sub.add_parser("spec-path", help="print one task's spec path")
        p_spec.add_argument("id", type=int)

        p_suggestion = sub.add_parser("suggestion", help="print one task's raw request text")
        p_suggestion.add_argument("id", type=int)

        p_drafted = sub.add_parser("mark-drafted", help="flip one task pending -> drafted")
        p_drafted.add_argument("id", type=int)

        p_failed = sub.add_parser("mark-failed", help="record a failed attempt")
        p_failed.add_argument("id", type=int)
        p_failed.add_argument("reason", nargs="*", default=[])

        p_run = sub.add_parser("run", help="the full loop: sync, draft, flip")
        p_run.add_argument("--max-tasks", type=int, default=config.DEFAULT_MAX_TASKS)

        return parser

    def main(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        loop = SuggestionsLoop(model=args.model, budget_usd=args.budget_usd)

        match args.command:
            case "sync":
                asyncio.run(loop.sync())
            case "show":
                asyncio.run(loop.show())
            case "run":
                asyncio.run(loop.run(args.max_tasks))
            case "summary":
                loop.summary()
            case "pending":
                loop.pending(args.limit)
            case "spec-path":
                loop.spec_path(args.id)
            case "suggestion":
                loop.suggestion(args.id)
            case "mark-drafted":
                loop.mark_drafted(args.id)
            case "mark-failed":
                loop.mark_failed(args.id, " ".join(args.reason))

        return 0


def main(argv: list[str] | None = None) -> int:
    return CLI().main(argv)
