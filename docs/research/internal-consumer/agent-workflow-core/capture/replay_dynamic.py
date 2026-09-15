#!/usr/bin/env python3
"""Replay the interrupt-resume and repeated-attempt capture fixtures offline
-- no agent-workflow-core checkout, no LangGraph, no network. Standard
library only.

Derives, from the raw captured event list alone, the pause/attempt facts each
scenario exists to prove: that a dynamic interrupt pauses the graph and
resume completes it without pausing again, that the pre-interrupt node code
re-runs on resume, and that a same-node retry stays inside one invocation --
never claiming any of this proves authorization, budget compliance, or
effect success (see ../../README.md#interpretation-boundaries).
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
    "interrupt-resume": FIXTURE_DIR / "interrupt-resume",
    "repeated-attempt": FIXTURE_DIR / "repeated-attempt",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _common_facts(trace: dict[str, Any]) -> dict[str, Any]:
    events = trace["events"]
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
    return {
        "totalEvents": len(events),
        "distinctRunIds": sorted(by_run),
        "distinctInvocationRunIds": sorted(by_invocation),
        "sequencesContiguousPerRun": sequences_contiguous,
        "eventsByInvocation": dict(sorted(by_invocation.items())),
        "eventTypesByInvocation": {
            invocation_run_id: [event["eventType"] for event in run_events]
            for invocation_run_id, run_events in sorted(by_invocation.items())
        },
    }


def _replay_interrupt_resume(trace: dict[str, Any]) -> dict[str, Any]:
    facts = _common_facts(trace)
    first, second = trace["invocations"][0], trace["invocations"][1]

    approve_events_by_invocation = {
        invocation_run_id: [e for e in events if e["nodeId"] == "approve"]
        for invocation_run_id, events in facts["eventsByInvocation"].items()
    }
    node_reexecuted_on_resume = bool(
        approve_events_by_invocation.get(first["run_id"])
        and approve_events_by_invocation.get(second["run_id"])
    )

    return {
        "replayVersion": "1",
        "scenario": trace["provenance"]["scenario"],
        "consumerCommit": trace["provenance"]["consumer"]["commit"],
        "captureMechanism": trace["provenance"]["captureMechanism"],
        "totalEvents": facts["totalEvents"],
        "distinctRunIds": facts["distinctRunIds"],
        "distinctInvocationRunIds": facts["distinctInvocationRunIds"],
        "sequencesContiguousPerRun": facts["sequencesContiguousPerRun"],
        "firstInvocationPaused": bool(first["paused"]),
        "pausedAtNodeId": first["pausedAtNodeId"],
        "secondInvocationPaused": bool(second["paused"]),
        "nodeReExecutedOnResume": node_reexecuted_on_resume,
        "eventTypesByInvocation": facts["eventTypesByInvocation"],
    }


def _replay_repeated_attempt(trace: dict[str, Any]) -> dict[str, Any]:
    facts = _common_facts(trace)
    attempt_numbers = [
        event["metadata"]["attemptNumber"]
        for event in trace["events"]
        if event["eventType"].startswith("attempt.")
    ]
    return {
        "replayVersion": "1",
        "scenario": trace["provenance"]["scenario"],
        "consumerCommit": trace["provenance"]["consumer"]["commit"],
        "captureMechanism": trace["provenance"]["captureMechanism"],
        "totalEvents": facts["totalEvents"],
        "distinctRunIds": facts["distinctRunIds"],
        "distinctInvocationRunIds": facts["distinctInvocationRunIds"],
        "sequencesContiguousPerRun": facts["sequencesContiguousPerRun"],
        "attemptNumbersObserved": attempt_numbers,
        "repeatedWithinSingleInvocation": (
            len(facts["distinctInvocationRunIds"]) == 1 and len(attempt_numbers) > 1
        ),
        "eventTypesByInvocation": facts["eventTypesByInvocation"],
    }


def replay(trace: dict[str, Any]) -> dict[str, Any]:
    scenario = trace["provenance"]["scenario"]
    if scenario == "interrupt-resume":
        return _replay_interrupt_resume(trace)
    return _replay_repeated_attempt(trace)


def _human_summary(result: dict[str, Any]) -> str:
    commit = result["consumerCommit"][:8]
    lines = [
        f"Scenario: {result['scenario']} (agent-workflow-core {commit})",
        f"Capture mechanism: {result['captureMechanism']}",
        f"Total events: {result['totalEvents']}",
        f"Distinct event run IDs: {result['distinctRunIds']}",
        f"Distinct invocation run IDs: {result['distinctInvocationRunIds']}",
        f"Per-run sequences contiguous from 1: {result['sequencesContiguousPerRun']}",
    ]
    if result["scenario"] == "interrupt-resume":
        lines += [
            f"First invocation paused: {result['firstInvocationPaused']}",
            f"Paused at node: {result['pausedAtNodeId']}",
            f"Second invocation paused again: {result['secondInvocationPaused']}",
            f"Node body re-executed on resume: {result['nodeReExecutedOnResume']}",
        ]
    else:
        lines += [
            f"Attempt numbers observed: {result['attemptNumbersObserved']}",
            "Repeated within a single invocation: "
            f"{result['repeatedWithinSingleInvocation']}",
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
