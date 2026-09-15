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


def _mapped_compiled_child(
    compiled_graph: CompiledStateGraph, drawable: Any, node_id: str
) -> CompiledStateGraph | None:
    """Return the compiled child confirmed bound at node_id, mapped by runtime
    identity, never by display name or wrapper inspection."""
    runtime_node = compiled_graph.nodes.get(node_id)
    if runtime_node is None or drawable.nodes[node_id].data is not runtime_node.bound:
        return None
    bound = runtime_node.bound
    return bound if isinstance(bound, CompiledStateGraph) else None


def _interpretation_version(graph: dict[str, Any]) -> str:
    """A graph advances to revision 2 only where it materializes a child."""
    has_materialized_child = any(
        "subgraphId" in node for node in graph["structure"]["nodes"]
    )
    return "2" if has_materialized_child else "1"


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
        {
            "version": _interpretation_version(graph),
            "traversalDepth": depth,
            "nodes": [],
        },
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


def _subgraph_interpretation(
    compiled_graph: CompiledStateGraph, drawable: Any, graph: dict[str, Any], depth: int
) -> None:
    """Confirm exposed compiled children without looking inside user callables."""
    extension = graph.setdefault(
        "x-topology-interpretation",
        {
            "version": _interpretation_version(graph),
            "traversalDepth": depth,
            "nodes": [],
        },
    )
    records = {record["nodeId"]: record for record in extension["nodes"]}
    for node in graph["structure"]["nodes"]:
        node_id = node["id"]
        if node_id in {START, END}:
            continue
        if "subgraphId" in node:
            fact = {
                "status": "known",
                "value": "materialized-child",
                "evidence": {
                    "kind": "materialized-subgraph-reference",
                    "source": "graphs[].id+node.subgraphId",
                },
            }
            records.setdefault(node_id, {"nodeId": node_id})["subgraph"] = fact
            continue
        runtime_node = compiled_graph.nodes.get(node_id)
        mapped = (
            runtime_node is not None
            and drawable.nodes[node_id].data is runtime_node.bound
        )
        if not mapped:
            fact = {"status": "unknown", "reason": "scope-not-inspected"}
        elif isinstance(runtime_node.bound, CompiledStateGraph):
            fact = {
                "status": "known",
                "value": "opaque-child",
                "evidence": {
                    "kind": "compiled-child",
                    "source": "compiled.nodes.bound",
                },
            }
        else:
            # Functions and wrappers may hide child invocation; absence is not proved.
            fact = {"status": "unknown", "reason": "identity-unavailable"}
        records.setdefault(node_id, {"nodeId": node_id})["subgraph"] = fact
    extension["nodes"] = [records[node_id] for node_id in sorted(records)]


def _node_identity(
    compiled_graph: CompiledStateGraph, drawable: Any, node_id: str, depth: int
) -> dict[str, Any]:
    """Inspect framework ownership for sentinel and entry interpretations."""
    builder_nodes = compiled_graph.builder.nodes
    data = drawable.nodes[node_id].data
    runtime_node = compiled_graph.nodes.get(node_id)
    mapped = runtime_node is not None and data is runtime_node.bound
    fact: dict[str, Any] = {
        "status": "unknown",
        "reason": "scope-not-inspected" if depth > 0 else "identity-unavailable",
    }
    if node_id in {START, END}:
        fact["reason"] = "identity-unavailable"
        owned = (
            compiled_graph.input_channels == START
            and node_id not in builder_nodes
            and (
                (node_id == START and mapped)
                or (node_id == END and runtime_node is None and data is None)
            )
        )
        if owned:
            fact = {
                "status": "known",
                "value": "start" if node_id == START else "end",
                "evidence": {
                    "kind": "framework-sentinel",
                    "source": (
                        "compiled.input_channels+nodes+get_graph.reserved-sentinels"
                    ),
                },
            }
    elif node_id in builder_nodes and mapped:
        fact = {
            "status": "known",
            "value": "ordinary",
            "evidence": {
                "kind": "ordinary-node",
                "source": "compiled.builder.nodes+nodes.bound",
            },
        }
    return fact


def _sentinel_interpretation(
    compiled_graph: CompiledStateGraph, drawable: Any, graph: dict[str, Any], depth: int
) -> None:
    """Use reserved framework identity and positive root-node membership."""
    extension = graph.setdefault(
        "x-topology-interpretation",
        {
            "version": _interpretation_version(graph),
            "traversalDepth": depth,
            "nodes": [],
        },
    )
    records = {record["nodeId"]: record for record in extension["nodes"]}
    for node in graph["structure"]["nodes"]:
        node_id = node["id"]
        fact = _node_identity(compiled_graph, drawable, node_id, depth)
        records.setdefault(node_id, {"nodeId": node_id})["sentinel"] = fact
    extension["nodes"] = [records[node_id] for node_id in sorted(records)]


def _entry_interpretation(
    compiled_graph: CompiledStateGraph, drawable: Any, graph: dict[str, Any], depth: int
) -> None:
    """Separate snapshot connectivity from affirmative framework entry evidence."""
    extension = graph.setdefault(
        "x-topology-interpretation",
        {
            "version": _interpretation_version(graph),
            "traversalDepth": depth,
            "nodes": [],
        },
    )
    records = {record["nodeId"]: record for record in extension["nodes"]}
    targets = {edge["target"] for edge in graph["structure"]["edges"]} | {
        join["target"] for join in graph["structure"]["joins"]
    }
    for node in graph["structure"]["nodes"]:
        node_id = node["id"]
        identity = _node_identity(compiled_graph, drawable, node_id, depth)
        fact: dict[str, Any] = {
            "observedRoot": node_id not in targets,
            "status": "unknown",
            "reason": "entry-not-established"
            if identity["status"] == "known" or depth == 0
            else "scope-not-inspected",
        }
        if identity.get("value") in {"start", "end"}:
            fact = {
                "observedRoot": node_id not in targets,
                "status": "known",
                "value": "confirmed" if identity["value"] == "start" else "not-entry",
                "evidence": {
                    "kind": "framework-entry",
                    "source": identity["evidence"]["source"],
                },
            }
        records.setdefault(node_id, {"nodeId": node_id})["entry"] = fact
    extension["nodes"] = [records[node_id] for node_id in sorted(records)]


def _extract_graph(
    compiled_graph: CompiledStateGraph,
    graph_id: str,
    remaining_depth: int,
    assigned_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build one graph and materialize its confirmed compiled children within
    the remaining depth budget, depth-first in sorted-sibling order.

    Returns ``(graphs, gaps)``: ``graphs[0]`` is this graph, followed by every
    graph materialized beneath it in traversal order; ``gaps`` covers this
    graph and everything materialized beneath it.
    """
    drawable = compiled_graph.get_graph(xray=0)
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
    edges, joins, unknown_routers = _builder_structure(compiled_graph)

    targets = {edge["target"] for edge in edges} | {join["target"] for join in joins}
    sources = (
        {edge["source"] for edge in edges}
        | {source for join in joins for source in join["sources"]}
        | unknown_routers
    )
    graph_name = compiled_graph.get_name()
    graph_document: dict[str, Any] = {
        "id": graph_id,
        "structure": {
            "nodes": nodes,
            "edges": edges,
            "joins": joins,
            "entryNodeIds": [node_id for node_id in node_ids if node_id not in targets],
            "exitNodeIds": [node_id for node_id in node_ids if node_id not in sources],
        },
        "x-langgraph": {"traversalDepth": remaining_depth},
    }
    if isinstance(graph_name, str) and graph_name:
        graph_document["name"] = graph_name

    gaps = [
        {
            "code": "unknown-routing-targets",
            "message": "Not every destination of this router could be determined.",
            "element": {"graphId": graph_id, "kind": "node", "id": source},
        }
        for source in sorted(unknown_routers)
    ]

    descendants: list[dict[str, Any]] = []
    if remaining_depth > 0:
        node_lookup = {node["id"]: node for node in nodes}
        for node_id in sorted(compiled_graph.nodes):
            child = _mapped_compiled_child(compiled_graph, drawable, node_id)
            if child is None:
                continue
            derived_id = f"{graph_id}:{node_id}"
            if derived_id in assigned_ids:
                gaps.append(
                    {
                        "code": "child-graph-id-collision",
                        "message": (
                            "A materialized child graph id would collide with "
                            "an existing graph id; the child was left opaque."
                        ),
                        "element": {"graphId": graph_id, "kind": "node", "id": node_id},
                    }
                )
                continue
            assigned_ids.add(derived_id)
            node_lookup[node_id]["subgraphId"] = derived_id
            child_graphs, child_gaps = _extract_graph(
                child, derived_id, remaining_depth - 1, assigned_ids
            )
            descendants.extend(child_graphs)
            gaps.extend(child_gaps)

    _branch_interpretation(compiled_graph, drawable, graph_document, remaining_depth)
    _subgraph_interpretation(compiled_graph, drawable, graph_document, remaining_depth)
    _sentinel_interpretation(compiled_graph, drawable, graph_document, remaining_depth)
    _entry_interpretation(compiled_graph, drawable, graph_document, remaining_depth)

    return [graph_document, *descendants], gaps


def describe(
    compiled_graph: CompiledStateGraph,
    *,
    graph_id: str = "main",
    depth: int = 0,
    strict: bool = False,
) -> dict[str, Any]:
    """Describe a compiled LangGraph ``StateGraph`` as a topology document.

    Args:
        compiled_graph: A graph returned by ``StateGraph.compile()``.
        graph_id: Document-local identifier for the graph. Callers composing
            producer outputs should supply a distinct stable value for each graph.
        depth: Number of nested graph levels to materialize as their own
            addressable ``graphs[]`` entries. The default, ``0``, keeps
            subgraphs opaque, unchanged from prior releases. ``depth = N``
            materializes levels ``1..N``; level ``N``'s own children remain
            governed by the unchanged depth-0 opaque-child contract. A node
            holding a confirmed compiled child always keeps its own id in its
            containing graph, at every depth.
        strict: Raise :class:`IncompleteTopologyError` when graph-specific gaps
            are present. Producer limitations do not cause strict extraction to fail.

    Returns:
        The canonical public document representation from ``agent_topology.spec``.

    Raises:
        UnsupportedLangGraphVersionError: If the installed LangGraph release has
            not passed this producer's conformance suite.
        TypeError: If ``compiled_graph`` is not a compiled LangGraph state graph,
            if ``graph_id`` is not a string, if ``depth`` is not an integer, or if
            ``strict`` is not a boolean.
        ValueError: If ``graph_id`` is empty or ``depth`` is negative.
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
    if not isinstance(graph_id, str):
        raise TypeError("graph_id must be a non-empty string")
    if not graph_id:
        raise ValueError("graph_id must be a non-empty string")
    if isinstance(depth, bool) or not isinstance(depth, int):
        raise TypeError("depth must be a non-negative integer")
    if depth < 0:
        raise ValueError("depth must be a non-negative integer")
    if not isinstance(strict, bool):
        raise TypeError("strict must be a boolean")

    graphs, gaps = _extract_graph(compiled_graph, graph_id, depth, {graph_id})

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
        "graphs": graphs,
        "completeness": {
            "status": "incomplete" if gaps else "complete",
            "gaps": gaps,
        },
    }
    finalized = finalize_document(document)
    if strict and finalized["completeness"]["gaps"]:
        raise IncompleteTopologyError(finalized)
    return finalized
