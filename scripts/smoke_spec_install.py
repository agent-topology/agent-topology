#!/usr/bin/env python3
"""Prove an installed spec distribution is usable without LangGraph."""

from __future__ import annotations

import sys
from importlib.metadata import requires

from agent_topology.spec import load_schema, validate_document

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
                "nodes": [{"id": "node"}],
                "edges": [],
                "joins": [],
                "entryNodeIds": ["node"],
                "exitNodeIds": ["node"],
            },
        }
    ],
    "completeness": {"status": "complete", "gaps": []},
}

assert load_schema()["title"] == "Agent Topology Document"
assert validate_document(document) == []
assert not any(
    "langgraph" in requirement.lower()
    for requirement in (requires("agent-topology-spec") or [])
)
assert not any(
    name == "langgraph" or name.startswith("langgraph.") for name in sys.modules
)
