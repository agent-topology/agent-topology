#!/usr/bin/env python3
"""Replay the minimal repeat-attempt capture fixture (issue #194) offline --
no LangGraph, no network, no checkout. Standard library only.

Derives, from the raw captured event list alone, the fact this fixture
exists to prove: that a same-node retry (`attemptNumber` 1 -> 2, both under
one `invocationRunId`, no `Command(resume=...)`, no second invoke()) leaves
the node's step-occurrence counter at 1 throughout -- attempt count and step
(node) occurrence are independent counters, never conflated -- exactly
mirroring capture.py's (#191) `retryAttemptsObserved` field, but with that
field now nonzero instead of the 0 recorded there.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = CAPTURE_DIR / "fixtures" / "repeat-attempt"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def replay(trace: dict[str, Any]) -> dict[str, Any]:
    events = trace["events"]
    (invocation,) = trace["invocations"]

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
        "consumer": trace["provenance"]["consumer"],
        "captureMechanism": trace["provenance"]["captureMechanism"],
        "totalEvents": len(events),
        "distinctRunIds": sorted(by_run),
        "distinctInvocationRunIds": sorted(by_invocation),
        "sequencesContiguousPerRun": sequences_contiguous,
        "paused": bool(invocation["paused"]),
        "attemptNumbersObserved": [
            e["metadata"]["attemptNumber"] for e in attempt_events
        ],
        "retryAttemptsObserved": len(retry_attempt_events),
        "repeatedWithinSingleInvocation": (
            len(by_invocation) == 1 and len(attempt_events) > 1
        ),
        "stepOccurrencesByNode": dict(sorted(step_occurrences.items())),
        "attemptOccurrencesByNode": dict(sorted(attempt_occurrences.items())),
        "finalOutcome": trace["finalOutcome"],
        "unresolvedEvidence": trace["provenance"]["unresolvedEvidence"],
        "eventTypesByInvocation": {
            invocation_run_id: [event["eventType"] for event in run_events]
            for invocation_run_id, run_events in sorted(by_invocation.items())
        },
    }


def _human_summary(result: dict[str, Any]) -> str:
    lines = [
        f"Scenario: {result['scenario']} (synthetic, no consumer checkout)",
        f"Capture mechanism: {result['captureMechanism']}",
        f"Total events: {result['totalEvents']}",
        f"Distinct logical run IDs: {result['distinctRunIds']}",
        f"Distinct invocation run IDs: {result['distinctInvocationRunIds']}",
        f"Per-run sequences contiguous from 1: {result['sequencesContiguousPerRun']}",
        f"Paused (should be False -- no resume in this fixture): {result['paused']}",
        f"Attempt numbers observed: {result['attemptNumbersObserved']}",
        f"Retry attempts observed: {result['retryAttemptsObserved']}",
        "Repeated within a single invocation: "
        f"{result['repeatedWithinSingleInvocation']}",
        f"Step occurrences by node: {result['stepOccurrencesByNode']}",
        f"Attempt occurrences by node: {result['attemptOccurrencesByNode']}",
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
