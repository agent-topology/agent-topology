"""Ad-hoc verification of beta.5 producer behavior against the clean-installed
agent_topology_langgraph-0.1.0b5 wheel (not the source tree). Exercises:
  1. Repeated join declaration dedup (issue #182 / ADR 0015).
  2. Permuted join declaration dedup, reversed order, distinct id stability.
  3. declare_children evidence kind at depth 0/1/2 (issue #185 / ADR 0014).
  4. CLI --depth and --strict flags.
Not part of the committed test suite; run once against the qualification
venv and the output captured into the qualification evidence.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

from agent_topology.langgraph import declare_children, describe
from agent_topology.spec import canonical_json, validate_document
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class State(TypedDict):
    x: int


def _step(state: State) -> dict:
    return {"x": state["x"]}


def check_repeated_join_dedup() -> None:
    builder = StateGraph(State)
    for name in ("a", "b", "sink"):
        builder.add_node(name, _step)
    builder.add_edge(START, "a")
    builder.add_edge(START, "b")
    builder.add_edge(["a", "b"], "sink")
    builder.add_edge(["a", "b"], "sink")
    builder.add_edge("sink", END)
    document = describe(builder.compile())
    errors = validate_document(document)
    assert not errors, errors
    joins = document["graphs"][0]["structure"]["joins"]
    assert len(joins) == 1, joins
    assert joins[0]["id"] == "join:a+b:sink", joins
    print("OK repeated-join-declaration dedup ->", joins[0]["id"])


def check_permuted_join_dedup() -> None:
    builder = StateGraph(State)
    for name in ("a", "b", "sink"):
        builder.add_node(name, _step)
    builder.add_edge(START, "a")
    builder.add_edge(START, "b")
    builder.add_edge(["a", "b"], "sink")
    builder.add_edge(["b", "a"], "sink")
    builder.add_edge("sink", END)
    document = describe(builder.compile())
    errors = validate_document(document)
    assert not errors, errors
    joins = document["graphs"][0]["structure"]["joins"]
    assert len(joins) == 1, joins
    assert joins[0]["id"] == "join:a+b:sink", joins
    print("OK permuted-join-declaration dedup ->", joins[0]["id"])


def build_leaf() -> CompiledStateGraph:
    b = StateGraph(State)
    b.add_node("step", _step)
    b.add_edge(START, "step")
    b.add_edge("step", END)
    return b.compile(name="leaf")


def build_mid(leaf: CompiledStateGraph) -> CompiledStateGraph:
    def _call_leaf(state: State) -> dict:
        return leaf.invoke(state)

    b = StateGraph(State)
    b.add_node("grand", _call_leaf)
    b.add_edge(START, "grand")
    b.add_edge("grand", END)
    compiled = b.compile(name="mid")
    return declare_children(compiled, {"grand": leaf})


KEY = "x-topology-interpretation"


def _node(graph: dict, node_id: str) -> dict:
    return next(n for n in graph["structure"]["nodes"] if n["id"] == node_id)


def _subgraph_fact(graph: dict, node_id: str) -> dict:
    return next(
        record["subgraph"]
        for record in graph[KEY]["nodes"]
        if record["nodeId"] == node_id and "subgraph" in record
    )


def check_declare_children_depths() -> None:
    leaf = build_leaf()
    mid = build_mid(leaf)

    d0 = describe(mid, graph_id="main")
    main0 = next(g for g in d0["graphs"] if g["id"] == "main")
    assert "subgraphId" not in _node(main0, "grand"), main0
    fact0 = _subgraph_fact(main0, "grand")
    assert fact0 == {
        "status": "known",
        "value": "opaque-child",
        "evidence": {
            "kind": "declared-child-call",
            "source": "compiled.__agent_topology_children__",
        },
    }, fact0
    print("OK declare_children depth=0 -> opaque-child, declared-child-call evidence")

    d1 = describe(mid, graph_id="main", depth=1)
    graph_ids = sorted(g["id"] for g in d1["graphs"])
    assert graph_ids == ["main", "main:grand"], graph_ids
    main1 = next(g for g in d1["graphs"] if g["id"] == "main")
    node = _node(main1, "grand")
    assert node["subgraphId"] == "main:grand", node
    fact1 = _subgraph_fact(main1, "grand")
    assert fact1 == {
        "status": "known",
        "value": "materialized-child",
        "evidence": {
            "kind": "materialized-subgraph-reference",
            "source": "graphs[].id+node.subgraphId",
        },
    }, fact1
    print(
        "OK declare_children depth=1 -> subgraphId + materialized-subgraph-reference evidence"
    )

    errors = validate_document(d1)
    assert not errors, errors
    print("OK declare_children depth=1 document validates")

    child_document = describe(leaf, graph_id="main:grand")
    child_node_ids = sorted(
        n["id"] for n in child_document["graphs"][0]["structure"]["nodes"]
    )
    grandchild_graph = next(g for g in d1["graphs"] if g["id"] == "main:grand")
    materialized_node_ids = sorted(
        n["id"] for n in grandchild_graph["structure"]["nodes"]
    )
    assert child_node_ids == materialized_node_ids, (child_node_ids, materialized_node_ids)
    print("OK materialized child node-id set matches the child's own standalone describe()")


def check_cli_depth_and_strict() -> None:
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        graph_file = temp / "graph.py"
        graph_file.write_text(
            """
from langgraph.graph import END, START, StateGraph
from agent_topology.langgraph import declare_children


def leaf_step(state):
    return {"x": state["x"]}


def build_leaf():
    b = StateGraph(dict)
    b.add_node("step", leaf_step)
    b.add_edge(START, "step")
    b.add_edge("step", END)
    return b.compile(name="leaf")


_leaf = build_leaf()


def _call_leaf(state):
    return _leaf.invoke(state)


_b = StateGraph(dict)
_b.add_node("grand", _call_leaf)
_b.add_edge(START, "grand")
_b.add_edge("grand", END)
graph = declare_children(_b.compile(name="mid"), {"grand": _leaf})
""",
            encoding="utf-8",
        )
        out_depth1 = temp / "depth1.json"
        executable = Path(sys.executable).with_name("agt")
        subprocess.run(
            [
                str(executable),
                "describe",
                f"{graph_file}:graph",
                "--depth",
                "1",
                "--strict",
                "--out",
                str(out_depth1),
            ],
            check=True,
        )
        document = json.loads(out_depth1.read_text())
        assert canonical_json(document) + "\n" == out_depth1.read_text()
        graph_ids = sorted(g["id"] for g in document["graphs"])
        assert graph_ids == ["main", "main:grand"], graph_ids
        print("OK CLI --depth 1 --strict -> ", graph_ids)


if __name__ == "__main__":
    check_repeated_join_dedup()
    check_permuted_join_dedup()
    check_declare_children_depths()
    check_cli_depth_and_strict()
    print("ALL INSTALLED-ARTIFACT BEHAVIOR CHECKS PASSED")
