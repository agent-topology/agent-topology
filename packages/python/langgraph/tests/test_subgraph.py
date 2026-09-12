"""Minimum real graphs; shared child meanings are independent of producer output."""

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
CASES = json.loads((ROOT / "conformance/subgraph-cases.json").read_text())
ORACLE = runpy.run_path(str(ROOT / "spec/tests/test_interpretation_examples.py"))[
    "interpretation_status"
]


class State(TypedDict):
    value: str


def forbidden(_state):
    raise AssertionError("user function executed")


def chain(nodes, reverse=False):
    builder = StateGraph(State)
    for name, runnable in reversed(nodes) if reverse else nodes:
        builder.add_node(name, runnable)
    edges = list(zip([START] + [n for n, _ in nodes], [n for n, _ in nodes] + [END]))
    for source, target in reversed(edges) if reverse else edges:
        builder.add_edge(source, target)
    return builder.compile()


HIDDEN = {}


def compile_case(mode, reverse=False, width=1):
    child = chain([(name, forbidden) for name in ["step", "next"][:width]], reverse)
    if mode == "grandchild":
        child = chain([("inner", child)], reverse)
    if mode == "ordinary":
        child = forbidden
    elif mode == "wrapper":
        HIDDEN["child"] = child

        def wrapper(state):
            raise AssertionError("wrapper executed")
            return HIDDEN["child"].invoke(state)

        child = wrapper
    return chain([("child", child)], reverse)


def meaning(document):
    result = {}
    for record in document["graphs"][0][KEY]["nodes"]:
        if "subgraph" not in record:
            continue
        fact = copy.deepcopy(record["subgraph"])
        if "evidence" in fact:
            assert fact["evidence"].pop("source") == "compiled.nodes.bound"
        result[record["nodeId"]] = fact
    return result


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['mode']}-{c['depth']}")
def test_shared_subgraph(case, monkeypatch):
    compiled = compile_case(case["mode"], width=case.get("width", 1))
    document = describe(compiled, depth=case["depth"])
    assert not validate_document(document)
    assert ORACLE(document) == "valid"
    assert document["provenance"]["framework"]["version"] in {"1.2.10", "1.2.11"}
    assert document["graphs"][0][KEY]["traversalDepth"] == case["depth"]
    assert meaning(document) == case["expected"]
    reversed_document = describe(
        compile_case(case["mode"], True, width=case.get("width", 1)),
        depth=case["depth"],
    )
    reversed_document["provenance"] = document["provenance"]
    assert canonical_json(document) == canonical_json(reversed_document)
    module = importlib.import_module("agent_topology.langgraph._describe")
    with monkeypatch.context() as context:
        context.setattr(module, "_subgraph_interpretation", lambda *args: None)
        baseline = describe(compiled, depth=case["depth"])
    stripped = copy.deepcopy(document)
    for value in (baseline, stripped):
        del value["graphs"][0][KEY]
    baseline["provenance"] = stripped["provenance"]
    assert baseline == stripped
    assert compute_structure_hash(stripped) == document["structureHash"]
    assert document["structureHash"]["algorithmVersion"] == "1"
    assert len(document["graphs"]) == 1
    assert all(
        "subgraphId" not in n for n in document["graphs"][0]["structure"]["nodes"]
    )
    if document["completeness"]["gaps"]:
        with pytest.raises(IncompleteTopologyError) as error:
            describe(compiled, depth=case["depth"], strict=True)
        assert error.value.document["completeness"] == document["completeness"]
    else:
        describe(compiled, depth=case["depth"], strict=True)


@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("mode", ["child", "grandchild"])
def test_expanded_scope(depth, mode):
    document = describe(compile_case(mode, width=2), depth=depth)
    assert not validate_document(document)
    assert ORACLE(document) == "valid"
    facts = meaning(document)
    assert "child" not in facts
    assert facts
    assert all(
        f == {"status": "unknown", "reason": "scope-not-inspected"}
        for f in facts.values()
    )
    assert any(
        g["code"] == "expanded-subgraph-metadata"
        for g in document["completeness"]["gaps"]
    )


def test_retained_identity_and_preserved_branch():
    child = chain([("step", forbidden), ("next", forbidden)])
    builder = StateGraph(State)
    for name, runnable in [
        ("child", child),
        ("retained", forbidden),
        ("left", forbidden),
        ("right", forbidden),
    ]:
        builder.add_node(name, runnable)
    for source, target in [
        (START, "child"),
        ("child", "retained"),
        ("retained", "left"),
        ("retained", "right"),
        ("left", END),
        ("right", END),
    ]:
        builder.add_edge(source, target)
    for depth in [0, 1, 2]:
        document = describe(builder.compile(), depth=depth)
        records = {r["nodeId"]: r for r in document["graphs"][0][KEY]["nodes"]}
        assert records["retained"]["branch"]["value"] == "all-declared"
        assert records["retained"]["sentinel"]["value"] == "ordinary"
        assert records["retained"]["subgraph"] == {
            "status": "unknown",
            "reason": "identity-unavailable",
        }
        assert ORACLE(document) == "valid"


@pytest.mark.parametrize("depth", [1, 2])
def test_positive_depth_can_remain_opaque(depth, monkeypatch):
    compiled = compile_case("child")
    drawable = compiled.get_graph(xray=0)
    # Controlled framework traversal fallback over a real compiled child.
    monkeypatch.setattr(compiled, "get_graph", lambda **kwargs: drawable)
    document = describe(compiled, depth=depth)
    assert meaning(document)["child"]["value"] == "opaque-child"
    assert ORACLE(document) == "valid"


def test_materialized_reference_rejects_opaque_assertion():
    document = describe(compile_case("child"))
    child = copy.deepcopy(document["graphs"][0])
    child["id"] = "materialized"
    del child[KEY]
    document["graphs"].append(child)
    node = next(
        n for n in document["graphs"][0]["structure"]["nodes"] if n["id"] == "child"
    )
    node["subgraphId"] = "materialized"
    assert not validate_document(document)
    assert ORACLE(document) == "invalid"


def test_display_name_is_not_child_evidence():
    child = describe(compile_case("child"))
    ordinary = describe(compile_case("ordinary"))
    assert child["graphs"][0]["structure"] == ordinary["graphs"][0]["structure"]
    assert child["structureHash"] == ordinary["structureHash"]
    assert meaning(child)["child"]["value"] == "opaque-child"
    assert meaning(ordinary)["child"] == {
        "status": "unknown",
        "reason": "identity-unavailable",
    }
