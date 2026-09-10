from pathlib import Path

import agent_topology.langgraph
import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


def test_langgraph_owns_only_its_namespace_portion() -> None:
    package_dir = Path(agent_topology.langgraph.__file__).parent

    assert agent_topology.langgraph.__all__ == ["describe"]
    assert not (package_dir.parent / "__init__.py").exists()


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
        set(node) <= {"id", "x-langgraph"} and set(node["x-langgraph"]) == {"name"}
        for node in graph["structure"]["nodes"]
    )


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
