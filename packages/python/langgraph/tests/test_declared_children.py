"""ADR 0014: `declare_children` as a second, independent evidence source for
`_mapped_compiled_child`, alongside the existing direct-bound check.

Fixtures mirror the oracle proven in
`docs/research/internal-consumer/wrapped-child-contract-2026-09-17/probe_materialization.py`
and `probe_behavior.py`, now exercising the real implementation instead of a
monkeypatch: reuse at two call sites, depth 0/1/2 including a real
grandchild, unknown fallback, rejection of an undeclared node id, and that
`declare_children` is a runtime no-op under input projection, error
translation, result folding, and pause/resume.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

import pytest
from agent_topology.langgraph import IncompleteTopologyError, declare_children, describe
from agent_topology.spec import validate_document
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

KEY = "x-topology-interpretation"


class LeafState(TypedDict):
    raw_input: dict
    result: dict | None


def leaf_step(state: LeafState) -> dict:
    return {"result": {"ok": True}}


def build_leaf() -> CompiledStateGraph:
    b = StateGraph(LeafState)
    b.add_node("step", leaf_step)
    b.add_edge(START, "step")
    b.add_edge("step", END)
    return b.compile(name="leaf")


class MidState(TypedDict):
    raw_input: dict
    result: dict | None


def build_mid(leaf: CompiledStateGraph) -> CompiledStateGraph:
    def _call_leaf(state: MidState) -> dict:
        final = leaf.invoke({"raw_input": {}, "result": None})
        return {"result": final["result"]}

    b = StateGraph(MidState)
    b.add_node("grand", _call_leaf)
    b.add_edge(START, "grand")
    b.add_edge("grand", END)
    return declare_children(b.compile(name="mid"), {"grand": leaf})


class RootState(TypedDict):
    entry: dict


def build_root(mid: CompiledStateGraph, leaf: CompiledStateGraph) -> CompiledStateGraph:
    def _call_mid(state: RootState) -> dict:
        final = mid.invoke({"raw_input": {}, "result": None})
        return {"entry": {**state["entry"], "sub": final["result"]}}

    def _call_leaf(key: str):
        def _fn(state: RootState) -> dict:
            final = leaf.invoke({"raw_input": {}, "result": None})
            return {"entry": {**state["entry"], key: final["result"]}}

        return _fn

    b = StateGraph(RootState)
    b.add_node("sub", _call_mid)
    b.add_node("left", _call_leaf("left"))
    b.add_node("right", _call_leaf("right"))
    b.add_node("plain", lambda state: {"entry": state["entry"]})  # not declared
    b.add_edge(START, "sub")
    b.add_edge("sub", "left")
    b.add_edge("left", "right")
    b.add_edge("right", "plain")
    b.add_edge("plain", END)
    compiled = b.compile(name="root")
    return declare_children(compiled, {"sub": mid, "left": leaf, "right": leaf})


def _subgraph_facts(document):
    main = next(g for g in document["graphs"] if g["id"] == "main")
    return {
        record["nodeId"]: record["subgraph"]
        for record in main[KEY]["nodes"]
        if "subgraph" in record
    }


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_declared_children_materialize_like_direct_bound(depth):
    leaf = build_leaf()
    mid = build_mid(leaf)
    root = build_root(mid, leaf)

    document = describe(root, graph_id="main", depth=depth, strict=True)
    assert not validate_document(document)
    assert document["completeness"]["status"] == "complete"

    graph_ids = {g["id"] for g in document["graphs"]}
    if depth >= 1:
        assert {"main", "main:sub", "main:left", "main:right"} <= graph_ids
    else:
        assert graph_ids == {"main"}
    if depth >= 2:
        assert "main:sub:grand" in graph_ids
    else:
        assert "main:sub:grand" not in graph_ids

    facts = _subgraph_facts(document)
    if depth >= 1:
        expected = {
            "status": "known",
            "value": "materialized-child",
            "evidence": {
                "kind": "materialized-subgraph-reference",
                "source": "graphs[].id+node.subgraphId",
            },
        }
    else:
        expected = {
            "status": "known",
            "value": "opaque-child",
            "evidence": {
                "kind": "declared-child-call",
                "source": "compiled.__agent_topology_children__",
            },
        }
    for node_id in ("sub", "left", "right"):
        assert facts[node_id] == expected
    assert facts["plain"] == {"status": "unknown", "reason": "identity-unavailable"}


def test_reused_declared_child_produces_independent_materialized_graphs():
    leaf = build_leaf()
    mid = build_mid(leaf)
    root = build_root(mid, leaf)
    document = describe(root, graph_id="main", depth=1)
    left = next(g for g in document["graphs"] if g["id"] == "main:left")
    right = next(g for g in document["graphs"] if g["id"] == "main:right")
    assert left["id"] != right["id"]
    assert left["structure"] == right["structure"]


def test_declare_children_rejects_unknown_node_id():
    leaf = build_leaf()
    with pytest.raises(ValueError, match="nope"):
        declare_children(build_leaf(), {"nope": leaf})


def test_direct_bound_and_declared_child_coexist_with_distinct_evidence():
    class State(TypedDict):
        value: str

    direct_child = build_leaf()
    wrapped_child = build_leaf()

    def _call_wrapped(state: State) -> dict:
        wrapped_child.invoke({"raw_input": {}, "result": None})
        return {}

    b = StateGraph(State)
    b.add_node("direct", direct_child)
    b.add_node("wrapped", _call_wrapped)
    b.add_edge(START, "direct")
    b.add_edge("direct", "wrapped")
    b.add_edge("wrapped", END)
    compiled = declare_children(b.compile(name="root"), {"wrapped": wrapped_child})

    document = describe(compiled, graph_id="main", depth=0)
    facts = _subgraph_facts(document)
    assert facts["direct"]["evidence"]["kind"] == "compiled-child"
    assert facts["wrapped"]["evidence"]["kind"] == "declared-child-call"


def test_derived_id_collision_still_falls_back_to_opaque_for_declared_child():
    leaf = build_leaf()

    class ParentState(TypedDict):
        value: str

    def _call_leaf(state: ParentState) -> dict:
        leaf.invoke({"raw_input": {}, "result": None})
        return {}

    b = StateGraph(ParentState)
    b.add_node("child", _call_leaf)
    b.add_edge(START, "child")
    b.add_edge("child", END)
    compiled = declare_children(b.compile(name="main"), {"child": leaf})

    from agent_topology.langgraph import _describe

    graphs, gaps = _describe._extract_graph(compiled, "main", 1, {"main", "main:child"})
    assert [g["id"] for g in graphs] == ["main"]
    node = next(n for n in graphs[0]["structure"]["nodes"] if n["id"] == "child")
    assert "subgraphId" not in node
    assert gaps == [
        {
            "code": "child-graph-id-collision",
            "message": (
                "A materialized child graph id would collide with an existing "
                "graph id; the child was left opaque."
            ),
            "element": {"graphId": "main", "kind": "node", "id": "child"},
        }
    ]


def test_declare_children_is_a_runtime_noop_under_input_projection_and_resume():
    """Mirrors campaign's channel_concept._prepare_brief shape (ADR 0014):
    input projection, a narrower per-call-site context, error translation,
    result folding, and pause/resume, with declare_children applied."""

    class ChildState(TypedDict):
        raw_input: dict
        result: dict | None

    @dataclass
    class ChildRuntimeContext:
        gateway: str

    class InvalidInputError(Exception):
        pass

    def child_validate(state: ChildState) -> dict:
        if not state["raw_input"].get("task_id"):
            raise InvalidInputError("missing task_id")
        return {}

    def child_step(state: ChildState, runtime: Runtime[ChildRuntimeContext]) -> dict:
        approved = interrupt({"gateway": runtime.context.gateway})
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

    class ParentState(TypedDict):
        direction_id: str
        entry: dict
        last_error: str | None

    @dataclass
    class ParentRuntimeContext:
        gateway: str
        authorization_hash: str

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

    child = build_child()
    b = StateGraph(ParentState, context_schema=ParentRuntimeContext)
    b.add_node(
        "prepare_brief",
        lambda state, runtime: _prepare_brief(state, runtime, child=child),
    )
    b.add_edge(START, "prepare_brief")
    b.add_edge("prepare_brief", END)
    parent = declare_children(b.compile(name="parent"), {"prepare_brief": child})
    parent.checkpointer = InMemorySaver()

    document = describe(parent, depth=0, strict=True)
    assert not validate_document(document)
    facts = _subgraph_facts(document)
    assert facts["prepare_brief"]["evidence"]["kind"] == "declared-child-call"

    config = {"configurable": {"thread_id": "t1"}}
    ctx = ParentRuntimeContext(gateway="gw", authorization_hash="auth")
    state = {"direction_id": "dir-1", "entry": {}, "last_error": None}
    first = parent.invoke(state, config=config, context=ctx)
    assert "__interrupt__" in first
    second = parent.invoke(Command(resume="yes"), config=config, context=ctx)
    assert second["entry"] == {"brief": "brief-for-dir-1:brief", "approved": "yes"}
    assert second["last_error"] is None

    # Error translation: a raw_input that fails the child's own validation
    # folds into last_error rather than propagating uncaught, unaffected by
    # declare_children.
    class BadState(TypedDict):
        direction_id: str
        entry: dict
        last_error: str | None

    def _prepare_brief_bad_input(state, runtime, *, child):
        try:
            child.invoke(
                {"raw_input": {}, "result": None},
                context=ChildRuntimeContext(gateway="gw"),
            )
        except InvalidInputError as exc:
            return {"last_error": f"internal_error: prepare_brief: {exc}"}
        raise AssertionError("expected InvalidInputError")

    bad_child = build_child()
    bad_b = StateGraph(BadState, context_schema=ParentRuntimeContext)
    bad_b.add_node(
        "prepare_brief",
        lambda state, runtime: _prepare_brief_bad_input(
            state, runtime, child=bad_child
        ),
    )
    bad_b.add_edge(START, "prepare_brief")
    bad_b.add_edge("prepare_brief", END)
    bad_parent = declare_children(
        bad_b.compile(name="bad_parent"), {"prepare_brief": bad_child}
    )
    bad_result = bad_parent.invoke(
        {"direction_id": "dir-3", "entry": {}, "last_error": None},
        context=ParentRuntimeContext(gateway="gw", authorization_hash="auth"),
    )
    assert bad_result["last_error"] == "internal_error: prepare_brief: missing task_id"


def test_incomplete_topology_error_carries_the_same_document_as_non_strict():
    leaf = build_leaf()
    mid = build_mid(leaf)
    root = build_root(mid, leaf)
    document = describe(root, depth=1)
    if document["completeness"]["gaps"]:
        with pytest.raises(IncompleteTopologyError) as error:
            describe(root, depth=1, strict=True)
        assert error.value.document["completeness"] == document["completeness"]
    else:
        describe(root, depth=1, strict=True)
