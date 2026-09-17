#!/usr/bin/env python3
"""Capture a sanitized real trace through one of campaign-agent's six
`declare_children`-verified real parent/child relationships (issue #193,
advancing #181 past #192's campaign gate capture, using the fake-port harness
precedent it set). The chosen relationship is `channel_concept`'s
`prepare_brief` node calling its declared child `copy_brief_prepare` -- the
exact example the issue names -- against the source-pinned campaign-agent
checkout at the commit
docs/research/internal-consumer/campaign-agent/review-2026-09-17-declared-children.md
already proved all six relationships hold statically for.

This does two things that neither #192's capture nor
../verify_declared_children.py did alone:

1. Calls `agent_topology.langgraph.describe()` on the *exact* compiled
   `channel_concept` object this script goes on to execute for real (not a
   separately-recompiled standalone instance), confirming the depth-0
   `x-topology-interpretation` fact for `prepare_brief` is `status: known`,
   `evidence.kind: declared-child-call` -- the accepted mapping from #180 /
   `_describe.py:301-359` -- exactly as ../verify_declared_children.py already
   confirmed for a fresh, never-invoked instance (this script reuses that same
   assertion but on an instance it is about to run).
2. Drives that same compiled graph through a real invocation reaching
   `prepare_brief`, and installs a `CompiledStateGraph.invoke` spy that
   records, for every nested `child.invoke(...)` call `prepare_brief`
   (`draft_copy`, `review_copy`) makes, whether the object `.invoke()` was
   called on `is` (Python object identity, not a name comparison) the exact
   compiled child `describe()` resolved as that node's declared child via
   `compiled.__agent_topology_children__`. This is the runtime half of the
   "declared-child-call" evidence kind: #180/#181's static check confirms the
   *declaration*; this confirms the declared object is what the parent node
   *actually calls* at runtime, correlated by identity, not display name.

`describe()` is imported from *this* repository's own
`packages/python/langgraph/src` (ahead of campaign-agent's own pinned
`agent-topology-langgraph` git dependency, which may be a different
revision), matching ../verify_declared_children.py's sys.path precedent --
this capture demonstrates this repository's current `_describe.py`, not
whatever revision campaign-agent's lockfile happens to pin.

Reuses campaign-agent's own `tests/channel_concept/support.py` and
`tests/notifications/support.py` (imported read-only via sys.path, never
modified or copied) -- the same fake `ModelGateway`/notification-store
fixtures `tests/channel_concept/test_channel_concept.py`'s own
`test_select_produces_approved_carrying_selection_and_comparison` uses to
reach `prepare_brief`/`draft_copy`/`review_copy`'s real child invocations and
resume through `await_decision` to `approved`, per #181: "Do not substitute a
generic synthetic interrupt/wiring for these consumer wiring proofs." No
model call, notification send, or campaign/GitHub effect is real: every port
is scripted, and the notification store is a throwaway SQLite file in a
temporary directory, discarded after capture.

Must run with campaign-agent's own interpreter (its `.venv/bin/python`) so it
imports the real `campaign_agent`/`agent_workflow_core`/`langgraph` packages
at the exact dependency versions its lockfile pins.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

CAPTURE_DIR = Path(__file__).resolve().parent
CORE_ROOT = CAPTURE_DIR.parents[4]
FIXTURE_TIMESTAMP = "2026-09-17T00:00:00Z"
COMMIT = "a1532d5eed2d356792d5c3ee460d2bb8fb23db1e"
REF = "main"
SCENARIO = "prepare-brief-declared-child"
THREAD_ID = "capture-thread-declared-child-1"
PARENT_GRAPH_ID = "channel_concept"
RELATIONSHIP = {"nodeId": "prepare_brief", "declaredChildGraph": "copy_brief_prepare"}
SENTINELS = {"__start__", "__end__"}


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


def _core_commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(CORE_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _install_import_paths(consumer_src: Path) -> None:
    """Prepend this repo's own agent_topology sources, then campaign-agent's
    own src/ and checkout root, matching ../verify_declared_children.py's
    precedent. Deliberately does not add CORE_ROOT itself to sys.path, so
    `import tests...` below resolves to campaign-agent's own `tests` package,
    not this repository's own top-level `tests/`."""
    sys.path[:0] = [
        str(CORE_ROOT / "packages" / "python" / "spec" / "src"),
        str(CORE_ROOT / "packages" / "python" / "langgraph" / "src"),
        str(consumer_src / "src"),
        str(consumer_src),
    ]


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
    """Records three independent, real event sources onto one sequence, each
    tagged with `nestedUnderNodeId`: which declared-child call (if any) was
    in flight when the event was observed, derived from the invoke-spy's own
    identity checks below -- the parent/child correlation this issue asks
    for, not inferred from node-name resemblance.

    - `record_debug_task_result`: one event per LangGraph `stream_mode=
      "debug"` `task_result` chunk. Only ever fires for `channel_concept`'s
      own top-level nodes: a nested `child.invoke(...)` call runs entirely
      inside one parent node's synchronous execution, invisible to the outer
      graph's own debug stream -- a real boundary this capture documents by
      recording `nestedUnderNodeId: null` on every such event, not by
      omission.
    - `step`/`attempt`: real `agent_workflow_core.observers.RunObserver`
      callbacks. The same recorder instance is threaded into every declared
      child's own `RuntimeContext.observer` (see `_prepare_brief` et al. in
      `channel_concept/graph.py`), so this is the only mechanism that
      observes a declared child's *own* node identity (e.g.
      `select_evidence`, owned by `copy_brief_prepare`) at all.
    - `declared_child_call`: one event per nested `child.invoke(...)` call,
      recording whether the invoked object `is` the declared child
      `describe()` resolved for that node.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._sequence = 0
        self._task_occurrence: dict[str, int] = {}
        self._observer_step_occurrence: dict[str, int] = {}
        self._observer_attempt_occurrence: dict[str, int] = {}
        self._declared_child_call_occurrence: dict[str, int] = {}
        self.invocation_run_id: str | None = None
        self.nesting_stack: list[str] = []

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _nested_under(self) -> str | None:
        return self.nesting_stack[-1] if self.nesting_stack else None

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
                "nestedUnderNodeId": self._nested_under(),
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
                "nestedUnderNodeId": self._nested_under(),
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
                "nestedUnderNodeId": self._nested_under(),
            }
        )

    def declared_child_call(
        self, *, node_id: str, identity_confirmed: bool, child_graph_name: str | None
    ) -> None:
        self._declared_child_call_occurrence[node_id] = (
            self._declared_child_call_occurrence.get(node_id, 0) + 1
        )
        self.events.append(
            {
                "sequence": self._next_sequence(),
                "eventType": "invoke.declared-child-call",
                "nodeId": node_id,
                "runId": THREAD_ID,
                "invocationRunId": self.invocation_run_id,
                "nodeOccurrence": self._declared_child_call_occurrence[node_id],
                "declaredChildIdentityConfirmed": identity_confirmed,
                "declaredChildGraphName": child_graph_name,
            }
        )


def _install_invoke_spy(recorder: _Recorder, declared: dict[str, Any]):
    """Patch `CompiledStateGraph.invoke` so every nested `child.invoke(...)`
    call `prepare_brief`/`draft_copy`/`review_copy` makes is attributed to
    its declared node id by object identity (`is`), never by name -- the
    same check `_describe.py`'s `_declared_child()` performs, applied to the
    object that is actually invoked at runtime rather than only to static
    metadata. Refuses (does not guess) if a nested call matches none of the
    three declared children."""
    from langgraph.graph.state import CompiledStateGraph

    original_invoke = CompiledStateGraph.invoke

    def spy(self, *args, **kwargs):
        node_id = next((n for n, child in declared.items() if child is self), None)
        if node_id is None:
            raise SystemExit(
                "a nested CompiledStateGraph.invoke() call matched none of "
                "channel_concept's declared children by identity; refusing "
                "to guess which relationship this is"
            )
        recorder.nesting_stack.append(node_id)
        try:
            result = original_invoke(self, *args, **kwargs)
        finally:
            recorder.nesting_stack.pop()
        recorder.declared_child_call(
            node_id=node_id,
            identity_confirmed=declared[node_id] is self,
            child_graph_name=self.get_name(),
        )
        return result

    return patch.object(CompiledStateGraph, "invoke", spy)


def _compile_standalone(name: str):
    import importlib

    support = importlib.import_module(f"tests.{name}.support")
    factory = importlib.import_module(f"campaign_agent.{name}").create_graph
    return factory(graph_id=name, policy=support.policy())


def _static_evidence(compiled: Any) -> dict[str, Any]:
    """Reproduces ../verify_declared_children.py's per-relationship check,
    scoped to the one relationship this issue names, on the exact compiled
    object this script goes on to run -- with CompiledStateGraph.invoke/
    ainvoke patched to raise, confirming describe() itself never executes
    anything, exactly as ../verify_declared_children.py established."""
    from agent_topology.langgraph import describe
    from agent_topology.spec import validate_document
    from langgraph.graph.state import CompiledStateGraph

    node_id = RELATIONSHIP["nodeId"]
    child_name = RELATIONSHIP["declaredChildGraph"]

    with (
        patch.object(
            CompiledStateGraph, "invoke", side_effect=AssertionError("workflow invoked")
        ),
        patch.object(
            CompiledStateGraph,
            "ainvoke",
            side_effect=AssertionError("workflow invoked"),
        ),
    ):
        standalone = _compile_standalone(child_name)
        standalone_doc = describe(standalone, graph_id=child_name, depth=0, strict=True)
        assert validate_document(standalone_doc) == []
        standalone_structure = next(
            g for g in standalone_doc["graphs"] if g["id"] == child_name
        )["structure"]
        standalone_node_ids = frozenset(
            n["id"] for n in standalone_structure["nodes"] if n["id"] not in SENTINELS
        )

        depth0 = describe(compiled, graph_id=PARENT_GRAPH_ID, depth=0, strict=True)
        assert validate_document(depth0) == []
        depth0_graph = next(g for g in depth0["graphs"] if g["id"] == PARENT_GRAPH_ID)
        depth0_facts = {
            n["nodeId"]: n["subgraph"]
            for n in depth0_graph["x-topology-interpretation"]["nodes"]
            if "subgraph" in n
        }

        depth2 = describe(compiled, graph_id=PARENT_GRAPH_ID, depth=2, strict=True)
        assert validate_document(depth2) == []
        depth2_graph = next(g for g in depth2["graphs"] if g["id"] == PARENT_GRAPH_ID)
        depth2_nodes_by_id = {n["id"]: n for n in depth2_graph["structure"]["nodes"]}
        depth2_graphs_by_id = {g["id"]: g for g in depth2["graphs"]}

    fact = depth0_facts[node_id]
    if fact["status"] != "known" or fact["evidence"]["kind"] != "declared-child-call":
        raise SystemExit(
            f"depth-0 subgraph fact for {node_id} is not a known "
            f"declared-child-call; refusing to capture: {fact}"
        )

    subgraph_id = depth2_nodes_by_id[node_id].get("subgraphId")
    expected_subgraph_id = f"{PARENT_GRAPH_ID}:{node_id}"
    if subgraph_id != expected_subgraph_id:
        raise SystemExit(
            f"materialized subgraphId for {node_id} was {subgraph_id!r}, "
            f"expected {expected_subgraph_id!r}"
        )
    materialized = depth2_graphs_by_id[subgraph_id]["structure"]
    materialized_node_ids = frozenset(
        n["id"] for n in materialized["nodes"] if n["id"] not in SENTINELS
    )
    matches_standalone = materialized_node_ids == standalone_node_ids

    unresolved: list[dict[str, Any]] = []
    for doc, depth in ((depth0, 0), (depth2, 2)):
        for gap in doc["completeness"]["gaps"]:
            unresolved.append({"traversalDepth": depth, **gap})

    return {
        "relationship": {
            "parent": PARENT_GRAPH_ID,
            "nodeId": node_id,
            "declaredChildGraph": child_name,
            "depth0Evidence": fact["evidence"],
            "materializedSubgraphId": subgraph_id,
            "materializedNodeCount": len(materialized_node_ids),
            "matchesStandaloneFactory": matches_standalone,
        },
        "unresolvedTopologyEvidence": unresolved,
    }


def _capture(consumer_src: Path) -> dict[str, Any]:
    _verify_pinned_commit(consumer_src)
    _install_import_paths(consumer_src)

    import tests.channel_concept.support as ccs
    import tests.notifications.support as notif_support
    from agent_workflow_core.ports import FakeModelGateway
    from langgraph.types import Command

    p = ccs.policy()
    compiled = ccs.graph(p)
    declared = dict(getattr(compiled, "__agent_topology_children__", {}))
    if RELATIONSHIP["nodeId"] not in declared:
        raise SystemExit(
            f"{RELATIONSHIP['nodeId']} is not a declared child of "
            f"{PARENT_GRAPH_ID}; refusing to capture"
        )

    static_evidence = _static_evidence(compiled)

    recorder = _Recorder()
    invoke_patch = _install_invoke_spy(recorder, declared)
    config = {"configurable": {"thread_id": THREAD_ID}}

    with tempfile.TemporaryDirectory() as tmp:
        stores = notif_support.Stores(Path(tmp) / "notify.db")
        notif_exec = notif_support.executor(stores)

        outcomes = ccs.direction_outcomes() + [ccs.compare_candidate_outcome(("d1",))]
        ctx1 = replace(
            ccs.context(FakeModelGateway(outcomes), notification_executor=notif_exec),
            observer=recorder,
        )

        recorder.invocation_run_id = "invocation-1"
        with invoke_patch:
            for chunk in compiled.stream(
                {"raw_input": ccs.raw_input(variation_count=1)},
                config,
                context=ctx1,
                stream_mode="debug",
            ):
                recorder.record_debug_task_result(chunk)

        state1 = compiled.get_state(config)
        paused1 = "await_decision" in state1.next
        if not paused1:
            raise SystemExit(
                "invocation-1 did not pause at await_decision; refusing to capture"
            )
        invocations: list[dict[str, Any]] = [
            {
                "label": (
                    "invocation-1 (real prepare_brief -> copy_brief_prepare "
                    "child.invoke(), draft_copy, review_copy, graph pauses "
                    "at await_decision)"
                ),
                "run_id": "invocation-1",
                "paused": True,
                "pausedAtNodeId": "await_decision",
            }
        ]

        decision = {
            "decision_id": "dec-1",
            "concept_run_id": state1.values["concept_run_id"],
            "gate_revision": state1.values["gate"]["gate_revision"],
            "action": "select",
            "actor_ref": "user-1",
            "selected_direction_id": "d1",
        }
        auth = ccs.auth(decision, authority="reviewer")
        ctx2 = replace(
            ccs.context(
                FakeModelGateway([]),
                notification_executor=notif_exec,
                decision_authorization=auth,
            ),
            observer=recorder,
        )

        recorder.invocation_run_id = "invocation-2"
        with invoke_patch:
            for chunk in compiled.stream(
                Command(resume=decision), config, context=ctx2, stream_mode="debug"
            ):
                recorder.record_debug_task_result(chunk)

        state2 = compiled.get_state(config)
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
        final_status = final_result.get("status") if final_result else None
        sends_count = len(stores.sends())

    return {
        "traceVersion": "1",
        "provenance": {
            "kind": "sanitized-source-pinned-capture",
            "consumer": {
                "repository": "https://github.com/milocosmopolitan/campaign-agent",
                "ref": REF,
                "commit": COMMIT,
            },
            "core": {
                "repository": "https://github.com/agent-topology/agent-topology",
                "commit": _core_commit(),
                "note": (
                    "this repository's own current agent_topology.langgraph/"
                    "agent_topology.spec sources (packages/python/{langgraph,"
                    "spec}/src), imported ahead of campaign-agent's own "
                    "pinned agent-topology-langgraph git dependency -- this "
                    "capture exercises this repository's live describe()/"
                    "declare_children implementation, not the revision "
                    "campaign-agent's own lockfile pins"
                ),
            },
            "framework": {"name": "langgraph", "version": "1.2.11"},
            "generator": (
                "docs/research/internal-consumer/campaign-agent/"
                "capture-declared-child/capture.py"
            ),
            "scenario": SCENARIO,
            "captureMechanism": (
                "campaign_agent.channel_concept.create_graph (real, approved "
                "graph); agent_topology.langgraph.describe() called on the "
                "exact compiled object before it is ever invoked (confirmed "
                "via a CompiledStateGraph.invoke/ainvoke patch that raises "
                "during describe(), same as verify_declared_children.py), "
                "asserting prepare_brief's depth-0 x-topology-interpretation "
                "subgraph fact is a known declared-child-call and its "
                "depth-2 materialized subgraph matches copy_brief_prepare's "
                "own standalone describe() output; then a real invocation "
                "through prepare_brief/draft_copy/review_copy for direction "
                "d1, resumed through await_decision to approved; a "
                "CompiledStateGraph.invoke spy records, for each nested "
                "child.invoke() call, whether the invoked object `is` "
                "(Python identity) the declared child describe() resolved "
                "for that node -- correlating the static declared-child-call "
                "evidence with the object actually invoked at runtime, not "
                "by display name; LangGraph's stream_mode='debug' task_result "
                "events and agent_workflow_core.observers.RunObserver "
                "step/attempt callbacks (threaded into every declared "
                "child's own RuntimeContext.observer) are recorded onto the "
                "same event sequence, each tagged nestedUnderNodeId from the "
                "invoke spy's own bookkeeping"
            ),
            "generatedAt": FIXTURE_TIMESTAMP,
            "sanitization": [
                "thread_id and invocation_run_id are host-chosen literals, "
                "never real UUIDs",
                "the resumed decision (decision_id/actor_ref/action/"
                "selected_direction_id) and its DecisionAuthorization are "
                "fabricated fixture values, not a real decision or "
                "authorization payload",
                "the captured direction/brief/draft/review content is "
                "entirely derived from campaign-agent's own fake "
                "model-gateway fixture text (direction_outcomes()/"
                "compare_candidate_outcome()), never a real model "
                "completion or real campaign content",
                "the notification store is a throwaway SQLite file in a "
                "temporary directory, discarded after capture, using "
                "tests.notifications.support's FakeSender -- no real "
                "notification is sent",
                "no prompts, model completions, paths, or credentials enter "
                "observer metadata -- enforced structurally by "
                "agent_workflow_core.observers.MetadataField, not by this "
                "script",
                "no real campaign/GitHub effect occurred",
            ],
            "unresolvedEvidence": static_evidence["unresolvedTopologyEvidence"],
        },
        "staticEvidence": static_evidence["relationship"],
        "invocations": invocations,
        "finalOutcome": final_status,
        "notificationSendsObserved": sends_count,
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
        help=("defaults to fixtures/prepare-brief-declared-child/ next to this script"),
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (
        CAPTURE_DIR / "fixtures" / "prepare-brief-declared-child"
    )
    trace_path = capture(args.consumer_src, output_dir)
    print(f"Wrote {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
