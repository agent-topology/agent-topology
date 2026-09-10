"""Validation against the packaged agent-topology document contract."""

from __future__ import annotations

import json
from collections.abc import Iterable
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


def load_schema() -> dict[str, Any]:
    """Load and return a fresh copy of the packaged canonical JSON Schema."""
    resource = files(__package__).joinpath("agent-topology.schema.json")
    if not resource.is_file():
        development_schema = next(
            (
                parent / "spec" / "agent-topology.schema.json"
                for parent in Path(__file__).resolve().parents
                if (parent / "spec" / "agent-topology.schema.json").is_file()
            ),
            None,
        )
        if development_schema is not None:
            return json.loads(development_schema.read_text(encoding="utf-8"))
    return json.loads(resource.read_text(encoding="utf-8"))


def _path(parts: Iterable[str | int]) -> str:
    result = "$"
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}"
    return result


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return duplicates


def _reference_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    graphs = document["graphs"]
    graph_ids = [graph["id"] for graph in graphs]

    for graph_id in sorted(_duplicates(graph_ids)):
        errors.append(f"$.graphs: duplicate graph id {graph_id!r}")

    graph_by_id = {graph["id"]: graph for graph in graphs}
    element_ids: dict[str, dict[str, set[str]]] = {}

    for graph_index, graph in enumerate(graphs):
        graph_path = f"$.graphs[{graph_index}]"
        structure_path = f"{graph_path}.structure"
        structure = graph["structure"]
        node_ids = [node["id"] for node in structure["nodes"]]
        edge_ids = [edge["id"] for edge in structure["edges"]]
        join_ids = [join["id"] for join in structure["joins"]]
        known_nodes = set(node_ids)
        element_ids[graph["id"]] = {
            "graph": {graph["id"]},
            "node": known_nodes,
            "edge": set(edge_ids),
            "join": set(join_ids),
        }

        for kind, ids in (("node", node_ids), ("edge", edge_ids), ("join", join_ids)):
            for duplicate in sorted(_duplicates(ids)):
                errors.append(
                    f"{structure_path}.{kind}s: duplicate {kind} id {duplicate!r}"
                )

        def require_node(reference: str, path: str) -> None:
            if reference not in known_nodes:
                errors.append(f"{path}: unknown node id {reference!r}")

        for node_index, node in enumerate(structure["nodes"]):
            subgraph_id = node.get("subgraphId")
            if subgraph_id is not None and subgraph_id not in graph_by_id:
                errors.append(
                    f"{structure_path}.nodes[{node_index}].subgraphId: "
                    f"unknown graph id {subgraph_id!r}"
                )

        for edge_index, edge in enumerate(structure["edges"]):
            require_node(edge["source"], f"{structure_path}.edges[{edge_index}].source")
            require_node(edge["target"], f"{structure_path}.edges[{edge_index}].target")

        for join_index, join in enumerate(structure["joins"]):
            for source_index, source in enumerate(join["sources"]):
                require_node(
                    source,
                    f"{structure_path}.joins[{join_index}].sources[{source_index}]",
                )
            require_node(join["target"], f"{structure_path}.joins[{join_index}].target")

        for field in ("entryNodeIds", "exitNodeIds"):
            for reference_index, reference in enumerate(structure[field]):
                require_node(reference, f"{structure_path}.{field}[{reference_index}]")

    gaps = document["completeness"]["gaps"]
    expected_status = "complete" if not gaps else "incomplete"
    actual_status = document["completeness"]["status"]
    if actual_status != expected_status:
        errors.append(
            "$.completeness.status: must be "
            f"{expected_status!r} when gaps contains {len(gaps)} item(s)"
        )

    for gap_index, gap in enumerate(gaps):
        element = gap["element"]
        path = f"$.completeness.gaps[{gap_index}].element"
        graph_id = element["graphId"]
        if graph_id not in element_ids:
            errors.append(f"{path}.graphId: unknown graph id {graph_id!r}")
            continue
        if element["id"] not in element_ids[graph_id][element["kind"]]:
            errors.append(
                f"{path}.id: unknown {element['kind']} id {element['id']!r} "
                f"in graph {graph_id!r}"
            )

    return errors


def validate_document(document: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic, path-qualified errors for one topology document."""
    if schema is None:
        schema = load_schema()
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors = sorted(
        validator.iter_errors(document),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    errors = [
        f"{_path(error.absolute_path)}: {error.message}" for error in schema_errors
    ]
    if errors or not isinstance(document, dict):
        return errors
    return _reference_errors(document)
