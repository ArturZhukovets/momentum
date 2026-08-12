"""Paths and environment for the loop. Loaded once; every other submodule imports this."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ai_automation/suggestions_loop/config.py -> repo root
ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL = os.getenv("MODEL", "sonnet")
DEFAULT_BUDGET_USD = os.getenv("BUDGET_USD", "1.0")
DEFAULT_MAX_TASKS = int(os.getenv("MAX_TASKS", "3"))

# The only remote status the loop drafts from: the admin reviewed the suggestion and
# green-lit it. `new` is still awaiting that review.
APPROVED_STATUS = "approved"
