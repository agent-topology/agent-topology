#!/usr/bin/env python3
"""Replay sanitized capture fixtures offline -- no agent-workflow-core checkout,
no LangGraph, no network. Standard library only.

Derives, from the raw captured event list alone, whether the two invocations'
step events land under one logical run (resume identity preserved) or two
separate ones (no resume identity), and checks that against the committed
`expected.json` for each scenario.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = CAPTURE_DIR / "fixtures"
SCENARIOS = {
    "tag": FIXTURE_DIR / "tag-v0.1.0.beta.3",
    "main": FIXTURE_DIR / "main-876f6a8a",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def replay(trace: dict[str, Any]) -> dict[str, Any]:
    """Return the resume-identity facts derivable from a captured trace alone."""
    events = trace["events"]
    invocation_count = len(trace["invocations"])

    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_run[event["runId"]].append(event)

    sequences_contiguous = all(
        [event["sequence"] for event in run_events]
        == list(range(1, len(run_events) + 1))
        for run_events in by_run.values()
    )

    step_events = [event for event in events if event["eventType"].startswith("step.")]
    node_ids_per_run = {
        run_id: [
            event["nodeId"]
            for event in run_events
            if event["eventType"].startswith("step.")
        ]
        for run_id, run_events in by_run.items()
    }

    return {
        "replayVersion": "1",
        "scenario": trace["provenance"]["scenario"],
        "consumerCommit": trace["provenance"]["consumer"]["commit"],
        "captureMechanism": trace["provenance"]["captureMechanism"],
        "totalEvents": len(events),
        "totalStepEvents": len(step_events),
        "distinctRunIds": sorted(by_run),
        "resumeIdentityPreserved": len(by_run) == 1 and invocation_count > 1,
        "sequencesContiguousPerRun": sequences_contiguous,
        "nodeIdsObservedPerRun": node_ids_per_run,
    }


def _human_summary(result: dict[str, Any]) -> str:
    commit = result["consumerCommit"][:8]
    lines = [
        f"Scenario: {result['scenario']} (agent-workflow-core {commit})",
        f"Capture mechanism: {result['captureMechanism']}",
        (
            f"Events: {result['totalEvents']} total, "
            f"{result['totalStepEvents']} step events"
        ),
        f"Distinct run IDs across both invocations: {result['distinctRunIds']}",
        (
            "Resume identity preserved across invocations: "
            f"{result['resumeIdentityPreserved']}"
        ),
        f"Per-run sequences contiguous from 1: {result['sequencesContiguousPerRun']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), required=True)
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the computed result with the checked-in "
        "fixtures/<scenario>/expected.json",
    )
    args = parser.parse_args(argv)

    scenario_dir = SCENARIOS[args.scenario]
    trace = _load_json(scenario_dir / "trace.json")
    result = replay(trace)

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_human_summary(result))

    if args.check:
        expected = _load_json(scenario_dir / "expected.json")
        if result != expected:
            print(
                f"ERROR: replay result differs from {scenario_dir / 'expected.json'}",
                file=sys.stderr,
            )
            return 1
        print("Acceptance assertions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
