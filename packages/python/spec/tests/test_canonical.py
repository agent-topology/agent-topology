from __future__ import annotations

from copy import deepcopy

import pytest
from agent_topology.spec import (
    canonical_json,
    canonicalize_document,
    compute_structure_hash,
    finalize_document,
)


def _document() -> dict:
    return {
        "topologyVersion": "0.1",
        "provenance": {
            "generatedAt": "2026-09-10T19:00:00Z",
            "producer": {"name": "test-producer", "version": "1.0"},
            "framework": {"name": "test-framework", "version": "2.0"},
        },
        "producerLimitations": [],
        "structureHash": {
            "algorithm": "sha256",
            "algorithmVersion": "1",
            "value": "0" * 64,
        },
        "graphs": [
            {
                "id": "main",
                "name": "Example graph",
                "structure": {
                    "nodes": [
                        {"id": "target", "type": "task"},
                        {"id": "b", "interrupts": ["before", "after"]},
                        {"id": "a"},
                    ],
                    "edges": [
                        {
                            "id": "b-target",
                            "source": "b",
                            "target": "target",
                            "kind": "direct",
                        },
                        {
                            "id": "a-target",
                            "source": "a",
                            "target": "target",
                            "kind": "direct",
                        },
                    ],
                    "joins": [
                        {"id": "wait", "sources": ["b", "a"], "target": "target"}
                    ],
                    "entryNodeIds": ["b", "a"],
                    "exitNodeIds": ["target"],
                },
            }
        ],
        "completeness": {"status": "complete", "gaps": []},
    }


def test_declaration_order_does_not_change_canonical_output_or_hash() -> None:
    first = _document()
    reordered = deepcopy(first)
    structure = reordered["graphs"][0]["structure"]
    structure["nodes"].reverse()
    structure["edges"].reverse()
    structure["joins"][0]["sources"].reverse()
    structure["entryNodeIds"].reverse()
    structure["nodes"][1]["interrupts"].reverse()

    original = deepcopy(reordered)
    assert canonical_json(finalize_document(first)) == canonical_json(
        finalize_document(reordered)
    )
    assert compute_structure_hash(first) == compute_structure_hash(reordered)
    assert reordered == original


def test_multi_source_join_differs_from_independent_edges() -> None:
    joined = _document()
    joined["graphs"][0]["structure"]["edges"] = []
    independent = deepcopy(joined)
    independent["graphs"][0]["structure"]["joins"] = []
    independent["graphs"][0]["structure"]["edges"] = [
        {
            "id": f"{source}-target",
            "source": source,
            "target": "target",
            "kind": "direct",
        }
        for source in ("a", "b")
    ]

    assert compute_structure_hash(joined) != compute_structure_hash(independent)


def test_descriptive_metadata_and_extensions_are_not_hashed() -> None:
    first = _document()
    changed = deepcopy(first)
    changed["graphs"][0]["name"] = "A different label"
    changed["provenance"]["generatedAt"] = "2030-01-01T00:00:00Z"
    changed["producerLimitations"] = [
        {"code": "opaque", "message": "Descriptive limitation text."}
    ]
    changed["x-example"] = {"presentation": ["right", "left"]}

    assert compute_structure_hash(first) == compute_structure_hash(changed)


def test_structural_properties_are_hashed() -> None:
    first = _document()
    changed = deepcopy(first)
    changed["graphs"][0]["structure"]["nodes"][0]["type"] = "approval"

    assert compute_structure_hash(first) != compute_structure_hash(changed)


def test_hash_algorithm_version_is_independent_and_explicit() -> None:
    document = _document()
    document["topologyVersion"] = "a-future-format"

    assert compute_structure_hash(document)["algorithmVersion"] == "1"
    with pytest.raises(
        ValueError, match="unsupported structure hash algorithm version"
    ):
        compute_structure_hash(document, algorithm_version="2")


def test_canonicalize_document_sorts_graphs() -> None:
    document = _document()
    second_graph = deepcopy(document["graphs"][0])
    second_graph["id"] = "alpha"
    second_graph["structure"]["nodes"] = []
    second_graph["structure"]["edges"] = []
    second_graph["structure"]["joins"] = []
    second_graph["structure"]["entryNodeIds"] = []
    second_graph["structure"]["exitNodeIds"] = []
    document["graphs"].append(second_graph)

    assert [graph["id"] for graph in canonicalize_document(document)["graphs"]] == [
        "alpha",
        "main",
    ]
