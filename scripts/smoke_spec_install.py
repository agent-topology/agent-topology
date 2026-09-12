#!/usr/bin/env python3
"""Prove an installed spec distribution is usable without LangGraph."""

from __future__ import annotations

import json
import sys
from decimal import ROUND_FLOOR, DivisionByZero, Inexact, Rounded, localcontext
from importlib.metadata import requires

from agent_topology.spec import (
    canonical_json,
    compute_structure_hash,
    derived_join_edges,
    load_schema,
    validate_document,
)

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

numeric_document = json.loads(
    """
    {
      "topologyVersion": "0.1",
      "provenance": {
        "generatedAt": "2026-09-10T19:00:00Z",
        "producer": {"name": "smoke-test", "version": "1.0"},
        "framework": {"name": "smoke-test", "version": "1.0"}
      },
      "producerLimitations": [],
      "structureHash": {
        "algorithm": "sha256",
        "algorithmVersion": "1",
        "value": "0000000000000000000000000000000000000000000000000000000000000000"
      },
      "graphs": [
        {
          "id": "main",
          "structure": {
            "nodes": [],
            "edges": [],
            "joins": [],
            "entryNodeIds": [],
            "exitNodeIds": []
          }
        }
      ],
      "completeness": {"status": "complete", "gaps": []},
      "x-numeric": [
        0.0,
        -0.0,
        1.0,
        0.5,
        0.000001,
        0.0000001,
        100000000000000000000,
        1e21,
        9007199254740993,
        {"decimal": 1.23456789}
      ]
    }
    """
)
expected_numeric_bytes = (
    '{"completeness":{"gaps":[],"status":"complete"},"graphs":[{"id":"main",'
    '"structure":{"edges":[],"entryNodeIds":[],"exitNodeIds":[],"joins":[],'
    '"nodes":[]}}],"producerLimitations":[],"provenance":{"framework":'
    '{"name":"smoke-test","version":"1.0"},"generatedAt":"2026-09-10T19:00:00Z",'
    '"producer":{"name":"smoke-test","version":"1.0"}},"structureHash":'
    '{"algorithm":"sha256","algorithmVersion":"1","value":"'
    + "0"
    * 64
    + '"},"topologyVersion":"0.1","x-numeric":[0,0,1,0.5,0.000001,1e-7,'
    '100000000000000000000,1e+21,9007199254740992,{"decimal":1.23456789}]}'
)
expected_hash = {
    "algorithm": "sha256",
    "algorithmVersion": "1",
    "value": "8bfd237d53e3cd48927ba6ddc520d66a3fd32c629e969204654a2801ed423319",
}

assert validate_document(numeric_document) == []
assert canonical_json(numeric_document) == expected_numeric_bytes
assert compute_structure_hash(numeric_document) == expected_hash
with localcontext() as context:
    context.prec = 6
    context.rounding = ROUND_FLOOR
    context.traps[Inexact] = True
    context.traps[Rounded] = True
    context.flags[DivisionByZero] = True
    assert canonical_json(numeric_document) == expected_numeric_bytes
    assert compute_structure_hash(numeric_document) == expected_hash

assert not any(
    "langgraph" in requirement.lower()
    for requirement in (requires("agent-topology-spec") or [])
)
assert not any(
    name == "langgraph" or name.startswith("langgraph.") for name in sys.modules
)
