#!/usr/bin/env python3
"""Refresh deterministic fixtures from a real LangGraph 1.2.11 execution."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import agent_topology.langgraph
import agent_topology.spec
from correlate import correlate
from langgraph.graph import END, START, StateGraph

EXAMPLE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = EXAMPLE_DIR / "fixtures"
FIXTURE_TIMESTAMP = "2026-09-10T00:00:00Z"
FIXTURE_LANGGRAPH_VERSION = "1.2.11"


def _primary_graph() -> Any:
    def plan(_: dict[str, Any]) -> dict[str, Any]:
        return {
            "route": "review",
            "runtimeEvidence": [
                {"kind": "tool.completed", "nodeId": "customer-lookup"}
            ],
        }

    def route(state: dict[str, Any]) -> str:
        return state["route"]

    def review(_: dict[str, Any]) -> dict[str, Any]:
        return {"reviewed": True}

    def archive(_: dict[str, Any]) -> dict[str, Any]:
        return {"archived": True}

    builder = StateGraph(dict)
    builder.add_node("plan", plan)
    builder.add_node("review", review)
    builder.add_node("archive", archive)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", route)
    builder.add_edge("review", END)
    builder.add_edge("archive", END)
    return builder.compile(name="approval-flow")


def _shadow_graph() -> Any:
    builder = StateGraph(dict)
    builder.add_node("review", lambda state: state)
    builder.add_node("archive", lambda state: state)
    builder.add_edge(START, "review")
    builder.add_edge("review", "archive")
    builder.add_edge("archive", END)
    return builder.compile(name="shadow-flow")


def _rename_graph(document: dict[str, Any], graph_id: str) -> dict[str, Any]:
    graph = deepcopy(document["graphs"][0])
    graph["id"] = graph_id
    return graph


def _topology(primary: Any, shadow: Any) -> dict[str, Any]:
    primary_document = agent_topology.langgraph.describe(primary)
    shadow_document = agent_topology.langgraph.describe(shadow)
    framework_version = primary_document["provenance"]["framework"]["version"]
    if framework_version != FIXTURE_LANGGRAPH_VERSION:
        raise RuntimeError(
            "fixture refresh requires LangGraph "
            f"{FIXTURE_LANGGRAPH_VERSION}, found {framework_version}"
        )

    gaps = deepcopy(primary_document["completeness"]["gaps"])
    document = {
        "topologyVersion": primary_document["topologyVersion"],
        "provenance": {
            **primary_document["provenance"],
            "generatedAt": FIXTURE_TIMESTAMP,
            "source": {
                "kind": "compiled-object",
                "locator": "examples/trace-correlation/generate_fixtures.py",
            },
        },
        "producerLimitations": primary_document["producerLimitations"],
        "graphs": [
            _rename_graph(primary_document, "approval"),
            _rename_graph(shadow_document, "shadow"),
        ],
        "completeness": {"status": "incomplete", "gaps": gaps},
    }
    for gap in document["completeness"]["gaps"]:
        gap["element"]["graphId"] = "approval"
    return agent_topology.spec.finalize_document(document)


def _trace(primary: Any, framework_version: str) -> dict[str, Any]:
    updates = list(primary.stream({}, stream_mode="updates"))
    if [next(iter(update)) for update in updates] != ["plan", "review"]:
        raise RuntimeError(f"unexpected execution updates: {updates!r}")

    runtime_evidence = updates[0]["plan"]["runtimeEvidence"][0]
    return {
        "traceVersion": "1",
        "provenance": {
            "kind": "sanitized-langgraph-execution",
            "framework": {"name": "langgraph", "version": framework_version},
            "generator": "examples/trace-correlation/generate_fixtures.py",
            "scenario": "approval-flow routes plan to review",
            "sanitization": [
                "removed run identifiers and timestamps",
                "replaced application payloads with deterministic literals",
                "omitted graph identity from one node event to retain ambiguity",
            ],
        },
        "events": [
            {
                "eventId": "event-001",
                "kind": "node.completed",
                "graphId": "approval",
                "nodeId": next(iter(updates[0])),
            },
            {
                "eventId": "event-002",
                "kind": runtime_evidence["kind"],
                "graphId": "approval",
                "nodeId": runtime_evidence["nodeId"],
            },
            {
                "eventId": "event-003",
                "kind": "node.completed",
                "nodeId": next(iter(updates[1])),
            },
            {"eventId": "event-004", "kind": "graph.completed", "graphId": "approval"},
        ],
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=FIXTURE_DIR)
    args = parser.parse_args()

    primary = _primary_graph()
    topology = _topology(primary, _shadow_graph())
    trace = _trace(primary, topology["provenance"]["framework"]["version"])
    expected = correlate(topology, trace)

    validation_errors = agent_topology.spec.validate_document(topology)
    if validation_errors:
        raise RuntimeError(
            "generated topology is not a valid canonical document:\n"
            + "\n".join(validation_errors)
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "topology.json", topology)
    _write_json(args.output_dir / "trace.json", trace)
    _write_json(args.output_dir / "expected.json", expected)
    print(f"Wrote deterministic fixtures to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
