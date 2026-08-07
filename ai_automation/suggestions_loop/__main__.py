"""Entry point: `uv run python -m ai_automation.suggestions_loop <command>`."""

from __future__ import annotations

import sys

from ai_automation.suggestions_loop.cli import main

if __name__ == "__main__":
    sys.exit(main())
