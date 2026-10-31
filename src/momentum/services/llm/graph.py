"""The coach-comment graph: code decides what to talk about, the model only phrases it.

    START → triage ─┬─ no_data ─────────────────────────────→ END   (no model call)
                    └─ <situation> → guard ─┬─ assemble ────→ END
                            ↑               ├─ fallback ────→ END   (no comment)
                            └── one rewrite ┘

``triage`` is a plain function over the facts' flags (``services/llm/writer``).
Every situation is the same leaf over its own prompt file and its own slice of
the facts, registered under the situation's name so a trace shows which way a
report went. Only ``assemble`` sets the comment, so nothing the guard rejected
can leave. The graph never touches the DB: facts arrive ready-made from
``services/reports``, which also owns the cache. Imported only by
``writer.default_writer`` once comments are on — this is where LangChain and
LangGraph load.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from importlib import resources
from typing import NotRequired, TypedDict, get_args

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy, default_retry_on

from momentum.services.llm import guard
from momentum.services.llm.facts import ReportFacts, Section
from momentum.services.llm.writer import SITUATION_SECTIONS, CommentWriter, Route, triage

log = logging.getLogger(__name__)

PROMPTS_DIR = ("prompts", "report")
# The first draft plus one rewrite after a failed guard.
MAX_DRAFTS = 2
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
