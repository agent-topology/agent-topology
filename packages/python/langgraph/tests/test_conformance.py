from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, TypedDict

import agent_topology.langgraph
import pytest
from agent_topology.spec import canonicalize_document
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

FIXTURES_DIR = Path(__file__).parents[4] / "conformance" / "fixtures"
EXPECTED_CASES = {
    "conditional-routing",
    "independent-incoming-edges",
    "interrupt-before",
    "join-permuted-sources",
    "join-repeated-declaration",
    "linear-flow",
    "loop",
    "multi-source-join",
    "nested-subgraph",
    "parallel-fanout",
    "unknown-routing-targets",
}


class _State(TypedDict, total=False):
    value: str


def _step(_state: _State) -> dict[str, str]:
    return {}


def _node_id(value: str) -> str:
    return {"$start": START, "$end": END}.get(value, value)


def _compile_fixture(recipe: dict[str, Any]) -> CompiledStateGraph:
    builder = StateGraph(_State)
    for node in recipe["nodes"]:
        runnable = _compile_fixture(node["subgraph"]) if "subgraph" in node else _step
        builder.add_node(node["id"], runnable)

    for edge in recipe.get("directEdges", []):
        builder.add_edge(_node_id(edge["source"]), _node_id(edge["target"]))

    for route in recipe.get("conditionalRoutes", []):
        targets = route["targets"]

        def choose_target(
            _state: _State,
            *,
            first_target: str = _node_id(targets[0]) if targets else END,
        ) -> str:
            return first_target

        path_map = None
        if targets is not None:
            normalized_targets = [_node_id(target) for target in targets]
            path_map = {target: target for target in normalized_targets}
        builder.add_conditional_edges(route["source"], choose_target, path_map)

    for join in recipe.get("joins", []):
        builder.add_edge(join["sources"], join["target"])

    return builder.compile(
        interrupt_before=recipe.get("interruptBefore"),
        interrupt_after=recipe.get("interruptAfter"),
    )


def _without_extensions(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_extensions(item)
            for key, item in value.items()
            if not key.startswith("x-")
        }
    if isinstance(value, list):
        return [_without_extensions(item) for item in value]
    return value


def _normalize_producer_document(document: dict[str, Any], case: str) -> dict[str, Any]:
    normalized = _without_extensions(deepcopy(document))
    normalized["provenance"] = {
        "framework": {"name": "conformance-fixture", "version": "1"},
        "generatedAt": "2000-01-01T00:00:00Z",
        "producer": {"name": "agent-topology-conformance", "version": "1"},
        "source": {"kind": "conformance-fixture", "locator": case},
    }
    normalized["producerLimitations"] = []
    for graph in normalized["graphs"]:
        graph.pop("name", None)
    return canonicalize_document(normalized)


CASES = sorted(path.name for path in FIXTURES_DIR.iterdir() if path.is_dir())


def test_fixture_inventory_covers_required_graph_meanings() -> None:
    assert set(CASES) == EXPECTED_CASES


@pytest.mark.parametrize("case", CASES)
def test_langgraph_consumes_shared_fixture(case: str) -> None:
    fixture_dir = FIXTURES_DIR / case
    recipe = json.loads((fixture_dir / "fixture.json").read_text(encoding="utf-8"))
    expected = json.loads((fixture_dir / "expected.json").read_text(encoding="utf-8"))

    actual = agent_topology.langgraph.describe(_compile_fixture(recipe))

    assert _normalize_producer_document(actual, case) == expected
