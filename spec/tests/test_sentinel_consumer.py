"""Framework-free presentation assertion; no renderer or reconnection API."""

import copy
import json
import runpy
from pathlib import Path

import pytest
from agent_topology.spec import canonical_json, finalize_document, validate_document

ROOT = Path(__file__).resolve().parents[2]
KEY = "x-topology-interpretation"
ORACLE = runpy.run_path(str(ROOT / "spec/tests/test_interpretation_examples.py"))[
    "interpretation_status"
]


def presentation(document):
    """Select display nodes only; retain every source connection and uncertainty."""
    assert not validate_document(document)
    status = ORACLE(document)
    graphs = []
    for graph in document["graphs"]:
        hidden = set()
        if status == "valid":
            hidden = {
                record["nodeId"]
                for record in graph.get(KEY, {}).get("nodes", [])
                if record.get("sentinel", {}).get("status") == "known"
                and record["sentinel"]["value"] in {"start", "end"}
            }
        structure = graph["structure"]
        graphs.append(
            {
                "nodeIds": [
                    node["id"]
                    for node in structure["nodes"]
                    if node["id"] not in hidden
                ],
                "edges": structure["edges"],
                "joins": structure["joins"],
            }
        )
    return {
        "status": status,
        "graphs": graphs,
        "completeness": document["completeness"],
        "producerLimitations": document["producerLimitations"],
    }


def assert_preserved(document):
    before = canonical_json(document)
    view = presentation(document)
    assert canonical_json(document) == before
    assert view["completeness"] is document["completeness"]
    assert view["producerLimitations"] is document["producerLimitations"]
    for graph, shown in zip(document["graphs"], view["graphs"]):
        assert shown["edges"] is graph["structure"]["edges"]
        assert shown["joins"] is graph["structure"]["joins"]
    return view


def authored_document():
    # Authored consumer case, not captured producer output. IDs intentionally
    # differ from LangGraph literals; a hidden sentinel also sources a join.
    document = json.loads(
        (ROOT / "conformance/fixtures/multi-source-join/expected.json").read_text()
    )
    graph = document["graphs"][0]
    graph["structure"] = {
        "nodes": [{"id": n} for n in ["begin", "work", "finish"]],
        "edges": [
            {"id": "connection", "source": "begin", "target": "work", "kind": "direct"}
        ],
        "joins": [
            {"id": "original-join", "sources": ["begin", "work"], "target": "finish"}
        ],
        "entryNodeIds": ["begin"],
        "exitNodeIds": ["finish"],
    }
    graph[KEY] = {
        "version": "1",
        "traversalDepth": 0,
        "nodes": [
            {
                "nodeId": n,
                "sentinel": {
                    "status": "known",
                    "value": value,
                    "evidence": {
                        "kind": "framework-sentinel",
                        "source": "authored-consumer-case",
                    },
                },
            }
            for n, value in [("begin", "start"), ("finish", "end")]
        ],
    }
    document["completeness"] = {
        "status": "incomplete",
        "gaps": [
            {
                "code": "unknown-routing-targets",
                "message": "Routing is unresolved.",
                "element": {"graphId": "main", "kind": "node", "id": "begin"},
            }
        ],
    }
    return finalize_document(document)


def test_filter_preserves_hidden_connection_and_join_provenance():
    document = authored_document()
    view = assert_preserved(document)
    assert view["graphs"][0]["nodeIds"] == ["work"]
    assert view["graphs"][0]["joins"][0]["sources"] == ["begin", "work"]
    assert view["completeness"]["gaps"][0]["element"]["id"] == "begin"
    # No producer metadata or framework import participates in the selection.
    assert "x-langgraph" not in canonical_json(document)


@pytest.mark.parametrize(
    "mode",
    [
        "absent",
        "unsupported",
        "invalid",
        "unknown",
        "missing-fact",
        "missing-record",
        "ordinary",
    ],
)
def test_no_trusted_role_does_not_hide(mode):
    document = copy.deepcopy(authored_document())
    extension = document["graphs"][0][KEY]
    if mode == "absent":
        del document["graphs"][0][KEY]
    elif mode == "unsupported":
        extension["version"] = "next"
    elif mode == "invalid":
        extension["nodes"][0]["sentinel"]["evidence"]["kind"] = "ordinary-node"
    elif mode == "missing-record":
        extension["nodes"] = []
    else:
        for record in extension["nodes"]:
            if mode == "unknown":
                record["sentinel"] = {
                    "status": "unknown",
                    "reason": "identity-unavailable",
                }
            elif mode == "ordinary":
                record["sentinel"]["value"] = "ordinary"
                record["sentinel"]["evidence"]["kind"] = "ordinary-node"
            else:
                del record["sentinel"]
                record["subgraph"] = {
                    "status": "unknown",
                    "reason": "identity-unavailable",
                }
    view = assert_preserved(document)
    assert set(view["graphs"][0]["nodeIds"]) == {"begin", "work", "finish"}
    assert view["status"] == {
        "absent": "absent",
        "unsupported": "unsupported",
        "invalid": "invalid",
    }.get(mode, "valid")


def test_legacy_document_keeps_every_node():
    document = json.loads(
        (ROOT / "conformance/fixtures/multi-source-join/expected.json").read_text()
    )
    view = assert_preserved(document)
    assert view["status"] == "absent"
    assert view["graphs"][0]["nodeIds"] == [
        n["id"] for n in document["graphs"][0]["structure"]["nodes"]
    ]
