"""Translate a compiled LangGraph graph into the public topology document."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from agent_topology.spec import finalize_document

from langgraph.graph.state import CompiledStateGraph


def _distribution_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        # Source checkouts can import the package without installed metadata.
        return "0.0.0"


def _node_document(node_id: str, node: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"id": node_id}
    name = getattr(node, "name", None)
    if isinstance(name, str) and name:
        result["x-langgraph"] = {"name": name}
    return result


def describe(
    compiled_graph: CompiledStateGraph,
    *,
    depth: int = 0,
) -> dict[str, Any]:
    """Describe a compiled LangGraph ``StateGraph`` as a topology document.

    Args:
        compiled_graph: A graph returned by ``StateGraph.compile()``.
        depth: Number of nested graph levels to expand. The default, ``0``, keeps
            subgraphs opaque. A positive value is passed to LangGraph's drawable
            graph traversal.

    Returns:
        The canonical public document representation from ``agent_topology.spec``.

    Raises:
        TypeError: If ``compiled_graph`` is not a compiled LangGraph state graph,
            or if ``depth`` is not an integer.
        ValueError: If ``depth`` is negative.
    """
    if not isinstance(compiled_graph, CompiledStateGraph):
        raise TypeError(
            "compiled_graph must be a CompiledStateGraph returned by "
            "StateGraph.compile()"
        )
    if isinstance(depth, bool) or not isinstance(depth, int):
        raise TypeError("depth must be a non-negative integer")
    if depth < 0:
        raise ValueError("depth must be a non-negative integer")

    drawable = compiled_graph.get_graph(xray=depth)
    node_ids = [str(node_id) for node_id in drawable.nodes]
    nodes = [
        _node_document(str(node_id), node) for node_id, node in drawable.nodes.items()
    ]

    edge_values = sorted(
        (
            str(edge.source),
            str(edge.target),
            "conditional" if edge.conditional else "direct",
        )
        for edge in drawable.edges
    )
    occurrence: Counter[tuple[str, str, str]] = Counter()
    edges: list[dict[str, str]] = []
    for source, target, kind in edge_values:
        key = (source, target, kind)
        occurrence[key] += 1
        edges.append(
            {
                "id": f"edge:{source}:{target}:{kind}:{occurrence[key]}",
                "source": source,
                "target": target,
                "kind": kind,
            }
        )

    targets = {edge[1] for edge in edge_values}
    sources = {edge[0] for edge in edge_values}
    graph_name = compiled_graph.get_name()
    graph_document: dict[str, Any] = {
        "id": "main",
        "structure": {
            "nodes": nodes,
            "edges": edges,
            "joins": [],
            "entryNodeIds": [node_id for node_id in node_ids if node_id not in targets],
            "exitNodeIds": [node_id for node_id in node_ids if node_id not in sources],
        },
        "x-langgraph": {"traversalDepth": depth},
    }
    if isinstance(graph_name, str) and graph_name:
        graph_document["name"] = graph_name

    document = {
        "topologyVersion": "0.1",
        "provenance": {
            "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "producer": {
                "name": "agent-topology-langgraph",
                "version": _distribution_version("agent-topology-langgraph"),
            },
            "framework": {
                "name": "langgraph",
                "version": _distribution_version("langgraph"),
            },
            "source": {"kind": "compiled-object"},
        },
        "producerLimitations": [],
        "graphs": [graph_document],
        "completeness": {"status": "complete", "gaps": []},
    }
    return finalize_document(document)
