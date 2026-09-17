#!/usr/bin/env python3
"""Replay the campaign-agent declared-child correlation capture fixture
offline -- no campaign-agent checkout, no LangGraph, no network, no
agent-topology `describe()` call. Standard library only.

Derives, from the raw captured `staticEvidence` and `events` alone, the facts
issue #193 exists to prove: that `channel_concept`'s `prepare_brief` node's
depth-0 subgraph fact really is `declared-child-call` (the accepted mapping
from #180 / `_describe.py:301-359`), that its depth-2 materialized subgraph
matches `copy_brief_prepare`'s own standalone `describe()` output, and that
at runtime the object actually invoked from inside `prepare_brief` was
confirmed `is`-identical to that declared child -- correlated by identity,
never by display name. It also keeps static call site (`nodeId`), logical
run (`runId`), resume invocation (`invocationRunId`), node occurrence
(`nodeOccurrence`), and retry attempt (`metadata.attemptNumber`) distinct,
and shows that a declared child's own node identity (e.g. `select_evidence`)
is only ever observed nested under the parent node that declared it
(`nestedUnderNodeId`) -- never as a top-level LangGraph task, which the
parent's own `stream_mode="debug"` channel cannot see at all, since the
nested `child.invoke()` call runs entirely inside one parent task.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = CAPTURE_DIR / "fixtures" / "prepare-brief-declared-child"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def replay(trace: dict[str, Any]) -> dict[str, Any]:
    events = trace["events"]
    static = trace["staticEvidence"]
    first, second = trace["invocations"][0], trace["invocations"][1]

    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_run[event["runId"]].append(event)
    sequences_contiguous = all(
        [event["sequence"] for event in run_events]
        == list(range(1, len(run_events) + 1))
        for run_events in by_run.values()
    )

    by_invocation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_invocation[event["invocationRunId"]].append(event)

    task_events = [e for e in events if e["eventType"].startswith("task.")]
    task_occurrences: dict[str, list[int]] = defaultdict(list)
    for event in task_events:
        task_occurrences[event["nodeId"]].append(event["nodeOccurrence"])
    task_events_never_nested = all(e["nestedUnderNodeId"] is None for e in task_events)

    identity_events = [
        e for e in events if e["eventType"] == "invoke.declared-child-call"
    ]
    identity_by_node = {
        e["nodeId"]: e["declaredChildIdentityConfirmed"] for e in identity_events
    }
    identity_all_confirmed = bool(identity_events) and all(
        e["declaredChildIdentityConfirmed"] for e in identity_events
    )
    declared_child_graph_names = {
        e["nodeId"]: e["declaredChildGraphName"] for e in identity_events
    }

    nested_observer_events = [
        e
        for e in events
        if e["eventType"].startswith("observer.") and e["nestedUnderNodeId"]
    ]
    nested_node_ids_by_parent: dict[str, set[str]] = defaultdict(set)
    for event in nested_observer_events:
        nested_node_ids_by_parent[event["nestedUnderNodeId"]].add(event["nodeId"])

    target_node_id = static["nodeId"]
    target_child_graph = static["declaredChildGraph"]
    relationship_confirmed = (
        static["depth0Evidence"]["kind"] == "declared-child-call"
        and static["matchesStandaloneFactory"] is True
        and identity_by_node.get(target_node_id) is True
        and "select_evidence" in nested_node_ids_by_parent.get(target_node_id, set())
    )

    attempt_events = [
        e for e in events if e["eventType"].startswith("observer.attempt.")
    ]
    retry_attempt_events = [
        e for e in attempt_events if e["metadata"]["attemptNumber"] > 1
    ]

    return {
        "replayVersion": "1",
        "scenario": trace["provenance"]["scenario"],
        "consumerCommit": trace["provenance"]["consumer"]["commit"],
        "coreCommit": trace["provenance"]["core"]["commit"],
        "captureMechanism": trace["provenance"]["captureMechanism"],
        "totalEvents": len(events),
        "distinctRunIds": sorted(by_run),
        "distinctInvocationRunIds": sorted(by_invocation),
        "sequencesContiguousPerRun": sequences_contiguous,
        "firstInvocationPaused": bool(first["paused"]),
        "pausedAtNodeId": first["pausedAtNodeId"],
        "secondInvocationPaused": bool(second["paused"]),
        "staticRelationship": {
            "parent": static["parent"],
            "nodeId": target_node_id,
            "declaredChildGraph": target_child_graph,
            "depth0EvidenceKind": static["depth0Evidence"]["kind"],
            "materializedSubgraphId": static["materializedSubgraphId"],
            "matchesStandaloneFactory": static["matchesStandaloneFactory"],
        },
        "declaredChildIdentityConfirmedByNode": dict(sorted(identity_by_node.items())),
        "declaredChildGraphNamesByNode": dict(
            sorted(declared_child_graph_names.items())
        ),
        "allDeclaredChildInvokesConfirmedByIdentity": identity_all_confirmed,
        "nestedObserverNodeIdsByParent": {
            parent: sorted(node_ids)
            for parent, node_ids in sorted(nested_node_ids_by_parent.items())
        },
        "taskLevelEventsNeverNested": task_events_never_nested,
        "declaredChildCallCorrelationConfirmed": relationship_confirmed,
        "taskOccurrencesByNode": dict(sorted(task_occurrences.items())),
        "retryAttemptsObserved": len(retry_attempt_events),
        "finalOutcome": trace["finalOutcome"],
        "unresolvedEvidence": trace["provenance"]["unresolvedEvidence"],
        "eventTypesByInvocation": {
            invocation_run_id: [event["eventType"] for event in run_events]
            for invocation_run_id, run_events in sorted(by_invocation.items())
        },
    }


def _human_summary(result: dict[str, Any]) -> str:
    commit = result["consumerCommit"][:8]
    rel = result["staticRelationship"]
    lines = [
        f"Scenario: {result['scenario']} (campaign-agent {commit})",
        f"Capture mechanism: {result['captureMechanism']}",
        f"Total events: {result['totalEvents']}",
        f"Distinct logical run IDs: {result['distinctRunIds']}",
        f"Distinct invocation run IDs: {result['distinctInvocationRunIds']}",
        f"Per-run sequences contiguous from 1: {result['sequencesContiguousPerRun']}",
        f"First invocation paused: {result['firstInvocationPaused']}",
        f"Paused at node: {result['pausedAtNodeId']}",
        f"Second invocation paused again: {result['secondInvocationPaused']}",
        (
            f"Static relationship: {rel['parent']}.{rel['nodeId']} -> "
            f"{rel['declaredChildGraph']} ({rel['depth0EvidenceKind']}, "
            f"materialized as {rel['materializedSubgraphId']}, matches "
            f"standalone factory: {rel['matchesStandaloneFactory']})"
        ),
        "Declared-child invoke identity confirmed by node: "
        f"{result['declaredChildIdentityConfirmedByNode']}",
        f"All declared-child invokes identity-confirmed: "
        f"{result['allDeclaredChildInvokesConfirmedByIdentity']}",
        "Nested observer node ids by parent: "
        f"{result['nestedObserverNodeIdsByParent']}",
        f"Task-level events never nested: {result['taskLevelEventsNeverNested']}",
        "Declared-child-call correlation confirmed for "
        f"{rel['nodeId']} -> {rel['declaredChildGraph']}: "
        f"{result['declaredChildCallCorrelationConfirmed']}",
        f"Retry attempts observed (0 expected): {result['retryAttemptsObserved']}",
        f"Final outcome: {result['finalOutcome']}",
        f"Unresolved evidence: {result['unresolvedEvidence']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the computed result with the checked-in expected.json",
    )
    args = parser.parse_args(argv)

    trace = _load_json(FIXTURE_DIR / "trace.json")
    result = replay(trace)

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_human_summary(result))

    if args.check:
        expected = _load_json(FIXTURE_DIR / "expected.json")
        if result != expected:
            print(
                f"ERROR: replay result differs from {FIXTURE_DIR / 'expected.json'}",
                file=sys.stderr,
            )
            return 1
        print("Acceptance assertions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
