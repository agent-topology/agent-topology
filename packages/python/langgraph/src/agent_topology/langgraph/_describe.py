"""Translate a compiled LangGraph graph into the public topology document."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from agent_topology.spec import finalize_document

from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph

from ._exceptions import IncompleteTopologyError

_PRODUCER_LIMITATIONS = [
    {
        "code": "dynamic-interrupts",
        "message": (
            "Interrupts raised inside node bodies cannot be observed statically."
        ),
    }
]


def _distribution_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        # Source checkouts can import the package without installed metadata.
        return "0.0.0"


def _node_document(node_id: str, node: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": node_id,
        "x-langgraph": {"sentinel": node_id in {START, END}},
    }
    name = getattr(node, "name", None)
    if isinstance(name, str) and name:
        result["x-langgraph"]["name"] = name
    return result


def _edge_documents(
    values: list[tuple[str, str, str]],
) -> list[dict[str, str]]:
    occurrence: Counter[tuple[str, str, str]] = Counter()
    edges: list[dict[str, str]] = []
    for source, target, kind in sorted(values):
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
    return edges


def _builder_structure(
    compiled_graph: CompiledStateGraph,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, Any]],
    set[str],
]:
    """Read declarations that LangGraph's drawable graph can flatten or invent."""
    builder = compiled_graph.builder
    edge_values = [
        (str(source), str(target), "direct") for source, target in builder.edges
    ]
    unknown_routers: set[str] = set()

    for source, branches in builder.branches.items():
        for branch in branches.values():
            if branch.ends is None:
                unknown_routers.add(str(source))
                continue
            edge_values.extend(
                (str(source), str(target), "conditional")
                for target in branch.ends.values()
            )

    for source, node in builder.nodes.items():
        edge_values.extend(
            (str(source), str(target), "conditional") for target in node.ends
        )

    joins = [
        {
            "id": f"join:{'+'.join(sorted(map(str, sources)))}:{target}",
            "sources": sorted(map(str, sources)),
            "target": str(target),
        }
        for sources, target in builder.waiting_edges
    ]
    return _edge_documents(edge_values), joins, unknown_routers


def _drawable_structure(
    compiled_graph: CompiledStateGraph,
    drawable: Any,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], set[str]]:
    """Preserve expanded drawable topology while correcting visible root metadata."""
    builder_edges, builder_joins, unknown_routers = _builder_structure(compiled_graph)
    direct_declarations = {
        (edge["source"], edge["target"])
        for edge in builder_edges
        if edge["kind"] == "direct"
    }
    represented_joins = [
        join
        for join in builder_joins
        if set(join["sources"] + [join["target"]]) <= set(drawable.nodes)
    ]
    joined_pairs = {
        (source, join["target"])
        for join in represented_joins
        for source in join["sources"]
    }
    edge_values = [
        (
            str(edge.source),
            str(edge.target),
            "conditional" if edge.conditional else "direct",
        )
        for edge in drawable.edges
        if (str(edge.source), str(edge.target)) not in joined_pairs
        and not (
            str(edge.source) in unknown_routers
            and (str(edge.source), str(edge.target)) not in direct_declarations
        )
    ]
    return _edge_documents(edge_values), represented_joins, unknown_routers


def describe(
    compiled_graph: CompiledStateGraph,
    *,
    depth: int = 0,
    strict: bool = False,
) -> dict[str, Any]:
    """Describe a compiled LangGraph ``StateGraph`` as a topology document.

    Args:
        compiled_graph: A graph returned by ``StateGraph.compile()``.
        depth: Number of nested graph levels to expand. The default, ``0``, keeps
            subgraphs opaque. A positive value is passed to LangGraph's drawable
            graph traversal.
        strict: Raise :class:`IncompleteTopologyError` when graph-specific gaps
            are present. Producer limitations do not cause strict extraction to fail.

    Returns:
        The canonical public document representation from ``agent_topology.spec``.

    Raises:
        TypeError: If ``compiled_graph`` is not a compiled LangGraph state graph,
            if ``depth`` is not an integer, or if ``strict`` is not a boolean.
        ValueError: If ``depth`` is negative.
        IncompleteTopologyError: If ``strict`` is true and the resulting document
            contains one or more graph-specific gaps. The exception's ``document``
            attribute contains the canonical incomplete document.
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
    if not isinstance(strict, bool):
        raise TypeError("strict must be a boolean")

    drawable = compiled_graph.get_graph(xray=depth)
    node_ids = [str(node_id) for node_id in drawable.nodes]
    nodes = [
        _node_document(str(node_id), node) for node_id, node in drawable.nodes.items()
    ]

    if depth == 0:
        edges, joins, unknown_routers = _builder_structure(compiled_graph)
    else:
        edges, joins, unknown_routers = _drawable_structure(compiled_graph, drawable)

    targets = {edge["target"] for edge in edges} | {join["target"] for join in joins}
    sources = (
        {edge["source"] for edge in edges}
        | {source for join in joins for source in join["sources"]}
        | unknown_routers
    )
    graph_name = compiled_graph.get_name()
    graph_document: dict[str, Any] = {
        "id": "main",
        "structure": {
            "nodes": nodes,
            "edges": edges,
            "joins": joins,
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
        "producerLimitations": _PRODUCER_LIMITATIONS,
        "graphs": [graph_document],
        "completeness": {
            "status": "incomplete" if unknown_routers else "complete",
            "gaps": [
                {
                    "code": "unknown-routing-targets",
                    "message": (
                        "Not every destination of this router could be determined."
                    ),
                    "element": {"graphId": "main", "kind": "node", "id": source},
                }
                for source in sorted(unknown_routers)
            ],
        },
    }
    finalized = finalize_document(document)
    if strict and finalized["completeness"]["gaps"]:
        raise IncompleteTopologyError(finalized)
    return finalized
