#!/usr/bin/env python3
"""Correlate a topology document with sanitized runtime evidence offline."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

EXAMPLE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = EXAMPLE_DIR / "fixtures"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _node_index(
    topology: dict[str, Any],
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, list[dict[str, str]]]]:
    exact: dict[tuple[str, str], dict[str, str]] = {}
    by_node_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for graph in topology["graphs"]:
        for node in graph["structure"]["nodes"]:
            reference = {"graphId": graph["id"], "kind": "node", "id": node["id"]}
            exact[(graph["id"], node["id"])] = reference
            by_node_id[node["id"]].append(reference)
    return exact, by_node_id


def _correlate_event(
    event: dict[str, Any],
    exact: dict[tuple[str, str], dict[str, str]],
    by_node_id: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "eventId": event["eventId"],
        "kind": event["kind"],
    }
    node_id = event.get("nodeId")
    graph_id = event.get("graphId")

    if node_id is None:
        return {
            **result,
            "status": "insufficient",
            "reason": "trace-event-has-no-node-identity",
        }

    if graph_id is not None:
        match = exact.get((graph_id, node_id))
        if match is None:
            return {
                **result,
                "status": "unmatched",
                "reason": "no-topology-node-has-this-qualified-identity",
            }
        return {**result, "status": "matched", "match": match}

    candidates = by_node_id.get(node_id, [])
    if len(candidates) == 1:
        return {
            **result,
            "status": "matched",
            "match": candidates[0],
            "reason": "node-id-is-globally-unique",
        }
    if candidates:
        return {
            **result,
            "status": "ambiguous",
            "reason": "trace-event-omits-graph-identity",
            "candidates": candidates,
        }
    return {
        **result,
        "status": "unmatched",
        "reason": "no-topology-node-has-this-node-id",
    }


def correlate(topology: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    """Return stable evidence classes without inferring execution from absence."""
    exact, by_node_id = _node_index(topology)
    events = [_correlate_event(event, exact, by_node_id) for event in trace["events"]]

    matched = {
        (event["match"]["graphId"], event["match"]["id"])
        for event in events
        if event["status"] == "matched"
    }
    ambiguous_events: dict[tuple[str, str], list[str]] = defaultdict(list)
    for event in events:
        for candidate in event.get("candidates", []):
            ambiguous_events[(candidate["graphId"], candidate["id"])].append(
                event["eventId"]
            )

    gaps_by_graph: dict[str, list[str]] = defaultdict(list)
    for gap in topology["completeness"]["gaps"]:
        gaps_by_graph[gap["element"]["graphId"]].append(gap["code"])

    elements = []
    for graph in topology["graphs"]:
        for node in graph["structure"]["nodes"]:
            key = (graph["id"], node["id"])
            element: dict[str, Any] = {
                "element": {"graphId": key[0], "kind": "node", "id": key[1]},
                "status": "observed" if key in matched else "unobserved",
            }
            if key in ambiguous_events:
                element["evidence"] = {
                    "confidence": "insufficient",
                    "reason": "ambiguous-trace-evidence",
                    "eventIds": ambiguous_events[key],
                }
            elif key not in matched and gaps_by_graph.get(graph["id"]):
                element["evidence"] = {
                    "confidence": "insufficient",
                    "reason": "graph-has-topology-gaps",
                    "gapCodes": gaps_by_graph[graph["id"]],
                }
            elif key not in matched:
                element["evidence"] = {
                    "confidence": "absent",
                    "reason": "no-matching-trace-evidence",
                }
            elements.append(element)

    counts = {
        status: 0 for status in ("matched", "unmatched", "ambiguous", "insufficient")
    }
    for event in events:
        counts[event["status"]] += 1
    counts["unobservedTopologyElements"] = sum(
        element["status"] == "unobserved" for element in elements
    )

    return {
        "correlationVersion": "1",
        "traceProvenance": trace["provenance"],
        "topologyEvidence": {
            "structureHash": topology["structureHash"],
            "completeness": topology["completeness"],
            "producerLimitations": topology["producerLimitations"],
        },
        "summary": counts,
        "events": events,
        "topologyElements": elements,
    }


def _human_summary(result: dict[str, Any]) -> str:
    summary = result["summary"]
    unobserved = summary["unobservedTopologyElements"]
    completeness = result["topologyEvidence"]["completeness"]["status"]
    lines = [
        "Topology-to-trace correlation",
        (
            "Events: "
            f"{summary['matched']} matched, {summary['unmatched']} unmatched, "
            f"{summary['ambiguous']} ambiguous, "
            f"{summary['insufficient']} insufficient"
        ),
        f"Topology elements without matching evidence: {unobserved}",
        f"Topology completeness: {completeness}",
        (
            "Producer limitations preserved: "
            f"{len(result['topologyEvidence']['producerLimitations'])}"
        ),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, default=FIXTURE_DIR / "topology.json")
    parser.add_argument("--trace", type=Path, default=FIXTURE_DIR / "trace.json")
    parser.add_argument("--expected", type=Path, default=FIXTURE_DIR / "expected.json")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the computed machine result with the checked-in expectation",
    )
    args = parser.parse_args(argv)

    result = correlate(_load_json(args.topology), _load_json(args.trace))
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_human_summary(result))

    if args.check and result != _load_json(args.expected):
        print(
            "ERROR: correlation result differs from fixtures/expected.json",
            file=sys.stderr,
        )
        return 1
    if args.check:
        print("Acceptance assertions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
