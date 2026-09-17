#!/usr/bin/env python3
"""Replay the campaign-agent await_decision interrupt/resume capture fixture
offline -- no campaign-agent checkout, no LangGraph, no network. Standard
library only.

Derives, from the raw captured event list alone, the facts issue #192 exists
to prove: that a real interrupt through campaign-agent's actual
`await_decision` node pauses the real, approved `campaign_contract` graph
exactly once, that resume completes it without pausing again, that the same
real LangGraph task id is reused for the pre- and post-resume execution of
that node (so "which task" is not "which invocation"), and that static call
site / logical run / node occurrence / resume invocation / retry attempt stay
five independently addressable identities. It also cross-checks the two
independent, real sources this capture recorded events from: LangGraph's own
`stream_mode="debug"` task events (the only source that observes
`await_decision` at all) and `agent_workflow_core`'s `RunObserver`
step/attempt callbacks (which only fire for the two model nodes,
`draft_rules`/`draft_concept`) -- their occurrence counts for those two nodes
must agree. It makes no claim about a real campaign/GitHub effect -- this
scenario's `await_decision` gate exercises no write port at all; see
capture.py's `captureMechanism` and `sanitization` provenance for what was
and was not real.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = CAPTURE_DIR / "fixtures" / "await-decision-interrupt-resume"


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

    task_events = [e for e in events if e["eventType"].startswith("task.")]
    await_decision_task_events = [
        e for e in task_events if e["nodeId"] == "await_decision"
    ]
    await_decision_by_invocation = {
        invocation_run_id: [e for e in run_events if e["nodeId"] == "await_decision"]
        for invocation_run_id, run_events in by_invocation.items()
    }
    node_reexecuted_on_resume = bool(
        await_decision_by_invocation.get(first["run_id"])
        and await_decision_by_invocation.get(second["run_id"])
    )
    await_decision_task_ids = {e["taskId"] for e in await_decision_task_events}
    same_task_id_across_invocations = len(await_decision_task_ids) == 1

    task_occurrences: dict[str, list[int]] = defaultdict(list)
    for event in task_events:
        task_occurrences[event["nodeId"]].append(event["nodeOccurrence"])

    observer_step_occurrences: dict[str, list[int]] = defaultdict(list)
    observer_attempt_occurrences: dict[str, list[int]] = defaultdict(list)
    for event in events:
        kind, _, _outcome = event["eventType"].partition(".")
        if kind != "observer":
            continue
        _observer, family, _ = event["eventType"].split(".", 2)
        target = (
            observer_step_occurrences
            if family == "step"
            else observer_attempt_occurrences
        )
        target[event["nodeId"]].append(event["nodeOccurrence"])

    model_nodes = sorted(
        set(observer_step_occurrences) | set(observer_attempt_occurrences)
    )
    observer_and_task_occurrences_agree = all(
        task_occurrences.get(node) == observer_step_occurrences.get(node)
        for node in model_nodes
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
        "captureMechanism": trace["provenance"]["captureMechanism"],
        "totalEvents": len(events),
        "distinctRunIds": sorted(by_run),
        "distinctInvocationRunIds": sorted(by_invocation),
        "sequencesContiguousPerRun": sequences_contiguous,
        "firstInvocationPaused": bool(first["paused"]),
        "pausedAtNodeId": first["pausedAtNodeId"],
        "secondInvocationPaused": bool(second["paused"]),
        "nodeReExecutedOnResume": node_reexecuted_on_resume,
        "awaitDecisionTaskOccurrences": [
            e["nodeOccurrence"] for e in await_decision_task_events
        ],
        "awaitDecisionTaskIdStableAcrossInvocations": same_task_id_across_invocations,
        "taskOccurrencesByNode": dict(sorted(task_occurrences.items())),
        "observerStepOccurrencesByNode": dict(
            sorted(observer_step_occurrences.items())
        ),
        "observerAttemptOccurrencesByNode": dict(
            sorted(observer_attempt_occurrences.items())
        ),
        "observerAndTaskOccurrencesAgreeForModelNodes": (
            observer_and_task_occurrences_agree
        ),
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
        f"Scenario: {result['scenario']} (campaign-agent {commit})",
        f"Capture mechanism: {result['captureMechanism']}",
        f"Total events: {result['totalEvents']}",
        f"Distinct logical run IDs: {result['distinctRunIds']}",
        f"Distinct invocation run IDs: {result['distinctInvocationRunIds']}",
        f"Per-run sequences contiguous from 1: {result['sequencesContiguousPerRun']}",
        f"First invocation paused: {result['firstInvocationPaused']}",
        f"Paused at node: {result['pausedAtNodeId']}",
        f"Second invocation paused again: {result['secondInvocationPaused']}",
        f"Node body re-executed on resume: {result['nodeReExecutedOnResume']}",
        f"await_decision task occurrences: {result['awaitDecisionTaskOccurrences']}",
        "await_decision reuses one real LangGraph task id across invocations: "
        f"{result['awaitDecisionTaskIdStableAcrossInvocations']}",
        "Observer- and debug-stream-derived occurrence counts agree for "
        "draft_rules/draft_concept: "
        f"{result['observerAndTaskOccurrencesAgreeForModelNodes']}",
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
