"""ADR 0014, probe 3 of 3: with the explicit construction-time contract
(`declare_children`), does `describe()` -- patched with one additional
evidence branch -- materialize the wrapped child correctly under ADR 0012
(depth budget, call-site ids, reuse, unknown fallback), and does the
resulting document still validate under the real spec validator, including
strict mode, at every depth?

This does not modify packages/python/langgraph/src; it monkeypatches the one
function ADR 0012 already isolates (`_mapped_compiled_child`) in-process, to
prove the shape of the change before #180 wires it in for real. Run with:

    rtk uv run --project packages/python/langgraph --group test python -B \
        docs/research/internal-consumer/wrapped-child-contract-2026-09-17/probe_materialization.py
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

from agent_topology.langgraph import _describe as d
from agent_topology.spec import validate_document
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


def declare_children(
    compiled_graph: CompiledStateGraph, children: Mapping[str, CompiledStateGraph]
) -> CompiledStateGraph:
    """Proposed topology-owned helper (ADR 0014). Explicit, construction-time,
    and identity-based: the factory that already holds every child object
    states, once, which node id invokes which compiled child. No source or
    closure inspection is involved; this is a no-op at runtime."""
    unknown = sorted(set(children) - set(compiled_graph.nodes))
    if unknown:
        raise ValueError(f"declare_children: not a node id in this graph: {unknown}")
    compiled_graph.__agent_topology_children__ = dict(children)
    return compiled_graph


_original_mapped = d._mapped_compiled_child


def patched_mapped_compiled_child(compiled_graph, drawable, node_id):
    """The proposed extension to _describe._mapped_compiled_child: try the
    existing direct-bound check first, then fall back to a declared child."""
    child = _original_mapped(compiled_graph, drawable, node_id)
    if child is not None:
        return child
    runtime_node = compiled_graph.nodes.get(node_id)
    if runtime_node is None or drawable.nodes[node_id].data is not runtime_node.bound:
        return None
    declared = getattr(compiled_graph, "__agent_topology_children__", {})
    candidate = declared.get(node_id)
    return candidate if isinstance(candidate, CompiledStateGraph) else None


d._mapped_compiled_child = patched_mapped_compiled_child


class LeafState(TypedDict):
    raw_input: dict
    result: dict | None


def leaf_step(state: LeafState) -> dict:
    return {"result": {"ok": True}}


def build_leaf() -> CompiledStateGraph:
    b = StateGraph(LeafState)
    b.add_node("step", leaf_step)
    b.add_edge(START, "step")
    b.add_edge("step", END)
    return b.compile(name="leaf")


class MidState(TypedDict):
    raw_input: dict
    result: dict | None


def build_mid(leaf: CompiledStateGraph) -> CompiledStateGraph:
    def _call_leaf(state: MidState) -> dict:
        final = leaf.invoke({"raw_input": {}, "result": None})
        return {"result": final["result"]}

    b = StateGraph(MidState)
    b.add_node("grand", _call_leaf)
    b.add_edge(START, "grand")
    b.add_edge("grand", END)
    compiled = b.compile(name="mid")
    return declare_children(compiled, {"grand": leaf})


class RootState(TypedDict):
    entry: dict


def build_root(mid: CompiledStateGraph, leaf: CompiledStateGraph) -> CompiledStateGraph:
    def _call_mid(state: RootState) -> dict:
        final = mid.invoke({"raw_input": {}, "result": None})
        return {"entry": {**state["entry"], "sub": final["result"]}}

    def _call_leaf(key: str):
        def _fn(state: RootState) -> dict:
            final = leaf.invoke({"raw_input": {}, "result": None})
            return {"entry": {**state["entry"], key: final["result"]}}

        return _fn

    b = StateGraph(RootState)
    b.add_node("sub", _call_mid)
    # two more call sites reusing the SAME leaf object as siblings -- the
    # "multiple uses of one child" minimum case.
    b.add_node("left", _call_leaf("left"))
    b.add_node("right", _call_leaf("right"))
    b.add_node(
        "plain", lambda state: {"entry": state["entry"]}
    )  # unknown fallback: not declared
    b.add_edge(START, "sub")
    b.add_edge("sub", "left")
    b.add_edge("left", "right")
    b.add_edge("right", "plain")
    b.add_edge("plain", END)
    compiled = b.compile(name="root")
    return declare_children(compiled, {"sub": mid, "left": leaf, "right": leaf})


if __name__ == "__main__":
    leaf = build_leaf()
    mid = build_mid(leaf)
    root = build_root(mid, leaf)

    for depth in (0, 1, 2):
        doc = d.describe(root, graph_id="main", depth=depth, strict=True)
        validate_document(doc)
        print(f"--- depth={depth} (validate_document passed, strict=True passed) ---")
        print("graph ids:", [g["id"] for g in doc["graphs"]])
        for g in doc["graphs"]:
            subgraph_nodes = [
                n["id"] for n in g["structure"]["nodes"] if "subgraphId" in n
            ]
            print(f"  {g['id']} materialized-parent nodes:", subgraph_nodes)
        print("gaps:", [gp["code"] for gp in doc["completeness"]["gaps"]])
        print("completeness:", doc["completeness"]["status"])
        main_graph = next(g for g in doc["graphs"] if g["id"] == "main")
        ext = main_graph.get("x-topology-interpretation", {})
        facts = {r["nodeId"]: r.get("subgraph") for r in ext.get("nodes", [])}
        for nid in ("sub", "left", "right", "plain"):
            print(f"  subgraph fact[{nid}] =", facts.get(nid))
        print()

    assert (
        d.describe(root, graph_id="main", depth=1)["graphs"][1]["id"]
        != d.describe(root, graph_id="main", depth=1)["graphs"][2]["id"]
    )

    # Unknown-declaration guard: declaring a node id that doesn't exist fails loud.
    try:
        declare_children(build_leaf(), {"nope": leaf})
    except ValueError as exc:
        print("declare_children rejects unknown node id as expected:", exc)
    else:
        raise AssertionError("expected declare_children to reject an unknown node id")

    print("all assertions passed")
