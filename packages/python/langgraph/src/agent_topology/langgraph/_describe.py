"""Translate a compiled LangGraph graph into the public topology document."""

from __future__ import annotations

import tomllib
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from agent_topology.spec import finalize_document

from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph

from ._compatibility import ensure_supported_langgraph_version
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
        project = Path(__file__).resolve().parents[3] / "pyproject.toml"
        metadata = tomllib.loads(project.read_text(encoding="utf-8"))["project"]
        if metadata["name"] != distribution:
            raise ValueError("source manifest does not match producer distribution")
        return metadata["version"]


def _node_document(
    node_id: str,
    node: Any,
    *,
    interrupt_before: set[str],
    interrupt_after: set[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": node_id,
        "x-langgraph": {"sentinel": node_id in {START, END}},
    }
    name = getattr(node, "name", None)
    if isinstance(name, str) and name:
        result["x-langgraph"]["name"] = name
    interrupts = [
        location
        for location, configured in (
            ("before", interrupt_before),
            ("after", interrupt_after),
        )
        if node_id in configured or ("*" in configured and node_id not in {START, END})
    ]
    if interrupts:
        result["interrupts"] = interrupts
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


def _branch_interpretation(
    compiled_graph: CompiledStateGraph, drawable: Any, graph: dict[str, Any], depth: int
) -> None:
    """Inspect root declarations; drawable connections alone never prove selection."""
    builder = compiled_graph.builder
    root_edges, _, _ = _builder_structure(compiled_graph)
    dynamic = {source for source, branches in builder.branches.items() if branches}
    dynamic.update(
        source
        for source, node in builder.nodes.items()
        if node.ends or isinstance(node.ends, dict)
    )
    extension = graph.setdefault(
        "x-topology-interpretation",
        {"version": "1", "traversalDepth": depth, "nodes": []},
    )
    records = {record["nodeId"]: record for record in extension["nodes"]}

    def mapped_identity(node_id: str) -> bool:
        return node_id in {START, END} or (
            node_id in compiled_graph.nodes
            and node_id in drawable.nodes
            and drawable.nodes[node_id].data is compiled_graph.nodes[node_id].bound
        )

    for node_id in drawable.nodes:
        outgoing = {
            (edge["target"], edge["kind"])
            for edge in graph["structure"]["edges"]
            if edge["source"] == node_id
        }
        # Compiled runnable identity establishes retained scope, never a flattened name.
        mapped = mapped_identity(node_id)
        declared = {
            (edge["target"], edge["kind"])
            for edge in root_edges
            if edge["source"] == node_id
        }
        applicable = (
            len(outgoing) >= 2
            or any(kind == "conditional" for _, kind in outgoing)
            or (mapped and node_id in dynamic)
        )
        if not applicable:
            continue
        if not mapped:
            fact = {"status": "unknown", "reason": "scope-not-inspected"}
        elif node_id in dynamic or any(kind != "direct" for _, kind in outgoing):
            fact = {"status": "unknown", "reason": "selection-not-observable"}
        elif depth > 0 and (
            outgoing != declared
            or any(not mapped_identity(target) for target, _ in outgoing)
        ):
            fact = {"status": "unknown", "reason": "scope-not-inspected"}
        else:
            fact = {
                "status": "known",
                "value": "all-declared",
                "evidence": {
                    "kind": "unconditional-edges",
                    "source": "compiled.builder.edges+branches+nodes.ends",
                },
            }
        records.setdefault(node_id, {"nodeId": node_id})["branch"] = fact
    extension["nodes"] = [records[node_id] for node_id in sorted(records)]


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
        UnsupportedLangGraphVersionError: If the installed LangGraph release has
            not passed this producer's conformance suite.
        TypeError: If ``compiled_graph`` is not a compiled LangGraph state graph,
            if ``depth`` is not an integer, or if ``strict`` is not a boolean.
        ValueError: If ``depth`` is negative.
        IncompleteTopologyError: If ``strict`` is true and the resulting document
            contains one or more graph-specific gaps. The exception's ``document``
            attribute contains the canonical incomplete document.
    """
    langgraph_version = ensure_supported_langgraph_version()

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
    interrupt_before = set(map(str, compiled_graph.interrupt_before_nodes))
    interrupt_after = set(map(str, compiled_graph.interrupt_after_nodes))
    nodes = [
        _node_document(
            str(node_id),
            node,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
        )
        for node_id, node in drawable.nodes.items()
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
    _branch_interpretation(compiled_graph, drawable, graph_document, depth)
    if isinstance(graph_name, str) and graph_name:
        graph_document["name"] = graph_name

    gaps = [
        {
            "code": "unknown-routing-targets",
            "message": "Not every destination of this router could be determined.",
            "element": {"graphId": "main", "kind": "node", "id": source},
        }
        for source in sorted(unknown_routers)
    ]
    root_node_ids = {START, END, *compiled_graph.builder.nodes}
    if depth > 0 and any(node_id not in root_node_ids for node_id in node_ids):
        gaps.append(
            {
                "code": "expanded-subgraph-metadata",
                "message": (
                    "Expanded child graphs expose drawable shape, but their join, "
                    "routing, and interrupt declarations are not fully inspected."
                ),
                "element": {"graphId": "main", "kind": "graph", "id": "main"},
            }
        )

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
                "version": langgraph_version,
            },
            "source": {"kind": "compiled-object"},
        },
        "producerLimitations": _PRODUCER_LIMITATIONS,
        "graphs": [graph_document],
        "completeness": {
            "status": "incomplete" if gaps else "complete",
            "gaps": gaps,
        },
    }
    finalized = finalize_document(document)
    if strict and finalized["completeness"]["gaps"]:
        raise IncompleteTopologyError(finalized)
    return finalized
