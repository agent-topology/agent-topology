#!/usr/bin/env python3
"""Capture sanitized observer events for a real dynamic interrupt-and-resume,
and a separate same-node repeated-attempt, through the real
`observer_from_runtime` bridge against a source-pinned agent-workflow-core
checkout.

This is the item-4 follow-up from ../../README.md's suggested work sequence
("Prove runtime enrichment (IC-03/06)"), pinned to the `main`
(876f6a8a4ba863424e1f85bc92f18dce59147957) commit already captured for
resume identity by [capture.py](capture.py) (issue #151) -- see that script
and ../README.md for why two commits were pinned there. Interrupt/resume and
retry are LangGraph-level mechanisms, not commit-specific behavior, so this
script only exercises `main`.

Two scenarios, each its own graph and its own fixture directory:

- `interrupt-resume`: a one-node graph whose node calls the real
  `agent_workflow_core.adapters.langgraph.approval.request_approval`, which
  calls the real `langgraph.types.interrupt`. The first `invoke()` pauses the
  graph; a second `invoke(Command(resume=...))` on the same thread resumes
  it. LangGraph re-runs the node body from its start on resume, so any
  observer call issued before the `interrupt()` call fires again -- this
  script records that, rather than assuming a single execution per node.
- `repeated-attempt`: a one-node graph with a real LangGraph `RetryPolicy`
  attached to the node. The node raises a retryable `ConnectionError` on its
  first attempt and succeeds on its second, within one `invoke()` call --  no
  checkpoint pause, no `Command(resume=...)`, no second invocation. This is
  the same-node retry case ADR-scoped as distinct from interrupt/resume.

Both graphs share one `EventGraphObserver`/`InMemoryEventStore` per scenario
(reused across a scenario's invoke calls, mirroring capture.py) and the same
sanitization rules as capture.py: run_id/thread_id/event_run_id are
host-chosen literals, never real UUIDs; the ApprovalEnvelope resume value is
a fabricated fixture, not a real decision; no prompts, payloads, paths, or
credentials enter observer metadata; event_id/occurred_at and the
LangGraph-minted interrupt id are omitted, sequence position is retained
instead.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_TIMESTAMP = "2026-09-15T00:00:00Z"
COMMIT = "876f6a8a4ba863424e1f85bc92f18dce59147957"
REF = "main"


def _verify_pinned_commit(core_src: Path) -> None:
    """Refuse to capture against anything but the exact pinned commit."""
    checkout_root = core_src.parent
    result = subprocess.run(
        ["git", "-C", str(checkout_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip()
    if head != COMMIT:
        raise SystemExit(
            f"--core-src {core_src} is at {head}, not the pinned main commit "
            f"{COMMIT}. Check out that exact commit before capturing."
        )


@dataclass(frozen=True)
class _RuntimeContext:
    graph_observer: Any
    graph_id: str
    subject_id: str
    subject_type: str
    semconv_version: str
    metadata: Any = None
    event_run_id: str | None = None


def _capture_interrupt_resume(core_src: Path) -> dict[str, Any]:
    sys.path.insert(0, str(core_src))
    from agent_workflow_core.adapters.langgraph.approval import request_approval
    from agent_workflow_core.adapters.langgraph.observer import observer_from_runtime
    from agent_workflow_core.events import InMemoryEventStore
    from agent_workflow_core.observers import (
        EventGraphObserver,
        StepOutcome,
        observe_step,
    )
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command

    store = InMemoryEventStore()
    graph_observer = EventGraphObserver(store)
    graph_id = "capture-demo-interrupt"
    event_run_id = "logical-run"

    def approve(state: dict[str, Any], runtime: Any) -> dict[str, Any]:
        observer = observer_from_runtime(runtime)
        observe_step(observer, node_id="approve", outcome=StepOutcome.AWAITING_APPROVAL)
        envelope = request_approval({"action": "publish-report"})
        observe_step(observer, node_id="approve", outcome=StepOutcome.PASSED)
        return {"decision": envelope.decision.value}

    builder = StateGraph(dict, context_schema=_RuntimeContext)
    builder.add_node("approve", approve)
    builder.add_edge(START, "approve")
    builder.add_edge("approve", END)
    compiled = builder.compile(checkpointer=InMemorySaver())

    context = _RuntimeContext(
        graph_observer=graph_observer,
        graph_id=graph_id,
        subject_id="subject-1",
        subject_type="example.subject",
        semconv_version="1",
        event_run_id=event_run_id,
    )

    invocations: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    def _drain(invocation_run_id: str) -> None:
        after = events[-1]["sequence"] if events else 0
        records = store.query(
            graph_id=graph_id, run_id=event_run_id, after_sequence=after
        )
        for record in records:
            events.append(
                {
                    "sequence": record.sequence,
                    "eventType": record.event.event_type,
                    "graphId": record.event.graph_id,
                    "runId": record.event.run_id,
                    "nodeId": record.event.node_id,
                    "invocationRunId": invocation_run_id,
                }
            )

    config1 = {
        "configurable": {"thread_id": "thread-interrupt-1"},
        "run_id": "invocation-1",
    }
    result1 = compiled.invoke({}, context=context, config=config1)
    paused = "__interrupt__" in result1
    _drain("invocation-1")
    invocations.append(
        {
            "label": "invocation-1 (raises the real interrupt, graph pauses)",
            "run_id": "invocation-1",
            "paused": paused,
            "pausedAtNodeId": "approve" if paused else None,
        }
    )

    resume_value = {
        "interrupt_id": "interrupt-1",
        "decision": "approved",
        "approver_subject": "approver-1",
        "decided_at": "2026-09-15T00:00:00Z",
        "expires_at": "2026-09-16T00:00:00Z",
        "plan_hash": "a" * 64,
        "subject_revision_digest": "digest-1",
        "policy_hash": "policy-hash-1",
        "authorization_hash": "b" * 64,
    }
    config2 = {
        "configurable": {"thread_id": "thread-interrupt-1"},
        "run_id": "invocation-2",
    }
    result2 = compiled.invoke(
        Command(resume=resume_value), context=context, config=config2
    )
    _drain("invocation-2")
    invocations.append(
        {
            "label": "invocation-2 (Command(resume=...), same thread)",
            "run_id": "invocation-2",
            "paused": "__interrupt__" in result2,
            "pausedAtNodeId": None,
        }
    )

    return {
        "traceVersion": "1",
        "provenance": {
            "kind": "sanitized-source-pinned-capture",
            "consumer": {
                "repository": "https://github.com/milocosmopolitan/agent-workflow-core",
                "ref": REF,
                "commit": COMMIT,
            },
            "framework": {"name": "langgraph", "version": "1.2.11"},
            "generator": (
                "docs/research/internal-consumer/agent-workflow-core/capture/"
                "capture_dynamic.py"
            ),
            "scenario": "interrupt-resume",
            "captureMechanism": (
                "core EventGraphObserver + InMemoryEventStore; real "
                "langgraph.types.interrupt via "
                "agent_workflow_core.adapters.langgraph.approval.request_approval"
            ),
            "generatedAt": FIXTURE_TIMESTAMP,
            "sanitization": [
                "run_id, thread_id, and event_run_id are host-chosen literals, "
                "never real UUIDs",
                "the resume ApprovalEnvelope is a fabricated fixture value "
                "(hash-shaped literals), not a real decision or authorization payload",
                "the LangGraph-minted interrupt id and event_id/occurred_at are "
                "omitted; only their presence and sequence position are retained",
                "no prompts, payloads, paths, or credentials enter observer metadata",
            ],
        },
        "invocations": invocations,
        "events": events,
    }


def _capture_repeated_attempt(core_src: Path) -> dict[str, Any]:
    sys.path.insert(0, str(core_src))
    from agent_workflow_core.adapters.langgraph.observer import observer_from_runtime
    from agent_workflow_core.events import InMemoryEventStore
    from agent_workflow_core.observers import (
        AttemptOutcome,
        EventGraphObserver,
        MetadataField,
        MetadataKind,
        ObserverMetadata,
        observe_attempt,
    )
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import RetryPolicy

    store = InMemoryEventStore()
    graph_observer = EventGraphObserver(store)
    graph_id = "capture-demo-repeat"
    event_run_id = "logical-run-repeat"
    attempt_counter = {"n": 0}

    def act(state: dict[str, Any], runtime: Any) -> dict[str, Any]:
        observer = observer_from_runtime(runtime)
        attempt_counter["n"] += 1
        number = attempt_counter["n"]
        node_meta = ObserverMetadata(
            fields=(MetadataField(name="node.id", kind=MetadataKind.KIND, value="act"),)
        )
        if number == 1:
            observe_attempt(
                observer,
                number=number,
                profile_hash="profile-hash-1",
                outcome=AttemptOutcome.FAILED,
                metadata=node_meta,
            )
            raise ConnectionError("simulated-transient-failure")
        observe_attempt(
            observer,
            number=number,
            profile_hash="profile-hash-1",
            outcome=AttemptOutcome.PASSED,
            metadata=node_meta,
        )
        return {"visited": [*state.get("visited", []), "act"]}

    builder = StateGraph(dict, context_schema=_RuntimeContext)
    builder.add_node(
        "act",
        act,
        retry_policy=RetryPolicy(
            max_attempts=2, initial_interval=0.01, backoff_factor=1.0, jitter=False
        ),
    )
    builder.add_edge(START, "act")
    builder.add_edge("act", END)
    compiled = builder.compile(checkpointer=InMemorySaver())

    context = _RuntimeContext(
        graph_observer=graph_observer,
        graph_id=graph_id,
        subject_id="subject-1",
        subject_type="example.subject",
        semconv_version="1",
        event_run_id=event_run_id,
    )
    config = {
        "configurable": {"thread_id": "thread-repeat-1"},
        "run_id": "invocation-1",
    }
    compiled.invoke({}, context=context, config=config)

    events: list[dict[str, Any]] = []
    for record in store.query(graph_id=graph_id, run_id=event_run_id):
        fields = {field.name: field.value for field in record.event.metadata.fields}
        events.append(
            {
                "sequence": record.sequence,
                "eventType": record.event.event_type,
                "graphId": record.event.graph_id,
                "runId": record.event.run_id,
                "nodeId": record.event.node_id,
                "invocationRunId": "invocation-1",
                "metadata": {
                    "attemptNumber": fields.get("attempt.number"),
                    "profileHash": fields.get("profile.hash"),
                },
            }
        )

    return {
        "traceVersion": "1",
        "provenance": {
            "kind": "sanitized-source-pinned-capture",
            "consumer": {
                "repository": "https://github.com/milocosmopolitan/agent-workflow-core",
                "ref": REF,
                "commit": COMMIT,
            },
            "framework": {"name": "langgraph", "version": "1.2.11"},
            "generator": (
                "docs/research/internal-consumer/agent-workflow-core/capture/"
                "capture_dynamic.py"
            ),
            "scenario": "repeated-attempt",
            "captureMechanism": (
                "core EventGraphObserver + InMemoryEventStore; real LangGraph "
                "RetryPolicy re-running the same node within one invoke() call"
            ),
            "generatedAt": FIXTURE_TIMESTAMP,
            "sanitization": [
                "run_id, thread_id, and event_run_id are host-chosen literals, "
                "never real UUIDs",
                "profile_hash is a fabricated fixture literal, not a real "
                "policy/profile hash",
                "event_id/occurred_at are omitted; sequence position is retained "
                "instead",
                "no prompts, payloads, paths, or credentials enter observer metadata",
            ],
        },
        "invocations": [
            {
                "label": "invocation-1 (single invoke(); node retries in-process)",
                "run_id": "invocation-1",
                "paused": False,
                "pausedAtNodeId": None,
            }
        ],
        "events": events,
    }


def capture(scenario: str, core_src: Path, output_dir: Path) -> Path:
    _verify_pinned_commit(core_src)
    if scenario == "interrupt-resume":
        trace = _capture_interrupt_resume(core_src)
    else:
        trace = _capture_repeated_attempt(core_src)

    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / "trace.json"
    trace_path.write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return trace_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario", choices=("interrupt-resume", "repeated-attempt"), required=True
    )
    parser.add_argument(
        "--core-src",
        type=Path,
        required=True,
        help="path to <checkout>/src of an agent-workflow-core worktree at the pinned "
        f"main commit {COMMIT}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="defaults to fixtures/<scenario>/ next to this script",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (CAPTURE_DIR / "fixtures" / args.scenario)
    trace_path = capture(args.scenario, args.core_src, output_dir)
    print(f"Wrote {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
