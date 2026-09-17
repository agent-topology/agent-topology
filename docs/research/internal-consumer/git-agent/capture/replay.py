#!/usr/bin/env python3
"""Replay the git-agent human_approval interrupt/resume capture fixture
offline -- no git-agent checkout, no LangGraph, no network. Standard library
only.

Derives, from the raw captured event list alone, the facts issue #191 exists
to prove: that a real interrupt through git-agent's actual human_approval
node pauses the real, approved issue_resolution graph exactly once, that
resume completes it without pausing again, that the pre-interrupt node code
re-runs on resume (so human_approval shows two step occurrences, not one),
and that static call site / logical run / node occurrence / resume
invocation / retry attempt stay five independently addressable identities
rather than being conflated into one. It makes no claim about authorization,
budget compliance, or a real GitHub effect -- see capture.py's
`captureMechanism` and `sanitization` provenance for what was and was not
real.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = CAPTURE_DIR / "fixtures" / "human-approval-interrupt-resume"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def replay(trace: dict[str, Any]) -> dict[str, Any]:
    events = trace["events"]
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

    human_approval_events = [e for e in events if e["nodeId"] == "human_approval"]
    human_approval_by_invocation = {
        invocation_run_id: [e for e in run_events if e["nodeId"] == "human_approval"]
        for invocation_run_id, run_events in by_invocation.items()
    }
    node_reexecuted_on_resume = bool(
        human_approval_by_invocation.get(first["run_id"])
        and human_approval_by_invocation.get(second["run_id"])
    )

    step_occurrences: dict[str, list[int]] = defaultdict(list)
    attempt_occurrences: dict[str, list[int]] = defaultdict(list)
    for event in events:
        kind, _, _outcome = event["eventType"].partition(".")
        target = step_occurrences if kind == "step" else attempt_occurrences
        target[event["nodeId"]].append(event["nodeOccurrence"])

    attempt_events = [e for e in events if e["eventType"].startswith("attempt.")]
    retry_attempt_events = [
        e for e in attempt_events if e["metadata"]["attemptNumber"] > 1
    ]

    return {
        "replayVersion": "1",
        "scenario": trace["provenance"]["scenario"],
        "consumerCommit": trace["provenance"]["consumer"]["commit"],
        "captureMechanism": trace["provenance"]["captureMechanism"],
        "totalEvents": len(events),
        "distinctRunIds": sorted(by_run),
        "distinctInvocationRunIds": sorted(by_invocation),
        "sequencesContiguousPerRun": sequences_contiguous,
        "firstInvocationPaused": bool(first["paused"]),
        "pausedAtNodeId": first["pausedAtNodeId"],
        "secondInvocationPaused": bool(second["paused"]),
        "nodeReExecutedOnResume": node_reexecuted_on_resume,
        "humanApprovalStepOccurrences": [
            e["nodeOccurrence"] for e in human_approval_events
        ],
        "stepOccurrencesByNode": dict(sorted(step_occurrences.items())),
        "attemptOccurrencesByNode": dict(sorted(attempt_occurrences.items())),
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
    lines = [
        f"Scenario: {result['scenario']} (git-agent {commit})",
        f"Capture mechanism: {result['captureMechanism']}",
        f"Total events: {result['totalEvents']}",
        f"Distinct logical run IDs: {result['distinctRunIds']}",
        f"Distinct invocation run IDs: {result['distinctInvocationRunIds']}",
        f"Per-run sequences contiguous from 1: {result['sequencesContiguousPerRun']}",
        f"First invocation paused: {result['firstInvocationPaused']}",
        f"Paused at node: {result['pausedAtNodeId']}",
        f"Second invocation paused again: {result['secondInvocationPaused']}",
        f"Node body re-executed on resume: {result['nodeReExecutedOnResume']}",
        f"human_approval step occurrences: {result['humanApprovalStepOccurrences']}",
        f"Retry attempts observed (0 expected -- see issue #194): "
        f"{result['retryAttemptsObserved']}",
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
