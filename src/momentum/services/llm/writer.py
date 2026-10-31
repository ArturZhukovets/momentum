"""The coach-comment writer ``services/reports`` calls, and the triage that picks the situation.

Light on purpose: nothing here imports LangChain or LangGraph. ``default_writer``
loads them — and builds the graph in ``services/llm/graph`` — only once comments
are on, so an empty ``LLM_API_KEY`` costs no import time and a broken install
turns the comments off instead of stopping the bot at boot.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from momentum.config import settings
from momentum.services.llm.facts import ReportFacts, ReportFlags, Section

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

log = logging.getLogger(__name__)

Route = Literal[
    "no_data",
    "no_goal",
    "cold_start",
    "stale_measurements",
    "on_track",
    "off_track",
    "recomp",
    "unsafe",
]

# The model-backed situations and the facts each one sees; a prompt file per key.
# A leaf can't drift off-topic about data it was never given.
SITUATION_SECTIONS: dict[Route, tuple[Section, ...]] = {
    "no_goal": ("workouts",),
    "cold_start": ("workouts", "goal", "measurements"),
    "stale_measurements": ("workouts", "goal"),
    "on_track": ("workouts", "goal", "measurements", "pace", "energy"),
    "off_track": ("workouts", "goal", "measurements", "pace", "energy"),
    "recomp": ("workouts", "goal", "measurements", "pace"),
    "unsafe": ("goal", "measurements", "pace", "energy"),
}
MAX_TOKENS = 400


@dataclass(frozen=True)
class CommentResult:
    route: Route
    comment: str | None  # None: the situation gets no comment, or no draft passed the guard


@dataclass(frozen=True)
class CommentWriter:
    """The compiled graph plus the version its comments are cached under.

    ``version`` hashes the model name and every prompt, so changing either
    retires the comments written before.
    """

    graph: CompiledStateGraph
    version: str

    def fingerprint(self, facts: ReportFacts) -> str:
        """Equal fingerprints, equal comment: the situation and exactly the facts its model saw."""
        route = triage(facts.flags)
        seen = facts.payload(SITUATION_SECTIONS.get(route, ()))
        blob = json.dumps([self.version, route, seen], sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

    async def write(self, facts: ReportFacts, *, user_id: int, timeout: float) -> CommentResult:
        """Run the graph for one report; ``timeout`` caps the whole run, retries included.

        A timeout, or a model error the retry policy gave up on, propagates.
        """
        config = {
            "metadata": {
                "user_id": user_id,
                "kind": facts.kind,
                "period_start": facts.period_start.isoformat(),
            },
        }
        async with asyncio.timeout(timeout):
            state = await self.graph.ainvoke({"facts": facts, "attempts": 0}, config)
        result = CommentResult(route=state["route"], comment=state.get("comment"))
        log.info(
            "Coach comment for %s (%s %s): route=%s, drafts=%s, sent=%s",
            user_id,
            facts.kind,
            facts.period_start,
            result.route,
            state["attempts"],
            result.comment is not None,
        )
        return result


def triage(flags: ReportFlags) -> Route:
    """Pick the situation. Order matters: no data, no goal, stale data, safety, thin data, verdicts.

    Stale data comes before safety: the unsafe verdict needs a fresh weigh-in,
    the same rule that decides whether the report prints a pace line at all.
    """
    if not flags.has_workouts and not flags.has_measurement:
        return "no_data"
    if not flags.has_goal:
        # Measurements alone mean nothing without a goal to read them against.
        return "no_goal" if flags.has_workouts else "no_data"
    if not flags.has_fresh_weighin:
        return "stale_measurements"
    if flags.pace_status == "unsafe":
        return "unsafe"
    if not flags.trend_ready and not flags.goal_reached:
        return "cold_start"
    if flags.weight_flat_waist_down:
        return "recomp"
    if flags.goal_reached or flags.pace_status in ("ahead", "on_track"):
        return "on_track"
    return "off_track"


@functools.cache
def default_writer() -> CommentWriter | None:
    """The writer for the configured model, built once; ``None`` — comments are off.

    Off without ``LLM_API_KEY``, and on a model, prompt or install that fails to
    load: a broken comment setup must not take the reports down with it.
    """
    if not settings.llm_enabled:
        return None
    try:
        from langchain.chat_models import init_chat_model

        from momentum.services.llm.graph import build_writer

        model = init_chat_model(
            settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY.get_secret_value(),
            # Half the report's budget, so a hung request still leaves room for the retry.
            timeout=settings.LLM_TIMEOUT / 2,
            # Retries belong to the graph's RetryPolicy, inside the report's budget.
            max_retries=0,
            max_tokens=MAX_TOKENS,
        )
        writer = build_writer(model, settings.LLM_MODEL)
    except Exception:
        log.exception("Coach comments are off: could not set up %s", settings.LLM_MODEL)
        return None
    log.info("Coach comments are on: %s", settings.LLM_MODEL)
    return writer
