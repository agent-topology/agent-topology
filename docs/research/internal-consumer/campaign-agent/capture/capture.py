#!/usr/bin/env python3
"""Capture a sanitized real interrupt/resume trace through campaign-agent's
actual `await_decision` node (issue #192, advancing #181's first acceptance
bullet and its "campaign actual gate" companion to #191's git-agent capture),
against a source-pinned campaign-agent checkout at the exact commit the
issue names (`campaign_contract.py:449-469` at
`a1532d5eed2d356792d5c3ee460d2bb8fb23db1e`).

Unlike ../../git-agent/capture/capture.py, campaign-agent's own graph code
never calls `RunObserver` for `await_decision` (or for `validate_input`,
`gate_readiness_check`, `apply_decision`, or the terminal outcome nodes):
grepping the pinned `agent_workflow_core` package shows `observe_step` /
`observe_attempt` are only ever called from `execution/contracts.py`,
`execution/model_step.py`, and `routing.py`'s `route_model_node` -- i.e. only
from the two model nodes (`draft_rules`, `draft_concept`) that
`create_model_step` wraps. git-agent's `human_approval` is unusual in calling
`observe_step` itself; campaign_contract's `await_decision` does not, so a
git-agent-style `RunObserver` alone cannot show it ran twice. This capture
instead reads node/task identity from LangGraph's own `stream_mode="debug"`
events, which exist for every node regardless of whether that consumer's code
touches the observer -- a strictly more general mechanism than #191 needed. A
`RunObserver` is still attached to independently record the two real model
attempts (`draft_rules`, `draft_concept`), which *do* call it (via a
`"node.id"` metadata field `route_model_node` attaches, the same field
git-agent's capture reads), and this capture cross-checks that the observer's
occurrence counts for those two nodes agree with the debug-stream's.

Reuses campaign-agent's own `tests/campaign_contract/test_campaign_contract.py`
(loaded read-only, not modified or copied) and its `support.py` fixture module
-- the same fake `ModelGateway`/`DecisionAuthorization` fixtures campaign-
agent's own `test_approve_produces_canonical_hash_with_no_duplicate_fields`
uses to reach `await_decision`'s real `interrupt()` call, per #181: "Do not
substitute a generic synthetic interrupt for these consumer wiring proofs."
No repository mutation, model call, push, notification, or campaign/GitHub
effect is real: every port is scripted, and this scenario never exercises any
port beyond the fake model gateway and an in-memory checkpointer -- unlike
git-agent's `human_approval`, campaign_contract's `await_decision` gate has no
downstream write port on this path at all.

This script must run with campaign-agent's own interpreter (its
`.venv/bin/python`) so it imports the real `campaign_agent` and
`agent_workflow_core` packages at the exact dependency versions its lockfile
pins (LangGraph 1.2.11, matching git-agent's). It only ever reads the pinned
checkout (to import `campaign_agent`/`agent_workflow_core` and to reuse the
test fixture module) and never writes to it.

`create_graph` compiles without a checkpointer (host responsibility, same
convention as git-agent); `support.graph()` attaches its own `InMemorySaver`
after compiling, which is what a real host integration must also do.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import types
from dataclasses import replace
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_TIMESTAMP = "2026-09-17T00:00:00Z"
COMMIT = "a1532d5eed2d356792d5c3ee460d2bb8fb23db1e"
REF = "main"
SCENARIO = "await-decision-interrupt-resume"
THREAD_ID = "capture-thread-await-decision-1"
FIXTURE_PACKAGE = "_campaign_agent_capture_fixtures"


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
    """Reuse campaign-agent's own campaign_contract test fixtures, not a
    rebuilt copy. `test_campaign_contract.py` does `from .support import
    ...`, so both files are registered as submodules of a throwaway package
    (never written to disk) rather than exec'd standalone, letting that
    relative import resolve exactly as it does under campaign-agent's own
    pytest run."""
    test_dir = consumer_src / "tests" / "campaign_contract"

    package = types.ModuleType(FIXTURE_PACKAGE)
    package.__path__ = [str(test_dir)]
    sys.modules[FIXTURE_PACKAGE] = package

    support_spec = importlib.util.spec_from_file_location(
        f"{FIXTURE_PACKAGE}.support", test_dir / "support.py"
    )
    if support_spec is None or support_spec.loader is None:
        raise SystemExit(f"cannot load fixtures from {test_dir / 'support.py'}")
    support_module = importlib.util.module_from_spec(support_spec)
    sys.modules[support_spec.name] = support_module
    support_spec.loader.exec_module(support_module)
    package.support = support_module

    test_path = test_dir / "test_campaign_contract.py"
    test_spec = importlib.util.spec_from_file_location(
        f"{FIXTURE_PACKAGE}.test_campaign_contract", test_path
    )
    if test_spec is None or test_spec.loader is None:
        raise SystemExit(f"cannot load fixtures from {test_path}")
    test_module = importlib.util.module_from_spec(test_spec)
    sys.modules[test_spec.name] = test_module
    test_spec.loader.exec_module(test_module)
    return test_module


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


class _Recorder:
    """Records two independent, real event sources onto one sequence:

    - `record_debug_task_result`: one event per LangGraph `stream_mode=
      "debug"` `task_result` chunk, for *every* node in the graph. This is
      the only source that observes `await_decision` at all (see module
      docstring) and is what proves it ran twice -- once interrupted, once
      to completion -- sharing one real LangGraph task id across both
      invocations (`taskId`, a fact this capture discovered, not asserted).
    - `step`/`attempt`: the real `agent_workflow_core.observers.RunObserver`
      callbacks, which only ever fire for `draft_rules`/`draft_concept`.
      `attempt()`'s protocol carries no `node_id` parameter, but
      `routing.route_model_node` attaches one as a `"node.id"` metadata
      field before calling it -- the same field git-agent's capture reads
      via `_metadata_node_id`.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._sequence = 0
        self._task_occurrence: dict[str, int] = {}
        self._observer_step_occurrence: dict[str, int] = {}
        self._observer_attempt_occurrence: dict[str, int] = {}
        self.invocation_run_id: str | None = None

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def record_debug_task_result(self, chunk: dict[str, Any]) -> None:
        if chunk.get("type") != "task_result":
            return
        payload = chunk["payload"]
        node_id = payload["name"]
        interrupted = bool(payload.get("interrupts"))
        errored = payload.get("error") is not None
        outcome = (
            "awaiting_approval" if interrupted else ("failed" if errored else "passed")
        )
        self._task_occurrence[node_id] = self._task_occurrence.get(node_id, 0) + 1
        self.events.append(
            {
                "sequence": self._next_sequence(),
                "eventType": f"task.{outcome}",
                "nodeId": node_id,
                "runId": THREAD_ID,
                "invocationRunId": self.invocation_run_id,
                "nodeOccurrence": self._task_occurrence[node_id],
                "taskId": payload["id"],
            }
        )

    def step(self, *, node_id: str, outcome: Any, metadata: Any = None) -> None:
        self._observer_step_occurrence[node_id] = (
            self._observer_step_occurrence.get(node_id, 0) + 1
        )
        self.events.append(
            {
                "sequence": self._next_sequence(),
                "eventType": f"observer.step.{outcome.value}",
                "nodeId": node_id,
                "runId": THREAD_ID,
                "invocationRunId": self.invocation_run_id,
                "nodeOccurrence": self._observer_step_occurrence[node_id],
                "metadata": _metadata_fields(metadata),
            }
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
        self._observer_attempt_occurrence[node_id] = (
            self._observer_attempt_occurrence.get(node_id, 0) + 1
        )
        self.events.append(
            {
                "sequence": self._next_sequence(),
                "eventType": f"observer.attempt.{outcome.value}",
                "nodeId": node_id,
                "runId": THREAD_ID,
                "invocationRunId": self.invocation_run_id,
                "nodeOccurrence": self._observer_attempt_occurrence[node_id],
                "metadata": {
                    "attemptNumber": number,
                    "profileHash": profile_hash,
                    "fields": _metadata_fields(metadata),
                },
            }
        )


def _capture(consumer_src: Path) -> dict[str, Any]:
    _verify_pinned_commit(consumer_src)
    fixtures = _load_fixtures(consumer_src)

    from langgraph.types import Command

    recorder = _Recorder()
    policy = fixtures.policy()
    graph = fixtures.graph(policy)
    config = fixtures._thread(THREAD_ID)

    gateway1 = fixtures.FakeModelGateway(
        [fixtures.rules_outcome(), fixtures.concept_outcome()]
    )
    ctx1 = replace(fixtures.context(gateway1), observer=recorder)

    recorder.invocation_run_id = "invocation-1"
    for chunk in graph.stream(
        {
            "raw_input": fixtures.raw_input(
                idea="Spring campaign",
                knowledge=[("src-1", "v1", "Spring sale runs March 1 to March 31.")],
            )
        },
        config,
        context=ctx1,
        stream_mode="debug",
    ):
        recorder.record_debug_task_result(chunk)

    state1 = graph.get_state(config)
    paused1 = "await_decision" in state1.next
    if not paused1:
        raise SystemExit(
            "invocation-1 did not pause at await_decision; refusing to capture"
        )
    interrupt_value = state1.tasks[0].interrupts[0].value
    invocations: list[dict[str, Any]] = [
        {
            "label": (
                "invocation-1 (real await_decision interrupt() call, graph pauses)"
            ),
            "run_id": "invocation-1",
            "paused": True,
            "pausedAtNodeId": "await_decision",
            "interruptValue": interrupt_value,
        }
    ]

    contract_id = state1.values["contract_id"]
    decision = fixtures._approve_decision(contract_id)
    auth = fixtures._auth(decision, authority="reviewer")
    gateway2 = fixtures.FakeModelGateway([])
    ctx2 = replace(
        fixtures.context(gateway2, decision_authorization=auth), observer=recorder
    )

    recorder.invocation_run_id = "invocation-2"
    for chunk in graph.stream(
        Command(resume=decision), config, context=ctx2, stream_mode="debug"
    ):
        recorder.record_debug_task_result(chunk)

    state2 = graph.get_state(config)
    paused2 = bool(state2.next)
    invocations.append(
        {
            "label": "invocation-2 (Command(resume=...), same checkpoint thread)",
            "run_id": "invocation-2",
            "paused": paused2,
            "pausedAtNodeId": "await_decision" if paused2 else None,
        }
    )

    final_result = state2.values.get("result")
    final_outcome = final_result.get("status") if final_result else None

    return {
        "traceVersion": "1",
        "provenance": {
            "kind": "sanitized-source-pinned-capture",
            "consumer": {
                "repository": "https://github.com/milocosmopolitan/campaign-agent",
                "ref": REF,
                "commit": COMMIT,
            },
            "framework": {"name": "langgraph", "version": "1.2.11"},
            "generator": (
                "docs/research/internal-consumer/campaign-agent/capture/capture.py"
            ),
            "scenario": SCENARIO,
            "captureMechanism": (
                "campaign_agent.campaign_contract.create_graph (real, approved "
                "graph); real langgraph.types.interrupt() inside the real "
                "await_decision node body; fake model gateway and "
                "DecisionAuthorization reused from campaign-agent's own "
                "test_approve_produces_canonical_hash_with_no_duplicate_fields "
                "fixture; a host-attached InMemorySaver checkpointer, which "
                "campaign-agent's production factory does not itself provide; "
                "node/task identity read from LangGraph's own "
                "stream_mode='debug' task_result events (the only mechanism "
                "that observes await_decision at all -- campaign_contract's "
                "own code never calls RunObserver for it, unlike git-agent's "
                "human_approval), cross-checked against "
                "agent_workflow_core.observers.RunObserver step/attempt "
                "callbacks for the two nodes (draft_rules, draft_concept) "
                "that do call it"
            ),
            "generatedAt": FIXTURE_TIMESTAMP,
            "sanitization": [
                "thread_id and invocation_run_id are host-chosen literals, "
                "never real UUIDs",
                "the resumed DecisionInput (decision_id/actor_ref/"
                "artifact_or_revision/action) and its DecisionAuthorization "
                "are fabricated fixture values, not a real decision or "
                "authorization payload",
                "the captured interrupt proposal (concept/rules/readiness/"
                "gate) is entirely derived from campaign-agent's own fake "
                "model-gateway fixture text (rules_outcome()/"
                "concept_outcome()), never a real model completion or real "
                "campaign content",
                "no prompts, model completions, paths, or credentials enter "
                "observer metadata -- enforced structurally by "
                "agent_workflow_core.observers.MetadataField, not by this "
                "script",
                "no real campaign/GitHub effect occurred: this scenario's "
                "await_decision gate exercises no write port at all -- only "
                "the fake model gateway and the in-memory checkpointer",
            ],
            "unresolvedEvidence": [],
        },
        "invocations": invocations,
        "finalOutcome": final_outcome,
        "events": recorder.events,
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
        help=f"path to a campaign-agent checkout at the pinned commit {COMMIT}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "defaults to fixtures/await-decision-interrupt-resume/ next to this script"
        ),
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (
        CAPTURE_DIR / "fixtures" / "await-decision-interrupt-resume"
    )
    trace_path = capture(args.consumer_src, output_dir)
    print(f"Wrote {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
