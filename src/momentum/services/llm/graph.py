"""The coach-comment graph: code decides what to talk about, the model only phrases it.

    START → triage ─┬─ no_data ─────────────────────────────→ END   (no model call)
                    └─ <situation> → guard ─┬─ assemble ────→ END
                            ↑               ├─ fallback ────→ END   (no comment)
                            └── one rewrite ┘

``triage`` is a plain function over the facts' flags. Every situation is the same
leaf over its own prompt file and its own slice of the facts, registered under the
situation's name so a trace shows which way a report went. Only ``assemble`` sets
the comment, so nothing the guard rejected can leave. The graph never touches the
DB: facts arrive ready-made from ``services/reports``, which also owns the cache.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from importlib import resources
from typing import Literal, NotRequired, TypedDict, get_args

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy, default_retry_on

from momentum.config import settings
from momentum.services.llm import guard
from momentum.services.llm.facts import ReportFacts, ReportFlags, Section

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
PROMPTS_DIR = ("prompts", "report")
# The first draft plus one rewrite after a failed guard.
MAX_DRAFTS = 2
MAX_TOKENS = 400
# HTTP statuses worth another try; any other 4xx (bad key, bad request) fails the same way again.
TRANSIENT_STATUSES = frozenset({408, 409, 429})


class CommentState(TypedDict):
    facts: ReportFacts
    attempts: int
    route: NotRequired[Route]
    draft: NotRequired[str]
    problems: NotRequired[list[str]]
    comment: NotRequired[str | None]


type Node = Callable[[CommentState], Awaitable[dict]]


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
    """Pick the situation. Order matters: no data, no goal, safety, thin data, then verdicts."""
    if not flags.has_workouts and not flags.has_measurement:
        return "no_data"
    if not flags.has_goal:
        # Measurements alone mean nothing without a goal to read them against.
        return "no_goal" if flags.has_workouts else "no_data"
    if flags.pace_status == "unsafe":
        return "unsafe"
    if not flags.has_fresh_weighin:
        return "stale_measurements"
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

    Off without ``LLM_API_KEY``, and on a model or prompt that fails to load: a
    broken comment setup must not take the reports down with it.
    """
    if not settings.llm_enabled:
        return None
    try:
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


def build_writer(model: BaseChatModel, model_name: str) -> CommentWriter:
    prompts = {
        "common": _prompt("_common"),
        "rewrite": _prompt("_retry"),
        **{f"fields/{section}": _prompt("fields", section) for section in get_args(Section)},
        **{route: _prompt(route) for route in SITUATION_SECTIONS},
    }
    version_blob = json.dumps([model_name, prompts], sort_keys=True)
    return CommentWriter(
        graph=_build_graph(model, prompts),
        version=hashlib.sha256(version_blob.encode()).hexdigest(),
    )


def _build_graph(model: BaseChatModel, prompts: dict[str, str]) -> CompiledStateGraph:
    situations = list(SITUATION_SECTIONS)
    retry = RetryPolicy(max_attempts=2, retry_on=_is_transient)

    builder = StateGraph(CommentState)
    builder.add_node("triage", _triage)
    builder.add_node("no_data", _no_comment)
    builder.add_node("guard", _guard)
    builder.add_node("assemble", _assemble)
    builder.add_node("fallback", _no_comment)
    for route in situations:
        sections = SITUATION_SECTIONS[route]
        system = "\n\n".join(
            (prompts["common"], *(prompts[f"fields/{s}"] for s in sections), prompts[route])
        )
        leaf = _leaf(model, sections, system, prompts["rewrite"])
        builder.add_node(route, leaf, retry_policy=retry)
        builder.add_edge(route, "guard")

    builder.add_edge(START, "triage")
    builder.add_conditional_edges("triage", _chosen_route, ["no_data", *situations])
    builder.add_conditional_edges("guard", _after_guard, ["assemble", "fallback", *situations])
    builder.add_edge("no_data", END)
    builder.add_edge("assemble", END)
    builder.add_edge("fallback", END)
    return builder.compile(name="report_comment")


def _triage(state: CommentState) -> dict:
    return {"route": triage(state["facts"].flags)}


def _chosen_route(state: CommentState) -> Route:
    return state["route"]


def _leaf(
    model: BaseChatModel, sections: tuple[Section, ...], system: str, rewrite_note: str
) -> Node:
    async def leaf(state: CommentState) -> dict:
        facts = json.dumps(state["facts"].payload(sections), ensure_ascii=False, default=str)
        attempts = state["attempts"]
        prompt = facts
        if attempts:
            prompt = f"{facts}\n\n{rewrite_note}\n{'; '.join(state['problems'])}"
        reply = await model.ainvoke([SystemMessage(system), HumanMessage(prompt)])
        draft = "" if _truncated(reply) else _tidy(reply.text)
        return {"draft": draft, "attempts": attempts + 1}

    return leaf


def _guard(state: CommentState) -> dict:
    route = state["route"]
    found = guard.problems(state["draft"], state["facts"].payload(SITUATION_SECTIONS[route]))
    if found:
        log.info("Coach comment draft rejected on %s: %s", route, "; ".join(found))
    return {"problems": found}


def _after_guard(state: CommentState) -> str:
    if not state["problems"]:
        return "assemble"
    return state["route"] if state["attempts"] < MAX_DRAFTS else "fallback"


def _assemble(state: CommentState) -> dict:
    return {"comment": state["draft"]}


def _no_comment(_state: CommentState) -> dict:
    return {"comment": None}


def _tidy(text: str) -> str:
    """One plain paragraph: Markdown emphasis dropped, whitespace collapsed."""
    return " ".join(text.replace("*", "").split())


def _truncated(reply: AIMessage) -> bool:
    """Cut off by ``max_tokens`` — Anthropic's and OpenAI's spellings of it."""
    meta = reply.response_metadata
    return meta.get("stop_reason") == "max_tokens" or meta.get("finish_reason") == "length"


def _is_transient(exc: Exception) -> bool:
    """Network trouble, rate limits, 5xx — by the SDK error's ``status_code`` when it has one."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status in TRANSIENT_STATUSES or status >= 500
    return default_retry_on(exc)


def _prompt(*parts: str) -> str:
    *dirs, name = parts
    path = resources.files("momentum").joinpath(*PROMPTS_DIR, *dirs, f"{name}.md")
    return path.read_text(encoding="utf-8").strip()
