"""Version-pinned entry evidence, using minimum non-executing real graphs."""

import copy
import importlib
import json
import runpy
from pathlib import Path
from typing import TypedDict

import pytest
from agent_topology.langgraph import IncompleteTopologyError, describe
from agent_topology.spec import (
    canonical_json,
    compute_structure_hash,
    validate_document,
)
from langgraph.graph import END, START, StateGraph

ROOT = Path(__file__).resolve().parents[4]
KEY = "x-topology-interpretation"
CASES = json.loads((ROOT / "conformance/entry-cases.json").read_text())
ORACLE = runpy.run_path(str(ROOT / "spec/tests/test_interpretation_examples.py"))[
    "interpretation_status"
]
SOURCES = {
    "framework-entry": "compiled.input_channels+nodes+get_graph.reserved-sentinels"
}


class State(TypedDict):
    value: str


def forbidden(_state):
    raise AssertionError("user function executed")


def chain(nodes, reverse=False):
    builder = StateGraph(State)
    for name, runnable in reversed(nodes) if reverse else nodes:
        builder.add_node(name, runnable)
    names = [n for n, _ in nodes]
    edges = list(zip([START, *names], [*names, END]))
    for source, target in reversed(edges) if reverse else edges:
        builder.add_edge(source, target)
    return builder.compile()


def compile_case(case, reverse=False):
    def ordered(values):
        return list(reversed(values)) if reverse else values

    child = (
        chain([(n, forbidden) for n in ["start", "__start__-user"]], reverse)
        if case.get("child")
        else None
    )
    builder = StateGraph(State)
    for name in ordered(case["nodes"]):
        builder.add_node(
            name, child if name == "child" and child is not None else forbidden
        )
    for source, target in ordered(case["edges"]):
        builder.add_edge(source, target)
    for sources, target in ordered(case.get("joins", [])):
        builder.add_edge(ordered(sources), target)
    if case.get("startTargets"):
        builder.add_conditional_edges(START, forbidden, case["startTargets"])
    for source in ordered(case.get("routers", [])):
        builder.add_conditional_edges(source, forbidden)
    return builder.compile()


def meaning(document):
    result = {}
    for record in document["graphs"][0][KEY]["nodes"]:
        fact = copy.deepcopy(record["entry"])
        if "evidence" in fact:
            assert fact["evidence"].pop("source") == SOURCES[fact["evidence"]["kind"]]
        result[record["nodeId"]] = fact
    return result


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_shared_entries(case, monkeypatch):
    depth = case.get("depth", 0)
    compiled = compile_case(case)
    document = describe(compiled, depth=depth)
    assert not validate_document(document)
    assert ORACLE(document) == "valid"
    assert document["provenance"]["framework"]["version"] in {"1.2.10", "1.2.11"}
    assert document["graphs"][0][KEY]["traversalDepth"] == depth
    assert meaning(document) == case["expected"]
    reversed_document = describe(compile_case(case, True), depth=depth)
    reversed_document["provenance"] = document["provenance"]
    assert canonical_json(document) == canonical_json(reversed_document)
    module = importlib.import_module("agent_topology.langgraph._describe")
    with monkeypatch.context() as context:
        context.setattr(module, "_entry_interpretation", lambda *args: None)
        baseline = describe(compiled, depth=depth)
    stripped = copy.deepcopy(document)
    records = stripped["graphs"][0][KEY]["nodes"]
    for record in records:
        del record["entry"]
    stripped["graphs"][0][KEY]["nodes"] = [r for r in records if len(r) > 1]
    baseline["provenance"] = stripped["provenance"]
    assert baseline == stripped  # All pre-existing facts, core, gaps, and x-langgraph.
    del stripped["graphs"][0][KEY]
    assert compute_structure_hash(stripped) == document["structureHash"]
    assert document["structureHash"]["algorithmVersion"] == "1"
    if document["completeness"]["gaps"]:
        with pytest.raises(IncompleteTopologyError) as error:
            describe(compiled, depth=depth, strict=True)
        assert error.value.document["completeness"] == document["completeness"]
    else:
        describe(compiled, depth=depth, strict=True)


@pytest.mark.parametrize("node_id", [START, END, "task"])
@pytest.mark.parametrize("depth", [0, 1, 2])
def test_failed_visible_identity(node_id, depth, monkeypatch):
    compiled = chain([("task", forbidden)])
    drawable = compiled.get_graph(xray=depth)
    drawable.nodes[node_id] = drawable.nodes[node_id]._replace(data=object())
    monkeypatch.setattr(compiled, "get_graph", lambda **kwargs: drawable)
    document = describe(compiled, depth=depth)
    assert meaning(document)[node_id] == {
        "status": "unknown",
        "reason": "scope-not-inspected" if depth > 0 else "entry-not-established",
        "observedRoot": node_id == START,
    }
    assert ORACLE(document) == "valid"


def test_failed_framework_ownership(monkeypatch):
    compiled = chain([("task", forbidden)])
    drawable = compiled.get_graph()
    monkeypatch.setattr(compiled, "get_graph", lambda **kwargs: drawable)
    compiled.input_channels = "unavailable"
    facts = meaning(describe(compiled))
    assert all(f["status"] == "unknown" for f in facts.values())


def test_roots_do_not_depend_on_legacy_entry_array():
    module = importlib.import_module("agent_topology.langgraph._describe")
    compiled = compile_case(next(c for c in CASES if c["name"] == "join-target"))
    document = describe(compiled)
    graph = document["graphs"][0]
    expected = meaning(document)
    graph["structure"]["entryNodeIds"] = ["joined"]
    module._entry_interpretation(compiled, compiled.get_graph(), graph, 0)
    assert meaning(document) == expected


@pytest.mark.parametrize("case", [c for c in CASES if c.get("routers")])
def test_unknown_router_causality(case):
    document = describe(compile_case(case))
    graph = document["graphs"][0]
    assert graph["structure"]["entryNodeIds"] == [START, "target"]
    assert {g["element"]["id"] for g in document["completeness"]["gaps"]} == set(
        case["routers"]
    )
    assert all(
        g["code"] == "unknown-routing-targets" for g in document["completeness"]["gaps"]
    )
    assert meaning(document)["target"] == {
        "status": "unknown",
        "reason": "entry-not-established",
        "observedRoot": True,
    }
