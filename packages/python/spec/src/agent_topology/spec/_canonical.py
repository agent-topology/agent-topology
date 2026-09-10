"""Canonical document output and versioned structural hashing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

STRUCTURE_HASH_ALGORITHM = "sha256"
STRUCTURE_HASH_ALGORITHM_VERSION = "1"

_NODE_HASH_FIELDS = ("id", "type", "subgraphId", "interrupts")
_EDGE_HASH_FIELDS = ("id", "source", "target", "kind")
_JOIN_HASH_FIELDS = ("id", "sources", "target")


def _ordered(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _ordered(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_ordered(item) for item in value]
    return value


def _sort_key(value: Any) -> str:
    return json.dumps(
        _ordered(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonicalize_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical copy of a topology document without mutating the input.

    Contract-defined structural collections are sets and are sorted here. Arrays in
    extensions and descriptive fields retain their order because the core contract
    does not define their semantics.
    """
    canonical = deepcopy(dict(document))

    for graph in canonical.get("graphs", []):
        structure = graph["structure"]
        for node in structure["nodes"]:
            if "interrupts" in node:
                node["interrupts"] = sorted(node["interrupts"])
        for join in structure["joins"]:
            join["sources"] = sorted(join["sources"])

        structure["nodes"] = sorted(structure["nodes"], key=_sort_key)
        structure["edges"] = sorted(structure["edges"], key=_sort_key)
        structure["joins"] = sorted(structure["joins"], key=_sort_key)
        structure["entryNodeIds"] = sorted(structure["entryNodeIds"])
        structure["exitNodeIds"] = sorted(structure["exitNodeIds"])

    canonical["graphs"] = sorted(canonical.get("graphs", []), key=_sort_key)
    return _ordered(canonical)


def canonical_json(document: Mapping[str, Any]) -> str:
    """Serialize a topology document to its byte-stable canonical JSON form."""
    return json.dumps(
        canonicalize_document(document),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _selected_fields(
    value: Mapping[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    return {field: value[field] for field in fields if field in value}


def _structure_projection_v1(document: Mapping[str, Any]) -> dict[str, Any]:
    canonical = canonicalize_document(document)
    graphs: list[dict[str, Any]] = []

    for graph in canonical["graphs"]:
        structure = graph["structure"]
        graphs.append(
            {
                "id": graph["id"],
                "structure": {
                    "nodes": [
                        _selected_fields(node, _NODE_HASH_FIELDS)
                        for node in structure["nodes"]
                    ],
                    "edges": [
                        _selected_fields(edge, _EDGE_HASH_FIELDS)
                        for edge in structure["edges"]
                    ],
                    "joins": [
                        _selected_fields(join, _JOIN_HASH_FIELDS)
                        for join in structure["joins"]
                    ],
                    "entryNodeIds": structure["entryNodeIds"],
                    "exitNodeIds": structure["exitNodeIds"],
                },
            }
        )

    return {"graphs": graphs}


_HASH_PROJECTIONS: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "1": _structure_projection_v1,
}


def compute_structure_hash(
    document: Mapping[str, Any],
    *,
    algorithm_version: str = STRUCTURE_HASH_ALGORITHM_VERSION,
) -> dict[str, str]:
    """Compute the versioned hash field for a topology document's structure."""
    try:
        project_structure = _HASH_PROJECTIONS[algorithm_version]
    except KeyError:
        supported = ", ".join(sorted(_HASH_PROJECTIONS))
        raise ValueError(
            f"unsupported structure hash algorithm version {algorithm_version!r}; "
            f"supported versions: {supported}"
        ) from None

    projection = project_structure(document)
    payload = json.dumps(
        projection,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "algorithm": STRUCTURE_HASH_ALGORITHM,
        "algorithmVersion": algorithm_version,
        "value": hashlib.sha256(payload).hexdigest(),
    }


def finalize_document(
    document: Mapping[str, Any],
    *,
    algorithm_version: str = STRUCTURE_HASH_ALGORITHM_VERSION,
) -> dict[str, Any]:
    """Set the structure hash and return the canonical output document."""
    finalized = deepcopy(dict(document))
    finalized["structureHash"] = compute_structure_hash(
        finalized, algorithm_version=algorithm_version
    )
    return canonicalize_document(finalized)
