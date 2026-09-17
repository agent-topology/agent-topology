#!/usr/bin/env python3
"""Capture a sanitized real interrupt/resume trace through git-agent's actual
`human_approval` node (issue #191, advancing #181's first acceptance bullet),
against a source-pinned git-agent checkout at the exact commit already
reviewed statically in ../README.md.

Unlike agent-workflow-core's capture_dynamic.py (issue #152), which built a
synthetic one-node demo graph around the real `interrupt()` primitive, this
drives git-agent's real, approved `issue_resolution` graph
(`git_agent.graphs.issue_resolution.create_graph`) through the exact
fake-input/fake-port fixtures git-agent's own test suite uses to reach
`human_approval` --
`tests/graphs/test_issue_resolution_nodes.py::test_complete_red_interrupt_observes_steps_and_model_attempts`
-- rather than hand-building new fake ports. Per #181: "Do not substitute a
generic synthetic interrupt for these consumer wiring proofs." No repository
mutation, model call, push, or GitHub effect is real: every port is scripted.

This script must run with git-agent's own interpreter (its `.venv/bin/python`)
so it imports the real `git_agent` and `agent_workflow_core` packages exactly
as git-agent's own tests do, at the exact dependency versions its lockfile
pins (LangGraph 1.2.11). It only ever reads the pinned checkout (to import
`git_agent`/`agent_workflow_core` and to reuse the test fixture module) and
never writes to it.

Only one node in git-agent's production factory carries no checkpointer
(`create_graph(...).checkpointer is None` -- checkpointing is host
responsibility, per git-agent's own docs). This script attaches its own
`InMemorySaver` after compiling, which is what a real host integration must
also do to support resume.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_TIMESTAMP = "2026-09-17T00:00:00Z"
COMMIT = "b67cb35a6195609a5d89976768fb5a4884f17ca1"
REF = "main"
SCENARIO = "human-approval-interrupt-resume"
THREAD_ID = "capture-thread-human-approval-1"


def _verify_pinned_commit(consumer_src: Path) -> None:
    """Refuse to capture against anything but the exact pinned commit."""
    result = subprocess.run(
        ["git", "-C", str(consumer_src), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip()
    if head != COMMIT:
        raise SystemExit(
            f"--consumer-src {consumer_src} is at {head}, not the pinned commit "
            f"{COMMIT}. Check out that exact commit before capturing."
        )


def _load_fixtures(consumer_src: Path) -> Any:
    """Reuse git-agent's own fake-input/port test fixtures, not a rebuilt copy."""
    fixture_path = consumer_src / "tests" / "graphs" / "test_issue_resolution_nodes.py"
    spec = importlib.util.spec_from_file_location(
        "git_agent_test_fixtures", fixture_path
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load fixtures from {fixture_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _metadata_fields(metadata: Any) -> list[dict[str, Any]]:
    if metadata is None:
        return []
    fields = []
    for entry in metadata.fields:
        value = entry.value
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        fields.append({"name": entry.name, "kind": entry.kind.value, "value": value})
    return fields


def _metadata_node_id(metadata: Any) -> str | None:
    if metadata is None:
        return None
    for entry in metadata.fields:
        if entry.name == "node.id":
            return str(entry.value)
    return None


class _RecordingObserver:
    """Minimal RunObserver. Every event carries four independently distinct
    identities: `nodeId` (static call site), `runId` (logical run -- the one
    checkpoint thread both invocations share), `invocationRunId` (which
    `invoke()` call -- a fact this script itself knows, not derived from any
    event store), and `nodeOccurrence` (this node's Nth observed *step*
    occurrence across the whole logical run, so a node observed twice, as
    `human_approval` is here, is never conflated into one occurrence). Step
    and attempt occurrences are counted separately: a node's attempt-retry
    count (`attempt.number`, already explicit on each attempt event) is a
    different granularity than how many times the node itself was stepped
    into, and conflating the two under one counter would misrepresent one
    real step (that happens to make one real attempt) as two occurrences.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._sequence = 0
        self._step_occurrence: dict[str, int] = {}
        self._attempt_occurrence: dict[str, int] = {}
        self.invocation_run_id: str | None = None

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
                "runId": THREAD_ID,
                "invocationRunId": self.invocation_run_id,
                "nodeOccurrence": occurrence_counts[node_id],
                **fields,
            }
        )

    def step(self, *, node_id: str, outcome: Any, metadata: Any = None) -> None:
        self._record(
            f"step.{outcome.value}",
            node_id,
            self._step_occurrence,
            {"metadata": _metadata_fields(metadata)},
        )

    def attempt(
        self,
        *,
        number: int,
        profile_hash: str,
        outcome: Any,
        metadata: Any = None,
    ) -> None:
        node_id = _metadata_node_id(metadata) or "unknown-attempt-node"
        self._record(
            f"attempt.{outcome.value}",
            node_id,
            self._attempt_occurrence,
            {
                "metadata": {
                    "attemptNumber": number,
                    "profileHash": profile_hash,
                    "fields": _metadata_fields(metadata),
                }
            },
        )


def _capture(consumer_src: Path) -> dict[str, Any]:
    _verify_pinned_commit(consumer_src)
    fixtures = _load_fixtures(consumer_src)

    from git_agent.graphs.issue_resolution import create_graph
    from git_agent.ports import (
        FakeGitHubIssueMutatePort,
        GitHubIssueOperationKind,
        IssueMutationReceipt,
    )
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    policy = fixtures._policy()
    observer = _RecordingObserver()
    verification = fixtures.FakeVerificationCommandPort(
        [
            fixtures.VerificationEvidence(
                status=fixtures.VerificationStatus.RED,
                summary="bounded failure",
                exit_code=1,
            )
        ]
    )
    context = fixtures._context(verification=verification, observer=observer)
    grant = fixtures.AuthorizationGrant(
        repositories=(fixtures._repo(),),
        operations=(fixtures.EffectOperation.COMMENT_ISSUE,),
    )
    gateway = fixtures.FakeModelGateway(
        [
            fixtures.ModelOutcome(
                text=(
                    '{"cause":"test_failure","scope":"bounded",'
                    '"summary":"bounded failure","evidence":["bounded"]}'
                ),
                usage=dict(),
                response_model="model-v1",
            ),
            fixtures.ModelOutcome(
                text=(
                    '{"comment":"## Verification status\\n'
                    'Verification is red: bounded failure"}'
                ),
                usage=dict(),
                response_model="model-v1",
            ),
        ]
    )
    context = replace(context, model_gateway=gateway, authorization_grant=grant)

    graph = create_graph(graph_id="issue_resolution", policy=policy)
    graph.checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": THREAD_ID}}

    invocations: list[dict[str, Any]] = []

    observer.invocation_run_id = "invocation-1"
    result1 = graph.invoke(
        fixtures._input().model_dump(), context=context, config=config
    )
    paused1 = "__interrupt__" in result1
    invocations.append(
        {
            "label": (
                "invocation-1 (real human_approval interrupt() call, graph pauses)"
            ),
            "run_id": "invocation-1",
            "paused": paused1,
            "pausedAtNodeId": "human_approval" if paused1 else None,
        }
    )
    if not paused1:
        raise SystemExit(
            "invocation-1 did not pause at human_approval; refusing to capture"
        )

    now = datetime.now(UTC)
    resume_value = {
        "decision": "approved",
        "approver_subject": "capture-harness-subject",
        "decided_at": (now - timedelta(seconds=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "draft_edits": {},
    }
    mutate_writer = fixtures._CombinedGitHubWriter()
    mutate_writer.mutate_issue = FakeGitHubIssueMutatePort(
        [
            IssueMutationReceipt(
                repository=fixtures._repo(),
                issue_number=12,
                kind=GitHubIssueOperationKind.COMMENT,
                mutation_id="capture-comment-1",
            )
        ]
    ).mutate_issue
    context2 = replace(context, github_writer=mutate_writer)

    observer.invocation_run_id = "invocation-2"
    result2 = graph.invoke(
        Command(resume=resume_value), context=context2, config=config
    )
    paused2 = "__interrupt__" in result2
    invocations.append(
        {
            "label": "invocation-2 (Command(resume=...), same checkpoint thread)",
            "run_id": "invocation-2",
            "paused": paused2,
            "pausedAtNodeId": "human_approval" if paused2 else None,
        }
    )

    final_outcome = result2.get("outcome")

    return {
        "traceVersion": "1",
        "provenance": {
            "kind": "sanitized-source-pinned-capture",
            "consumer": {
                "repository": "https://github.com/milocosmopolitan/git-agent",
                "ref": REF,
                "commit": COMMIT,
            },
            "framework": {"name": "langgraph", "version": "1.2.11"},
            "generator": (
                "docs/research/internal-consumer/git-agent/capture/capture.py"
            ),
            "scenario": SCENARIO,
            "captureMechanism": (
                "git_agent.graphs.issue_resolution.create_graph (real, approved "
                "graph); real langgraph.types.interrupt() inside the real "
                "human_approval node body; fake input/ports reused from "
                "git-agent's own test_complete_red_interrupt_observes_steps_and_"
                "model_attempts fixture; a host-attached InMemorySaver "
                "checkpointer, which git-agent's production factory does not "
                "itself provide"
            ),
            "generatedAt": FIXTURE_TIMESTAMP,
            "sanitization": [
                "thread_id and invocation_run_id are host-chosen literals, "
                "never real UUIDs",
                "the resume HumanApprovalResponse (decision/approver_subject/"
                "decided_at/expires_at) is a fabricated fixture value, not a "
                "real decision or authorization payload",
                "plan_hash/policy_hash/authorization_hash appear only as "
                "opaque hex digests already treated as safe by git-agent's own "
                "observer metadata contract (never raw plan/payload content)",
                "no prompts, payloads, paths, or credentials enter observer "
                "metadata -- enforced structurally by "
                "agent_workflow_core.observers.MetadataField, not by this "
                "script",
                "no real GitHub/git effect occurred: the issue-comment port is "
                "scripted (FakeGitHubIssueMutatePort), the same fake used by "
                "git-agent's own tests",
            ],
            "unresolvedEvidence": [],
        },
        "invocations": invocations,
        "finalOutcome": final_outcome,
        "events": observer.events,
    }


def capture(consumer_src: Path, output_dir: Path) -> Path:
    trace = _capture(consumer_src)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / "trace.json"
    trace_path.write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return trace_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--consumer-src",
        type=Path,
        required=True,
        help=f"path to a git-agent checkout at the pinned commit {COMMIT}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "defaults to fixtures/human-approval-interrupt-resume/ next to this script"
        ),
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (
        CAPTURE_DIR / "fixtures" / "human-approval-interrupt-resume"
    )
    trace_path = capture(args.consumer_src, output_dir)
    print(f"Wrote {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
