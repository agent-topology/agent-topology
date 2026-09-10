import json
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Literal, TypedDict

import agent_topology.langgraph
import pytest
from agent_topology.langgraph import _compatibility
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command


class _State(TypedDict, total=False):
    value: str


def _step(_state: _State) -> dict[str, str]:
    return {}


def test_langgraph_owns_only_its_namespace_portion() -> None:
    package_dir = Path(agent_topology.langgraph.__file__).parent

    assert agent_topology.langgraph.__all__ == [
        "IncompleteTopologyError",
        "UnsupportedLangGraphVersionError",
        "describe",
    ]
    assert not (package_dir.parent / "__init__.py").exists()


def test_package_metadata_matches_evidence_backed_compatibility_contract() -> None:
    package_root = Path(__file__).parents[1]
    project = tomllib.loads(
        (package_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    contract = json.loads(
        (
            Path(agent_topology.langgraph.__file__).parent / "_compatibility.json"
        ).read_text(encoding="utf-8")
    )

    dependencies = project["project"]["dependencies"]
    spec_dependency = next(
        dependency
        for dependency in dependencies
        if dependency.startswith("agent-topology-spec")
    )
    langgraph_dependency = next(
        dependency for dependency in dependencies if dependency.startswith("langgraph")
    )
    assert project["project"]["name"] == "agent-topology-langgraph"
    assert spec_dependency == "agent-topology-spec>=0.0.0,<0.1.0"
    assert langgraph_dependency == f"langgraph{contract['metadataSpecifier']}"
    assert contract["testedVersions"] == ["1.2.10", "1.2.11"]


@pytest.mark.parametrize("installed_version", ["1.2.9", "1.2.12"])
def test_describe_rejects_langgraph_versions_outside_tested_range(
    installed_version: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_compatibility, "version", lambda _name: installed_version)

    with pytest.raises(
        agent_topology.langgraph.UnsupportedLangGraphVersionError,
        match=(
            rf"Unsupported LangGraph version {installed_version}.*"
            r'python -m pip install "langgraph>=1.2.10,<=1.2.11"'
        ),
    ) as caught:
        agent_topology.langgraph.describe(_compile_minimal_graph())

    assert caught.value.installed_version == installed_version
    assert caught.value.supported_specifier == ">=1.2.10,<=1.2.11"
    assert caught.value.tested_versions == ("1.2.10", "1.2.11")


def _compile_minimal_graph() -> CompiledStateGraph:
    builder = StateGraph(dict)
    builder.add_node("step", lambda state: state)
    builder.add_edge(START, "step")
    builder.add_edge("step", END)
    return builder.compile()


def test_describe_returns_public_spec_document() -> None:
    document = agent_topology.langgraph.describe(_compile_minimal_graph())

    assert document["topologyVersion"] == "0.1"
    assert document["provenance"]["producer"]["name"] == "agent-topology-langgraph"
    assert document["provenance"]["framework"]["name"] == "langgraph"
    assert document["structureHash"]["algorithmVersion"] == "1"
    assert document["completeness"] == {"gaps": [], "status": "complete"}
    graph = document["graphs"][0]
    assert graph["id"] == "main"
    assert graph["x-langgraph"] == {"traversalDepth": 0}
    assert [node["id"] for node in graph["structure"]["nodes"]] == [
        "__end__",
        "__start__",
        "step",
    ]
    assert graph["structure"]["entryNodeIds"] == ["__start__"]
    assert graph["structure"]["exitNodeIds"] == ["__end__"]
    assert all(
        set(node) <= {"id", "x-langgraph"}
        and set(node["x-langgraph"]) == {"name", "sentinel"}
        for node in graph["structure"]["nodes"]
    )
    sentinel_by_id = {
        node["id"]: node["x-langgraph"]["sentinel"]
        for node in graph["structure"]["nodes"]
    }
    assert sentinel_by_id == {"__end__": True, "__start__": True, "step": False}


def test_strict_describe_succeeds_with_only_producer_limitations() -> None:
    document = agent_topology.langgraph.describe(_compile_minimal_graph(), strict=True)

    assert document["producerLimitations"] == [
        {
            "code": "dynamic-interrupts",
            "message": (
                "Interrupts raised inside node bodies cannot be observed statically."
            ),
        }
    ]
    assert document["completeness"] == {"gaps": [], "status": "complete"}


def test_describe_exposes_nested_graph_depth() -> None:
    inner = _compile_minimal_graph()
    builder = StateGraph(dict)
    builder.add_node("nested", inner)
    builder.add_edge(START, "nested")
    builder.add_edge("nested", END)
    compiled = builder.compile()

    opaque = agent_topology.langgraph.describe(compiled)
    expanded = agent_topology.langgraph.describe(compiled, depth=1)

    assert {node["id"] for node in opaque["graphs"][0]["structure"]["nodes"]} == {
        "__start__",
        "nested",
        "__end__",
    }
    assert {node["id"] for node in expanded["graphs"][0]["structure"]["nodes"]} == {
        "__start__",
        "nested:step",
        "__end__",
    }
    assert expanded["graphs"][0]["x-langgraph"] == {"traversalDepth": 1}


@pytest.mark.parametrize("value", [object(), StateGraph(dict)])
def test_describe_rejects_uncompiled_inputs(value: object) -> None:
    with pytest.raises(TypeError, match="StateGraph.compile"):
        agent_topology.langgraph.describe(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("depth", [True, 1.5, "1"])
def test_describe_rejects_non_integer_depth(depth: object) -> None:
    with pytest.raises(TypeError, match="non-negative integer"):
        agent_topology.langgraph.describe(  # type: ignore[arg-type]
            _compile_minimal_graph(), depth=depth
        )


def test_describe_rejects_negative_depth() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        agent_topology.langgraph.describe(_compile_minimal_graph(), depth=-1)


@pytest.mark.parametrize("strict", [None, 0, "yes"])
def test_describe_rejects_non_boolean_strict(strict: object) -> None:
    with pytest.raises(TypeError, match="strict must be a boolean"):
        agent_topology.langgraph.describe(  # type: ignore[arg-type]
            _compile_minimal_graph(), strict=strict
        )


def _conditional_graph(*, declaration: str) -> CompiledStateGraph:
    def route(_state: _State) -> Literal["left", "right"]:
        return "left"

    def unknown_route(_state: _State) -> str:
        return "left"

    builder = StateGraph(_State)
    for node_id in ("router", "left", "right"):
        builder.add_node(node_id, _step)
    builder.add_edge(START, "router")
    if declaration == "literal":
        builder.add_conditional_edges("router", route)
    elif declaration == "path-map":
        builder.add_conditional_edges(
            "router", unknown_route, {"left-key": "left", "right-key": "right"}
        )
    else:
        builder.add_conditional_edges("router", unknown_route)
    builder.add_edge("left", END)
    builder.add_edge("right", END)
    return builder.compile()


@pytest.mark.parametrize("declaration", ["literal", "path-map"])
def test_describe_records_declared_conditional_destinations(declaration: str) -> None:
    document = agent_topology.langgraph.describe(
        _conditional_graph(declaration=declaration)
    )
    edges = document["graphs"][0]["structure"]["edges"]

    assert {(edge["source"], edge["target"], edge["kind"]) for edge in edges} >= {
        ("router", "left", "conditional"),
        ("router", "right", "conditional"),
    }
    assert document["completeness"] == {"gaps": [], "status": "complete"}


def test_describe_records_command_literal_destinations() -> None:
    def route(_state: _State) -> Command[Literal["left", "right"]]:
        return Command(goto="left")

    builder = StateGraph(_State)
    builder.add_node("router", route)
    builder.add_node("left", _step)
    builder.add_node("right", _step)
    builder.add_edge(START, "router")
    builder.add_edge("left", END)
    builder.add_edge("right", END)

    edges = agent_topology.langgraph.describe(builder.compile())["graphs"][0][
        "structure"
    ]["edges"]

    assert {(edge["source"], edge["target"], edge["kind"]) for edge in edges} >= {
        ("router", "left", "conditional"),
        ("router", "right", "conditional"),
    }


def test_describe_records_unknown_router_as_an_element_local_gap() -> None:
    document = agent_topology.langgraph.describe(_conditional_graph(declaration="none"))
    graph = document["graphs"][0]

    assert not any(edge["source"] == "router" for edge in graph["structure"]["edges"])
    assert "router" not in graph["structure"]["exitNodeIds"]
    assert document["completeness"] == {
        "gaps": [
            {
                "code": "unknown-routing-targets",
                "element": {"graphId": "main", "id": "router", "kind": "node"},
                "message": "Not every destination of this router could be determined.",
            }
        ],
        "status": "incomplete",
    }


def test_strict_describe_raises_with_canonical_incomplete_document() -> None:
    with pytest.raises(
        agent_topology.langgraph.IncompleteTopologyError,
        match="1 graph-specific gap",
    ) as raised:
        agent_topology.langgraph.describe(
            _conditional_graph(declaration="none"), strict=True
        )

    document = raised.value.document
    assert document["structureHash"]["algorithmVersion"] == "1"
    assert document["completeness"]["status"] == "incomplete"
    assert [gap["element"]["id"] for gap in document["completeness"]["gaps"]] == [
        "router"
    ]


def _join_graph(sources: list[str]) -> CompiledStateGraph:
    builder = StateGraph(_State)
    for node_id in ("left", "right", "joined"):
        builder.add_node(node_id, _step)
    builder.add_edge(START, "left")
    builder.add_edge(START, "right")
    builder.add_edge(sources, "joined")
    builder.add_edge("joined", END)
    return builder.compile()


def test_describe_keeps_multi_source_join_distinct_from_independent_edges() -> None:
    joined = agent_topology.langgraph.describe(_join_graph(["right", "left"]))
    structure = joined["graphs"][0]["structure"]

    assert structure["joins"] == [
        {
            "id": "join:left+right:joined",
            "sources": ["left", "right"],
            "target": "joined",
        }
    ]
    assert not any(edge["target"] == "joined" for edge in structure["edges"])

    independent_builder = StateGraph(_State)
    for node_id in ("left", "right", "joined"):
        independent_builder.add_node(node_id, _step)
    independent_builder.add_edge(START, "left")
    independent_builder.add_edge(START, "right")
    independent_builder.add_edge("left", "joined")
    independent_builder.add_edge("right", "joined")
    independent_builder.add_edge("joined", END)
    independent = agent_topology.langgraph.describe(independent_builder.compile())

    assert independent["graphs"][0]["structure"]["joins"] == []
    assert joined["structureHash"] != independent["structureHash"]


def test_equivalent_declaration_order_has_canonical_structure_and_hash() -> None:
    def graph(edge_order: list[tuple[str, str]]) -> CompiledStateGraph:
        builder = StateGraph(_State)
        builder.add_node("first", _step)
        builder.add_node("second", _step)
        for source, target in edge_order:
            builder.add_edge(source, target)
        return builder.compile()

    first = agent_topology.langgraph.describe(
        graph([(START, "first"), ("first", "second"), ("second", END)])
    )
    reordered = agent_topology.langgraph.describe(
        graph([("second", END), (START, "first"), ("first", "second")])
    )

    first_without_time = deepcopy(first)
    reordered_without_time = deepcopy(reordered)
    first_without_time["provenance"].pop("generatedAt")
    reordered_without_time["provenance"].pop("generatedAt")

    assert first_without_time == reordered_without_time

    first_join = agent_topology.langgraph.describe(_join_graph(["left", "right"]))
    reordered_join = agent_topology.langgraph.describe(_join_graph(["right", "left"]))
    assert first_join["graphs"] == reordered_join["graphs"]
    assert first_join["structureHash"] == reordered_join["structureHash"]
