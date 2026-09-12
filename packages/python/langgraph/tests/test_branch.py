"""Real, nonexecuted graphs for the shared ADR 0008 branch meanings."""

import copy
import importlib
import json
import runpy
from pathlib import Path
from typing import Literal, TypedDict

import pytest
from agent_topology.langgraph import IncompleteTopologyError, describe
from agent_topology.spec import (
    canonical_json,
    compute_structure_hash,
    validate_document,
)
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

ROOT = Path(__file__).resolve().parents[4]
CASES = json.loads((ROOT / "conformance/branch-cases.json").read_text())
KEY = "x-topology-interpretation"
ORACLE = runpy.run_path(str(ROOT / "spec/tests/test_interpretation_examples.py"))[
    "interpretation_status"
]


class State(TypedDict):
    value: str


def forbidden(_state):
    raise AssertionError("user node executed")


def router(mode):
    def single(_state):
        raise AssertionError("single router executed")
        return "left"

    def multiple(_state):
        raise AssertionError("list router executed")
        return ["left", "right"]

    def annotated(_state) -> Literal["left", "right"]:
        raise AssertionError("annotated router executed")
        return "left"

    def annotated_list(_state) -> list[Literal["left", "right"]]:
        raise AssertionError("annotated list router executed")
        return ["left", "right"]

    def send(_state):
        raise AssertionError("Send router executed")
        return [Send("left", {}), Send("right", {})]

    return {
        "single": single,
        "list": multiple,
        "annotated": annotated,
        "annotated-list": annotated_list,
        "send": send,
    }[mode]


def compile_case(case, reverse=False):
    builder = StateGraph(State)

    def ordered(values):
        return list(reversed(values)) if reverse else values

    for name in ordered(case["nodes"]):
        options = {}
        if name in case.get("dynamic", {}):
            # An empty mapping remains a dynamic declaration, even with no core edges.
            options["destinations"] = {
                target: target for target in case["dynamic"][name]
            }
        builder.add_node(name, forbidden, **options)
    for source, target in ordered(case["edges"]):
        builder.add_edge(source, target)
    for sources, target in ordered(case.get("joins", [])):
        builder.add_edge(ordered(sources), target)
    for route in ordered(case.get("routers", [])):
        builder.add_conditional_edges(
            route["source"], router(route["mode"]), route.get("targets")
        )
    return builder.compile()


def meaning(document):
    records = [
        r for r in copy.deepcopy(document["graphs"][0][KEY]["nodes"]) if "branch" in r
    ]
    for record in records:
        if "evidence" in record["branch"]:
            assert (
                record["branch"]["evidence"].pop("source")
                == "compiled.builder.edges+branches+nodes.ends"
            )
    return {record["nodeId"]: record["branch"] for record in records}


def check(document, depth):
    assert not validate_document(document)
    assert ORACLE(document) == "valid"
    assert document["graphs"][0][KEY]["traversalDepth"] == depth
    stripped = copy.deepcopy(document)
    del stripped["graphs"][0][KEY]
    assert compute_structure_hash(stripped) == document["structureHash"]
    assert document["structureHash"]["algorithmVersion"] == "1"
    assert document["provenance"]["framework"]["version"] in {"1.2.10", "1.2.11"}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
@pytest.mark.parametrize("depth", [0, 1, 2])
def test_shared_branch_meaning(case, depth, monkeypatch):
    compiled = compile_case(case)
    actual = describe(compiled, depth=depth)
    check(actual, depth)
    assert meaning(actual) == case["expected"]
    reversed_document = describe(compile_case(case, reverse=True), depth=depth)
    reversed_document["provenance"] = actual["provenance"]
    assert canonical_json(actual) == canonical_json(reversed_document)
    module = importlib.import_module("agent_topology.langgraph._describe")
    # Compare the full historical core path, including x-langgraph and completeness.
    with monkeypatch.context() as context:
        context.setattr(module, "_branch_interpretation", lambda *args: None)
        context.setattr(module, "_subgraph_interpretation", lambda *args: None)
        context.setattr(module, "_sentinel_interpretation", lambda *args: None)
        baseline = describe(compiled, depth=depth)
    stripped = copy.deepcopy(actual)
    del stripped["graphs"][0][KEY]
    baseline["provenance"] = stripped["provenance"]
    assert baseline == stripped
    if actual["completeness"]["gaps"]:
        with pytest.raises(IncompleteTopologyError) as error:
            describe(compiled, depth=depth, strict=True)
        assert error.value.document["completeness"] == actual["completeness"]
    else:
        assert (
            describe(compiled, depth=depth, strict=True)["completeness"]
            == actual["completeness"]
        )


@pytest.mark.parametrize("depth", [0, 1, 2])
@pytest.mark.parametrize("nesting", [1, 2])
def test_expanded_child_scope(depth, nesting):
    child = compile_case(CASES[0])
    if nesting == 2:
        wrapper = StateGraph(State)
        wrapper.add_node("inner", child)
        wrapper.add_edge(START, "inner")
        wrapper.add_edge("inner", END)
        child = wrapper.compile()
    outer = StateGraph(State)
    outer.add_node("child", child)
    outer.add_node("retained", forbidden)
    outer.add_node("left", forbidden)
    outer.add_node("right", forbidden)
    outer.add_edge(START, "child")
    outer.add_edge("child", "retained")
    outer.add_edge("retained", "left")
    outer.add_edge("retained", "right")
    outer.add_edge("left", END)
    outer.add_edge("right", END)
    document = describe(outer.compile(), depth=depth)
    check(document, depth)
    facts = meaning(document)
    assert facts.pop("retained")["value"] == "all-declared"
    if depth < nesting:
        assert facts == {}
    else:
        assert facts == {
            ("child:" + "inner:" * (nesting - 1) + "router"): {
                "status": "unknown",
                "reason": "scope-not-inspected",
            }
        }
        assert any(
            gap["code"] == "expanded-subgraph-metadata"
            for gap in document["completeness"]["gaps"]
        )


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_rewritten_root_connections(depth):
    child = StateGraph(State).add_node("step", forbidden).add_node("next", forbidden)
    child.add_edge(START, "step")
    child.add_edge("step", "next")
    child.add_edge("next", END)
    outer = StateGraph(State).add_node("child", child.compile())
    outer.add_node("right", forbidden)
    outer.add_edge(START, "child")
    outer.add_edge(START, "right")
    outer.add_edge("child", END)
    outer.add_edge("right", END)
    document = describe(outer.compile(), depth=depth)
    check(document, depth)
    assert meaning(document)[START] == (
        CASES[0]["expected"]["router"]
        if depth == 0
        else {"status": "unknown", "reason": "scope-not-inspected"}
    )


def test_branch_merge_preserves_other_task_facts():
    compiled = compile_case(CASES[0])
    graph = describe(compiled)["graphs"][0]
    entry = {
        "status": "unknown",
        "reason": "entry-not-established",
        "observedRoot": False,
    }
    graph[KEY]["nodes"][0]["entry"] = entry
    module = importlib.import_module("agent_topology.langgraph._describe")
    module._branch_interpretation(compiled, compiled.get_graph(), graph, 0)
    assert graph[KEY]["nodes"][0]["entry"] == entry


@pytest.mark.parametrize("name", ["linear", "single", "mixed-unknown"])
def test_document_validator_rejects_unjustified_known_branch(name):
    case = next(case for case in CASES if case["name"] == name)
    document = describe(compile_case(case))
    node_id = "step" if name == "linear" else "router"
    document["graphs"][0][KEY]["nodes"] = [
        {
            "nodeId": node_id,
            "branch": {
                **CASES[0]["expected"]["router"],
                "evidence": {"kind": "unconditional-edges", "source": "authored-test"},
            },
        }
    ]
    assert not validate_document(document)
    assert ORACLE(document) == "invalid"


def test_hidden_dynamic_declaration_requires_producer_conformance():
    case = next(case for case in CASES if case["name"] == "dynamic-empty")
    document = describe(compile_case(case))
    assert meaning(document)["router"]["status"] == "unknown"
    # The document cannot refute this lie: only inspection of real declarations can.
    next(r for r in document["graphs"][0][KEY]["nodes"] if r["nodeId"] == "router")[
        "branch"
    ] = {
        **CASES[0]["expected"]["router"],
        "evidence": {"kind": "unconditional-edges", "source": "authored-test"},
    }
    assert ORACLE(document) == "valid"
