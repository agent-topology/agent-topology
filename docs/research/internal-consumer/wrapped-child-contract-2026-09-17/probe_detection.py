"""ADR 0014, probe 1 of 3: does LangGraph's own closure-based subgraph
detection see campaign-agent's wrapped-invoke pattern
(channel_concept._prepare_brief, graph.py:621-648/1485-1714, pinned at
campaign-agent@62089cc4a0adcd3703b22583246bf05ff69efc37)?

Fake ports only. No model/network/notification call. Run with:

    rtk uv run --project packages/python/langgraph --group test python -B \
        docs/research/internal-consumer/wrapped-child-contract-2026-09-17/probe_detection.py
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class ChildState(TypedDict):
    raw_input: dict
    result: dict | None


def child_step(state: ChildState) -> dict:
    return {"result": {"brief": f"brief-for-{state['raw_input']['task_id']}"}}


def build_child() -> CompiledStateGraph:
    b = StateGraph(ChildState)
    b.add_node("step", child_step)
    b.add_edge(START, "step")
    b.add_edge("step", END)
    return b.compile(name="child")


class ParentState(TypedDict):
    direction_id: str
    entry: dict


def build_parent_wrapped_indirect_closure(
    child: CompiledStateGraph,
) -> CompiledStateGraph:
    """A logically identical wrapper, refactored so the outer `add_node`
    callable closes over the *helper function* rather than over `child`
    directly. `find_subgraph_pregel` only recurses into a nonlocal that is
    itself a `Runnable`/`PregelProtocol`; a plain function nonlocal is not
    walked further, so this ordinary shape is invisible to it even though it
    is behaviorally identical to the campaign shape below."""

    def _prepare_brief(state: ParentState) -> dict:
        raw_input = {"task_id": f"{state['direction_id']}:brief"}
        final = child.invoke({"raw_input": raw_input, "result": None})
        return {"entry": {**state["entry"], "brief": final["result"]["brief"]}}

    b = StateGraph(ParentState)
    b.add_node("prepare_brief", lambda state: _prepare_brief(state))
    b.add_edge(START, "prepare_brief")
    b.add_edge("prepare_brief", END)
    return b.compile(name="parent_wrapped_indirect_closure")


def build_parent_wrapped_campaign_shape(
    child: CompiledStateGraph,
) -> CompiledStateGraph:
    """Exact shape used at channel_concept/graph.py:1545-1548: a lambda
    closing over a module-level helper function, itself receiving `child` by
    keyword."""

    def _prepare_brief(state: ParentState, *, child: CompiledStateGraph) -> dict:
        raw_input = {"task_id": f"{state['direction_id']}:brief"}
        final = child.invoke({"raw_input": raw_input, "result": None})
        return {"entry": {**state["entry"], "brief": final["result"]["brief"]}}

    b = StateGraph(ParentState)
    b.add_node("prepare_brief", lambda state: _prepare_brief(state, child=child))
    b.add_edge(START, "prepare_brief")
    b.add_edge("prepare_brief", END)
    return b.compile(name="parent_wrapped_campaign_shape")


def build_parent_indirect(child: CompiledStateGraph) -> CompiledStateGraph:
    """A child reached through a container lookup rather than a direct
    closure variable -- an ordinary refactor closure inspection cannot
    resolve, used to show detection quietly going blind rather than lying."""
    children = {"brief": child}

    def _prepare_brief(state: ParentState) -> dict:
        raw_input = {"task_id": f"{state['direction_id']}:brief"}
        final = children["brief"].invoke({"raw_input": raw_input, "result": None})
        return {"entry": {**state["entry"], "brief": final["result"]["brief"]}}

    b = StateGraph(ParentState)
    b.add_node("prepare_brief", lambda state: _prepare_brief(state))
    b.add_edge(START, "prepare_brief")
    b.add_edge("prepare_brief", END)
    return b.compile(name="parent_indirect")


def build_parent_direct(child: CompiledStateGraph) -> CompiledStateGraph:
    """Candidate 1a: framework-native composition -- bind the compiled child
    directly as the node's runnable (LangGraph's documented subgraph-as-node)."""
    b = StateGraph(ChildState)
    b.add_node("prepare_brief", child)
    b.add_edge(START, "prepare_brief")
    b.add_edge("prepare_brief", END)
    return b.compile(name="parent_direct")


if __name__ == "__main__":
    child = build_child()

    for label, builder_fn in (
        (
            "wrapped (helper closes over child; outer lambda does not)",
            build_parent_wrapped_indirect_closure,
        ),
        (
            "wrapped (campaign shape: lambda -> module fn(child=kw))",
            build_parent_wrapped_campaign_shape,
        ),
    ):
        parent = builder_fn(child)
        node = parent.nodes["prepare_brief"]
        drawable = parent.get_graph(xray=0)
        print(f"--- {label} ---")
        print("bound type:", type(node.bound))
        print("bound is child CompiledStateGraph:", node.bound is child)
        print(
            "drawable.data is node.bound:",
            drawable.nodes["prepare_brief"].data is node.bound,
        )
        print("node.subgraphs:", node.subgraphs)
        print(
            "node.subgraphs[0] is child (1b detects it):",
            bool(node.subgraphs) and node.subgraphs[0] is child,
        )
        print()

    parent = build_parent_indirect(child)
    node = parent.nodes["prepare_brief"]
    print("--- indirect (dict lookup inside the node body) ---")
    print("node.subgraphs (1b goes blind on this ordinary refactor):", node.subgraphs)
    print()

    parent = build_parent_direct(child)
    node = parent.nodes["prepare_brief"]
    print("--- direct binding (1a) ---")
    print("bound type:", type(node.bound))
    print("bound is child:", node.bound is child)
