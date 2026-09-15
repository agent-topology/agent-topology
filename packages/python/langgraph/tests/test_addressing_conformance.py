"""Minimal fixtures verifying graph/node address resolution (issue #150).

Exercises the shared `examples/trace-correlation` correlation module against
minimal real LangGraph graphs: caller-selected `graph_id` versus compile
display name, exact matches, parent/child/grandchild addresses, repeated
child call sites, missing graph ids, unknown nodes, and ambiguous evidence.
Every case records resolved, unmatched, or ambiguous -- never a manufactured
match (ADR 0002, ADR 0011).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, TypedDict

from agent_topology.langgraph import describe
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = ROOT / "examples" / "trace-correlation"


def _correlate_module():
    spec = importlib.util.spec_from_file_location(
        "trace_correlation_addressing_conformance", EXAMPLE / "correlate.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


correlate = _correlate_module().correlate


class _State(TypedDict, total=False):
    value: str


def _step(_state: _State) -> dict[str, str]:
    return {}


def _linear_graph(*names: str) -> CompiledStateGraph:
    builder = StateGraph(_State)
    for name in names:
        builder.add_node(name, _step)
    stops = [START, *names, END]
    for source, target in zip(stops, stops[1:]):
        builder.add_edge(source, target)
    return builder.compile()


def _trace(*events: dict[str, Any]) -> dict[str, Any]:
    return {
        "provenance": {
            "kind": "conformance-fixture",
            "framework": {"name": "langgraph", "version": "1"},
        },
        "events": list(events),
    }


def _event(
    event_id: str, node_id: str | None, graph_id: str | None = None
) -> dict[str, Any]:
    event: dict[str, Any] = {"eventId": event_id, "kind": "node"}
    if node_id is not None:
        event["nodeId"] = node_id
    if graph_id is not None:
        event["graphId"] = graph_id
    return event


def test_exact_graph_and_node_match_resolves() -> None:
    topology = describe(_linear_graph("first", "second"), graph_id="checkout")

    result = correlate(topology, _trace(_event("e1", "first", "checkout")))

    assert result["events"][0]["status"] == "matched"
    assert result["events"][0]["match"] == {
        "graphId": "checkout",
        "kind": "node",
        "id": "first",
    }


def test_caller_selected_graph_id_is_the_address_not_the_display_name() -> None:
    builder = StateGraph(_State)
    builder.add_node("first", _step)
    builder.add_node("second", _step)
    builder.add_edge(START, "first")
    builder.add_edge("first", "second")
    builder.add_edge("second", END)
    compiled = builder.compile(name="Checkout Flow")

    topology = describe(compiled, graph_id="checkout")

    assert topology["graphs"][0]["id"] == "checkout"
    assert topology["graphs"][0]["name"] == "Checkout Flow"

    by_display_name = correlate(
        topology, _trace(_event("e1", "first", "Checkout Flow"))
    )
    assert by_display_name["events"][0]["status"] == "unmatched"
    assert (
        by_display_name["events"][0]["reason"]
        == "no-topology-node-has-this-qualified-identity"
    )

    by_graph_id = correlate(topology, _trace(_event("e2", "first", "checkout")))
    assert by_graph_id["events"][0]["status"] == "matched"


def test_parent_child_grandchild_addresses_resolve_independently() -> None:
    grandchild_builder = StateGraph(_State)
    grandchild_builder.add_node("leaf", _step)
    grandchild_builder.add_edge(START, "leaf")
    grandchild_builder.add_edge("leaf", END)
    grandchild = grandchild_builder.compile()

    child_builder = StateGraph(_State)
    child_builder.add_node("inner", grandchild)
    child_builder.add_edge(START, "inner")
    child_builder.add_edge("inner", END)
    child = child_builder.compile()

    parent_builder = StateGraph(_State)
    parent_builder.add_node("child", child)
    parent_builder.add_edge(START, "child")
    parent_builder.add_edge("child", END)
    parent = parent_builder.compile()

    topology = describe(parent, graph_id="main", depth=2)
    assert {g["id"] for g in topology["graphs"]} == {
        "main",
        "main:child",
        "main:child:inner",
    }

    result = correlate(
        topology,
        _trace(
            _event("parent-evt", "child", "main"),
            _event("child-evt", "inner", "main:child"),
            _event("grandchild-evt", "leaf", "main:child:inner"),
        ),
    )
    statuses = {e["eventId"]: e["status"] for e in result["events"]}
    assert statuses == {
        "parent-evt": "matched",
        "child-evt": "matched",
        "grandchild-evt": "matched",
    }


def test_repeated_child_call_sites_stay_distinct_addresses() -> None:
    shared = _linear_graph("step")
    builder = StateGraph(_State)
    builder.add_node("left", shared)
    builder.add_node("right", shared)
    builder.add_edge(START, "left")
    builder.add_edge("left", "right")
    builder.add_edge("right", END)
    topology = describe(builder.compile(), graph_id="main", depth=1)
    assert {g["id"] for g in topology["graphs"]} == {"main", "main:left", "main:right"}

    qualified = correlate(
        topology,
        _trace(
            _event("e1", "step", "main:left"),
            _event("e2", "step", "main:right"),
        ),
    )
    assert [e["status"] for e in qualified["events"]] == ["matched", "matched"]
    assert qualified["events"][0]["match"]["graphId"] == "main:left"
    assert qualified["events"][1]["match"]["graphId"] == "main:right"

    unqualified = correlate(topology, _trace(_event("e3", "step")))
    assert unqualified["events"][0]["status"] == "ambiguous"
    assert unqualified["events"][0]["reason"] == "trace-event-omits-graph-identity"
    assert {c["graphId"] for c in unqualified["events"][0]["candidates"]} == {
        "main:left",
        "main:right",
    }


def test_missing_graph_id_resolves_only_when_node_id_is_globally_unique() -> None:
    topology = describe(_linear_graph("only"), graph_id="checkout")

    result = correlate(topology, _trace(_event("e1", "only")))

    assert result["events"][0] == {
        "eventId": "e1",
        "kind": "node",
        "status": "matched",
        "match": {"graphId": "checkout", "kind": "node", "id": "only"},
        "reason": "node-id-is-globally-unique",
    }


def test_unknown_node_is_unmatched_not_manufactured() -> None:
    topology = describe(_linear_graph("first", "second"), graph_id="checkout")

    unqualified = correlate(topology, _trace(_event("e1", "ghost")))
    assert unqualified["events"][0] == {
        "eventId": "e1",
        "kind": "node",
        "status": "unmatched",
        "reason": "no-topology-node-has-this-node-id",
    }

    qualified = correlate(topology, _trace(_event("e2", "ghost", "checkout")))
    assert qualified["events"][0] == {
        "eventId": "e2",
        "kind": "node",
        "status": "unmatched",
        "reason": "no-topology-node-has-this-qualified-identity",
    }
