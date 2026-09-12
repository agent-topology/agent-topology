"""Independent ADR 0008 document checks; not a shipped validator API."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from agent_topology.spec import (
    canonical_json,
    compute_structure_hash,
    validate_document,
)
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1] / "experimental"
CASES = json.loads((ROOT / "interpretation-cases.json").read_text())
SCHEMA = json.loads((ROOT / "interpretation-v1.schema.json").read_text())
KEY = "x-topology-interpretation"


def interpretation_status(document):
    """Check shape and document-verifiable semantics, never producer truth."""
    allowed = {id(graph) for graph in document["graphs"]}

    def misplaced(value):
        if isinstance(value, dict):
            return (KEY in value and id(value) not in allowed) or any(
                misplaced(item) for key, item in value.items() if key != KEY
            )
        return isinstance(value, list) and any(misplaced(item) for item in value)

    if misplaced(document):
        return "invalid"
    found = False
    for graph in document["graphs"]:
        if KEY not in graph:
            continue
        found = True
        extension = graph[KEY]
        if isinstance(extension, dict) and isinstance(extension.get("version"), str):
            if extension["version"] != "1":
                return "unsupported"
        if not Draft202012Validator(SCHEMA).is_valid(extension):
            return "invalid"
        structure = graph["structure"]
        nodes = {node["id"]: node for node in structure["nodes"]}
        ids = [record["nodeId"] for record in extension["nodes"]]
        if ids != sorted(set(ids)) or not set(ids) <= nodes.keys():
            return "invalid"
        targets = {edge["target"] for edge in structure["edges"]} | {
            join["target"] for join in structure["joins"]
        }
        for record in extension["nodes"]:
            node_id = record["nodeId"]
            entry = record.get("entry", {})
            if entry and entry["observedRoot"] != (node_id not in targets):
                return "invalid"
            if record.get("branch", {}).get("value") == "all-declared":
                outgoing = [
                    edge for edge in structure["edges"] if edge["source"] == node_id
                ]
                routing_gap = any(
                    gap["code"] == "unknown-routing-targets"
                    and gap["element"]
                    == {"graphId": graph["id"], "kind": "node", "id": node_id}
                    for gap in document["completeness"]["gaps"]
                )
                if (
                    len(outgoing) < 2
                    or any(edge["kind"] != "direct" for edge in outgoing)
                    or routing_gap
                ):
                    return "invalid"
            child = record.get("subgraph", {}).get("value")
            sentinel = record.get("sentinel", {}).get("value")
            if child == "opaque-child" and (
                "subgraphId" in nodes[node_id] or sentinel in {"start", "end"}
            ):
                return "invalid"
            if (sentinel, entry.get("value")) in {
                ("start", "not-entry"),
                ("end", "confirmed"),
            }:
                return "invalid"
    return "valid" if found else "absent"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_contract_example(case):
    document = case["document"]
    assert not validate_document(document)
    assert compute_structure_hash(document) == document["structureHash"]
    assert (
        hashlib.sha256(canonical_json(document).encode()).hexdigest()
        == case["canonicalSha256"]
    )
    assert interpretation_status(document) == case["extensionStatus"]
    for graph in document["graphs"]:
        if KEY in graph:
            assert (
                Draft202012Validator(SCHEMA).is_valid(graph[KEY]) == case["shapeValid"]
            )
    stripped = copy.deepcopy(document)
    stripped.pop(KEY, None)
    for graph in stripped["graphs"]:
        graph.pop(KEY, None)
    assert compute_structure_hash(document) == compute_structure_hash(stripped)


def test_extension_schema_is_valid():
    Draft202012Validator.check_schema(SCHEMA)
