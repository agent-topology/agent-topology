"""Version-pinned sentinel evidence, using minimum non-executing real graphs."""

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
CASES = json.loads((ROOT / "conformance/sentinel-cases.json").read_text())
ORACLE = runpy.run_path(str(ROOT / "spec/tests/test_interpretation_examples.py"))[
    "interpretation_status"
]
SOURCES = {
    "ordinary-node": "compiled.builder.nodes+nodes.bound",
    "framework-sentinel": "compiled.input_channels+nodes+get_graph.reserved-sentinels",
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
    child = None
    if case.get("child"):
        # Two child nodes are the minimum that both frameworks actually expand.
        child = chain([(n, forbidden) for n in ["start", "__start__-user"]], reverse)
    return chain(
        [
            (n, child if n == "child" and child is not None else forbidden)
            for n in case["nodes"]
        ],
        reverse,
    )


def meaning(document):
    result = {}
    for record in document["graphs"][0][KEY]["nodes"]:
        fact = copy.deepcopy(record["sentinel"])
        if "evidence" in fact:
            assert fact["evidence"].pop("source") == SOURCES[fact["evidence"]["kind"]]
        result[record["nodeId"]] = fact
    return result


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_shared_sentinels(case, monkeypatch):
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
        context.setattr(module, "_sentinel_interpretation", lambda *args: None)
        baseline = describe(compiled, depth=depth)
    stripped = copy.deepcopy(document)
    for graph in stripped["graphs"]:
        records = graph[KEY]["nodes"]
        for record in records:
            del record["sentinel"]
        graph[KEY]["nodes"] = [r for r in records if len(r) > 1]
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


def test_materialized_child_sentinels():
    """A materialized child's own nodes use the same sentinel evidence rules as
    a root graph; names resembling reserved sentinels are not evidence."""
    child = chain([("start", forbidden), ("__start__-user", forbidden)])
    document = describe(chain([("child", child)]), depth=1)
    child_graph = next(g for g in document["graphs"] if g["id"] == "main:child")
    records = {r["nodeId"]: r for r in child_graph[KEY]["nodes"]}
    assert records[START]["sentinel"]["value"] == "start"
    assert records[END]["sentinel"]["value"] == "end"
    assert records["start"]["sentinel"]["value"] == "ordinary"
    assert records["__start__-user"]["sentinel"]["value"] == "ordinary"
    assert ORACLE(document) == "valid"


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
        "reason": "scope-not-inspected"
        if depth > 0 and node_id == "task"
        else "identity-unavailable",
    }
    assert ORACLE(document) == "valid"


def test_failed_framework_ownership(monkeypatch):
    compiled = chain([("task", forbidden)])
    drawable = compiled.get_graph()
    monkeypatch.setattr(compiled, "get_graph", lambda **kwargs: drawable)
    compiled.input_channels = "unavailable"
    facts = meaning(describe(compiled))
    for node_id in [START, END]:
        assert facts[node_id] == {"status": "unknown", "reason": "identity-unavailable"}
    assert facts["task"]["value"] == "ordinary"


def test_reserved_ids_cannot_be_user_nodes():
    for node_id in [START, END]:
        with pytest.raises(ValueError):
            StateGraph(State).add_node(node_id, forbidden)
