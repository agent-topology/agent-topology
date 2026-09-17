#!/usr/bin/env python3
"""Capture the minimal repeat-attempt fixture for issue #194, advancing
#181's third acceptance bullet: "A separate smallest repeat-attempt case may
measure retry mechanics; do not grow the full campaign input to test those
mechanics."

[capture.py](capture.py) (issue #191) drives git-agent's real, approved
`issue_resolution` graph through its own human_approval node and observed
zero retry attempts (`retryAttemptsObserved: 0` in
[expected.json](fixtures/human-approval-interrupt-resume/expected.json)) --
that fixture's own README says the separate retry case "is a separate,
smaller fixture (#194), not grown from this one." Growing that real graph, or
campaign-agent's real gates (#192/#193, not yet built), to force a retry path
would violate #181's "do not grow the full campaign/git-agent input to test
retry mechanics."

This script instead reuses #191's cheaper harness -- its `_RecordingObserver`
event shape (`nodeId`/`runId`/`invocationRunId`/`nodeOccurrence`, step and
attempt occurrences counted on separate counters) and its capture/replay/
fixture conventions -- against the smallest possible graph: one node, one
real LangGraph `RetryPolicy`, no `interrupt()`, no `Command(resume=...)`, no
second invocation. It needs no external consumer checkout at all: `langgraph`
is already a direct dependency of this repo's own
`packages/python/langgraph` package (pinned `>=1.2.10,<=1.2.11`, matching the
`1.2.11` git-agent and campaign-agent both resolve to), so there is nothing
cheaper to reuse than the dependency already in this repo's own lockfile.

The point of the fixture is what it does *not* vary: `runId` and
`invocationRunId` stay constant across the whole capture (there is no resume
here -- one `invoke()`, no pause), while `attemptNumber` goes 1 -> 2 and the
node's own step-occurrence counter stays at 1 throughout, because one
step -- one real pass through the node's logic that returns state -- happens
to require two attempts. Conflating "how many times was this node stepped
into" with "how many attempts did this node's retry policy take" would
misreport a single occurrence as two, or vice versa; keeping them on
independent counters (as #191's `_RecordingObserver` already does) is the
fact this fixture exists to evidence.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_TIMESTAMP = "2026-09-17T00:00:00Z"
SCENARIO = "repeat-attempt"
RUN_ID = "capture-thread-repeat-attempt-1"
INVOCATION_RUN_ID = "invocation-1"
NODE_ID = "flaky_step"


class _RecordingObserver:
    """Same event shape as capture.py's `_RecordingObserver` (issue #191):
    `nodeId` (static call site), `runId` (logical run), `invocationRunId`
    (which `invoke()` call), and `nodeOccurrence` (this node's Nth observed
    *step* occurrence, counted separately from its Nth *attempt*
    occurrence). This fixture only ever uses one `invocationRunId` -- there
    is no resume to distinguish here, only the retry axis.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._sequence = 0
        self._step_occurrence: dict[str, int] = {}
        self._attempt_occurrence: dict[str, int] = {}

    def _record(
        self,
        event_type: str,
        node_id: str,
        occurrence_counts: dict[str, int],
        fields: dict[str, Any],
    ) -> None:
        self._sequence += 1
        occurrence_counts[node_id] = occurrence_counts.get(node_id, 0) + 1
        self.events.append(
            {
                "sequence": self._sequence,
                "eventType": event_type,
                "nodeId": node_id,
                "runId": RUN_ID,
                "invocationRunId": INVOCATION_RUN_ID,
                "nodeOccurrence": occurrence_counts[node_id],
                **fields,
            }
        )

    def step(self, *, node_id: str, outcome: str) -> None:
        self._record(f"step.{outcome}", node_id, self._step_occurrence, {})

    def attempt(self, *, node_id: str, number: int, outcome: str) -> None:
        self._record(
            f"attempt.{outcome}",
            node_id,
            self._attempt_occurrence,
            {"metadata": {"attemptNumber": number}},
        )


def _capture() -> dict[str, Any]:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import RetryPolicy

    langgraph_version = importlib.metadata.version("langgraph")
    observer = _RecordingObserver()
    attempt_counter = {"n": 0}

    def flaky_step(state: dict[str, Any]) -> dict[str, Any]:
        attempt_counter["n"] += 1
        number = attempt_counter["n"]
        if number == 1:
            observer.attempt(node_id=NODE_ID, number=number, outcome="failed")
            raise ConnectionError("simulated-transient-failure")
        observer.attempt(node_id=NODE_ID, number=number, outcome="passed")
        observer.step(node_id=NODE_ID, outcome="passed")
        return {"visited": [*state.get("visited", []), NODE_ID]}

    builder = StateGraph(dict)
    builder.add_node(
        NODE_ID,
        flaky_step,
        retry_policy=RetryPolicy(
            max_attempts=2, initial_interval=0.01, backoff_factor=1.0, jitter=False
        ),
    )
    builder.add_edge(START, NODE_ID)
    builder.add_edge(NODE_ID, END)
    compiled = builder.compile(checkpointer=InMemorySaver())

    config = {
        "configurable": {"thread_id": RUN_ID},
        "run_id": INVOCATION_RUN_ID,
    }
    result = compiled.invoke({}, config=config)
    paused = "__interrupt__" in result

    return {
        "traceVersion": "1",
        "provenance": {
            "kind": "sanitized-synthetic-minimal-fixture",
            "consumer": None,
            "framework": {"name": "langgraph", "version": langgraph_version},
            "generator": (
                "docs/research/internal-consumer/git-agent/capture/"
                "capture_repeat_attempt.py"
            ),
            "scenario": SCENARIO,
            "captureMechanism": (
                "one-node synthetic StateGraph with a real LangGraph "
                "RetryPolicy(max_attempts=2); no interrupt(), no "
                "Command(resume=...), no second invoke() call -- reuses "
                "capture.py's (#191) _RecordingObserver event shape rather "
                "than growing git-agent's or campaign-agent's real graphs "
                "to force a retry path"
            ),
            "generatedAt": FIXTURE_TIMESTAMP,
            "sanitization": [
                "thread_id/run_id/invocationRunId are host-chosen literals, "
                "never real UUIDs",
                "no external consumer checkout is read or referenced: this "
                "graph is entirely synthetic, built only against langgraph "
                "(already a direct dependency of this repo's own "
                "packages/python/langgraph package)",
                "no prompts, payloads, paths, or credentials enter observer metadata",
                "no repository mutation, model call, push, or GitHub effect occurs",
            ],
            "unresolvedEvidence": [],
        },
        "invocations": [
            {
                "label": (
                    "invocation-1 (single invoke(); node retries in-process, no pause)"
                ),
                "run_id": INVOCATION_RUN_ID,
                "paused": paused,
                "pausedAtNodeId": NODE_ID if paused else None,
            }
        ],
        "finalOutcome": "visited" if not paused else None,
        "events": observer.events,
    }


def capture(output_dir: Path) -> Path:
    trace = _capture()
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / "trace.json"
    trace_path.write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return trace_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=f"defaults to fixtures/{SCENARIO}/ next to this script",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (CAPTURE_DIR / "fixtures" / SCENARIO)
    trace_path = capture(output_dir)
    print(f"Wrote {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
