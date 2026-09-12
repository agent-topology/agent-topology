#!/usr/bin/env python3
"""Prove an installed spec distribution is usable without LangGraph."""

from __future__ import annotations

import sys
from importlib.metadata import requires

from agent_topology.spec import derived_join_edges, load_schema, validate_document

document = {
    "topologyVersion": "0.1",
    "provenance": {
        "generatedAt": "2026-09-10T19:00:00Z",
        "producer": {"name": "smoke-test", "version": "1.0"},
        "framework": {"name": "smoke-test", "version": "1.0"},
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
            "structure": {
                "nodes": [{"id": "left"}, {"id": "right"}, {"id": "node"}],
                "edges": [],
                "joins": [
                    {"id": "wait", "sources": ["right", "left"], "target": "node"}
                ],
                "entryNodeIds": ["node"],
                "exitNodeIds": ["node"],
            },
        }
    ],
    "completeness": {"status": "complete", "gaps": []},
}

assert load_schema()["title"] == "Agent Topology Document"
assert validate_document(document) == []
assert derived_join_edges(document["graphs"][0]["structure"]) == [
    {"joinId": "wait", "source": "left", "target": "node"},
    {"joinId": "wait", "source": "right", "target": "node"},
]
assert not any(
    "langgraph" in requirement.lower()
    for requirement in (requires("agent-topology-spec") or [])
)
assert not any(
    name == "langgraph" or name.startswith("langgraph.") for name in sys.modules
)
