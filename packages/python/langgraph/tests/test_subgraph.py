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


_SUBGRAPH_EVIDENCE_SOURCE = {
    "opaque-child": "compiled.nodes.bound",
    "materialized-child": "graphs[].id+node.subgraphId",
}


def meaning(document):
    result = {}
    for record in document["graphs"][0][KEY]["nodes"]:
        if "subgraph" not in record:
            continue
        fact = copy.deepcopy(record["subgraph"])
        if "evidence" in fact:
            assert (
                fact["evidence"].pop("source")
                == _SUBGRAPH_EVIDENCE_SOURCE[fact["value"]]
            )
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
        for graph in value["graphs"]:
            del graph[KEY]
    baseline["provenance"] = stripped["provenance"]
    assert baseline == stripped
    assert compute_structure_hash(stripped) == document["structureHash"]
    assert document["structureHash"]["algorithmVersion"] == "1"
    if case["mode"] == "child" and case["depth"] >= 1:
        materialized = 1
    elif case["mode"] == "grandchild" and case["depth"] >= 1:
        materialized = 2 if case["depth"] >= 2 else 1
    else:
        materialized = 0
    assert len(document["graphs"]) == 1 + materialized
    child_node = next(
        n for n in document["graphs"][0]["structure"]["nodes"] if n["id"] == "child"
    )
    if materialized:
        assert child_node["subgraphId"] == "main:child"
    else:
        assert "subgraphId" not in child_node
    assert all(
        "subgraphId" not in n
        for n in document["graphs"][0]["structure"]["nodes"]
        if n["id"] != "child"
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
    assert meaning(document) == {
        "child": {
            "status": "known",
            "value": "materialized-child",
            "evidence": {"kind": "materialized-subgraph-reference"},
        }
    }
    assert not any(
        g["code"] == "expanded-subgraph-metadata"
        for g in document["completeness"]["gaps"]
    )
    child_node = next(
        n for n in document["graphs"][0]["structure"]["nodes"] if n["id"] == "child"
    )
    assert child_node["subgraphId"] == "main:child"
    materialized_ids = {g["id"] for g in document["graphs"][1:]}
    assert "main:child" in materialized_ids
    if mode == "grandchild" and depth >= 2:
        assert "main:child:inner" in materialized_ids


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


def test_reused_child_at_two_call_sites():
    shared = chain([("step", forbidden)])
    builder = StateGraph(State)
    builder.add_node("left", shared)
    builder.add_node("right", shared)
    builder.add_edge(START, "left")
    builder.add_edge("left", "right")
    builder.add_edge("right", END)
    document = describe(builder.compile(), depth=1)
    assert not validate_document(document)
    assert ORACLE(document) == "valid"
    assert document["completeness"]["gaps"] == []
    graph_ids = {g["id"] for g in document["graphs"]}
    assert graph_ids == {"main", "main:left", "main:right"}
    left = next(g for g in document["graphs"] if g["id"] == "main:left")
    right = next(g for g in document["graphs"] if g["id"] == "main:right")
    left_structure = copy.deepcopy(left["structure"])
    right_structure = copy.deepcopy(right["structure"])
    assert left_structure == right_structure
    assert document["structureHash"]["algorithmVersion"] == "1"


def test_node_ids_cannot_contain_the_derived_id_delimiter():
    # LangGraph itself reserves ':' in node names, so a producer-caused
    # collision (two derivation paths concatenating to the same string) can
    # never arise from any real compiled graph: the derivation scheme is
    # injective once every segment is guaranteed colon-free. Confirm the
    # premise, then exercise the fallback directly below.
    with pytest.raises(ValueError, match="reserved character"):
        StateGraph(State).add_node("sub:grand", forbidden)


def test_derived_id_collision_falls_back_to_opaque():
    module = importlib.import_module("agent_topology.langgraph._describe")
    builder = StateGraph(State)
    builder.add_node("child", chain([("step", forbidden)]))
    builder.add_edge(START, "child")
    builder.add_edge("child", END)
    # Seed assigned_ids as if "main:child" were already taken elsewhere in the
    # traversal, since no real graph can make two derivations collide.
    graphs, gaps = module._extract_graph(
        builder.compile(), "main", 1, {"main", "main:child"}
    )
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
