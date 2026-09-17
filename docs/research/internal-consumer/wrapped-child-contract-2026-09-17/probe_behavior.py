"""ADR 0014, probe 2 of 3: does each composition candidate preserve input
projection, per-call-site context narrowing, InvalidInputError/ResumeDriftError
handling, result folding, and child pause/resume with correct state ownership?

Fake ports only (no model/network/notification call). Mirrors the exact call
shape at campaign-agent's channel_concept/graph.py:621-648 (_prepare_brief) and
its factory at 1485-1714 (pinned at
campaign-agent@62089cc4a0adcd3703b22583246bf05ff69efc37), using a dataclass in
place of the real pydantic models and a fake `InvalidInputError` in place of
campaign's own exception. Run with:

    rtk uv run --project packages/python/langgraph --group test python -B \
        docs/research/internal-consumer/wrapped-child-contract-2026-09-17/probe_behavior.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt


class InvalidInputError(Exception):
    pass


# ---- child: mirrors copy_brief_prepare's own contract shape --------------


class ChildState(TypedDict):
    raw_input: dict
    result: dict | None


@dataclass
class ChildRuntimeContext:
    gateway: str  # narrower than the parent's RuntimeContext


def child_validate(state: ChildState) -> dict:
    if not state["raw_input"].get("task_id"):
        raise InvalidInputError("missing task_id")
    return {}


def child_step(state: ChildState, runtime: Runtime[ChildRuntimeContext]) -> dict:
    approved = interrupt({"ask": "approve brief?", "gateway": runtime.context.gateway})
    return {
        "result": {
            "brief": f"brief-for-{state['raw_input']['task_id']}",
            "approved": approved,
        }
    }


def build_child() -> CompiledStateGraph:
    b = StateGraph(ChildState, context_schema=ChildRuntimeContext)
    b.add_node("validate", child_validate)
    b.add_node("step", child_step)
    b.add_edge(START, "validate")
    b.add_edge("validate", "step")
    b.add_edge("step", END)
    return b.compile(name="child")


# ---- parent: mirrors ChannelConceptState / RuntimeContext -----------------


class ParentState(TypedDict):
    direction_id: str
    entry: dict
    last_error: str | None


@dataclass
class ParentRuntimeContext:
    gateway: str
    authorization_hash: str  # a field the child never sees


def _prepare_brief(
    state: ParentState,
    runtime: Runtime[ParentRuntimeContext],
    *,
    child: CompiledStateGraph,
) -> dict:
    raw_input = {"task_id": f"{state['direction_id']}:brief"}
    child_ctx = ChildRuntimeContext(gateway=runtime.context.gateway)
    try:
        final = child.invoke(
            {"raw_input": raw_input, "result": None}, context=child_ctx
        )
    except InvalidInputError as exc:
        return {"last_error": f"internal_error: prepare_brief: {exc}"}
    return {
        "entry": {
            **state["entry"],
            "brief": final["result"]["brief"],
            "approved": final["result"]["approved"],
        }
    }


def build_parent_wrapped(child: CompiledStateGraph) -> CompiledStateGraph:
    b = StateGraph(ParentState, context_schema=ParentRuntimeContext)
    b.add_node(
        "prepare_brief",
        lambda state, runtime: _prepare_brief(state, runtime, child=child),
    )
    b.add_edge(START, "prepare_brief")
    b.add_edge("prepare_brief", END)
    return b.compile(name="parent_wrapped")


def build_parent_direct(child: CompiledStateGraph) -> CompiledStateGraph:
    """Candidate 1a: native composition. Only possible because ParentState is
    forced equal to ChildState here -- there is no hook for raw_input
    derivation, context narrowing, or exception translation in this shape;
    whatever the parent's state contains passes straight through by shared
    key names."""
    b = StateGraph(ChildState, context_schema=ChildRuntimeContext)
    b.add_node("prepare_brief", child)
    b.add_edge(START, "prepare_brief")
    b.add_edge("prepare_brief", END)
    return b.compile(name="parent_direct")


def run_wrapped_case() -> None:
    child = build_child()
    parent = build_parent_wrapped(child)
    parent.checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": "t1"}}
    ctx = ParentRuntimeContext(gateway="gw", authorization_hash="auth")
    state = {"direction_id": "dir-1", "entry": {}, "last_error": None}
    result = parent.invoke(state, config=config, context=ctx)
    print("first invoke result:", result)
    assert "__interrupt__" in result, (
        "expected the child's interrupt() to pause the parent"
    )
    result2 = parent.invoke(Command(resume="yes"), config=config, context=ctx)
    print("post-resume result:", result2)
    assert result2["entry"] == {"brief": "brief-for-dir-1:brief", "approved": "yes"}
    assert result2["last_error"] is None


def run_direct_case() -> None:
    child = build_child()
    parent = build_parent_direct(child)
    parent.checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": "t2"}}
    ctx = ChildRuntimeContext(gateway="gw")
    # No raw_input derivation hook under native composition: the caller must
    # already have `raw_input`/`result` keys matching the child schema.
    state = {"raw_input": {"task_id": "dir-1:brief"}, "result": None}
    result = parent.invoke(state, config=config, context=ctx)
    print("direct first invoke result:", result)
    assert "__interrupt__" in result
    result2 = parent.invoke(Command(resume="yes"), config=config, context=ctx)
    print("direct post-resume result:", result2)


def run_direct_bad_input_case() -> None:
    child = build_child()
    parent = build_parent_direct(child)
    parent.checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": "t3"}}
    state = {
        "raw_input": {},
        "result": None,
    }  # missing task_id -> InvalidInputError inside child
    try:
        parent.invoke(state, config=config, context=ChildRuntimeContext(gateway="gw"))
    except InvalidInputError as exc:
        print("direct bad-input raised uncaught (no fold point into last_error):", exc)
        return
    raise AssertionError(
        "expected InvalidInputError to propagate uncaught under direct composition"
    )


def run_direct_context_narrowing_case() -> None:
    """Does native composition let a child receive a *different*, narrower
    context type than the one the root .invoke() call was given?"""
    child = build_child()
    parent = build_parent_direct(child)
    parent.checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": "t4"}}

    @dataclass
    class WrongContextType:
        authorization_hash: str  # deliberately lacks `.gateway`

    state = {"raw_input": {"task_id": "dir-1:brief"}, "result": None}
    try:
        parent.invoke(
            state, config=config, context=WrongContextType(authorization_hash="auth")
        )
    except AttributeError as exc:
        print(
            "direct composition forwards the root context verbatim;",
            "child crashed reading it:",
            exc,
        )
        return
    raise AssertionError(
        "expected the child to see the parent's context object unmodified"
    )


if __name__ == "__main__":
    print("=== wrapped (candidate 2 shape), pause/resume + result fold ===")
    run_wrapped_case()
    print()
    print("=== direct binding (1a), pause/resume ===")
    run_direct_case()
    print()
    print("=== direct binding (1a), bad input: no fold point ===")
    run_direct_bad_input_case()
    print()
    print("=== direct binding (1a), context is not narrowed per call site ===")
    run_direct_context_narrowing_case()
    print()
    print("all assertions passed")
