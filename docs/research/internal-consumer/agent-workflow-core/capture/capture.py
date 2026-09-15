#!/usr/bin/env python3
"""Capture sanitized observer events from a source-pinned agent-workflow-core
checkout, through a real two-node LangGraph 1.2.11 graph and the real
`observer_from_runtime` bridge.

This script requires local read access to an agent-workflow-core checkout at
the exact pinned commit (see ../README.md and ../snapshot.json); it is not run
in CI and its output is not required to reproduce the correlation itself --
only the committed fixtures under `fixtures/` are (see `replay.py`).

Two commits are pinned separately because they expose different capabilities,
not just a different package version (both report `0.1.0b3`):

- `tag`  (v0.1.0.beta.3, 94cd31f58d8e94d55ea2d952c6db5508539ea53f): the
  observer bridge has no logical-run override, and `observers.py` has no
  `EventGraphObserver`/`EventStore` at all -- a host must supply its own
  `GraphObserver`/`RunObserver` implementation.
- `main` (876f6a8a4ba863424e1f85bc92f18dce59147957): the observer bridge
  prefers `context.event_run_id` over the runtime run ID, and `observers.py`
  ships `EventGraphObserver`/`InMemoryEventStore` for hosts to reuse.

Run identity here is fully deterministic and host-supplied (explicit
`run_id`/`thread_id` strings passed to `invoke`), and the only real value this
script sanitizes away is `occurred_at`/`event_id`, which `EventGraphObserver`
timestamps and mints itself on main. No prompts, payloads, or real identifiers
enter the captured fixtures.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

CAPTURE_DIR = Path(__file__).resolve().parent
FIXTURE_TIMESTAMP = "2026-09-15T00:00:00Z"

COMMITS = {
    "tag": "94cd31f58d8e94d55ea2d952c6db5508539ea53f",
    "main": "876f6a8a4ba863424e1f85bc92f18dce59147957",
}
REF = {"tag": "v0.1.0.beta.3", "main": "main"}


def _verify_pinned_commit(core_src: Path, scenario: str) -> None:
    """Refuse to capture against anything but the exact pinned commit."""
    checkout_root = core_src.parent
    result = subprocess.run(
        ["git", "-C", str(checkout_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip()
    expected = COMMITS[scenario]
    if head != expected:
        raise SystemExit(
            f"--core-src {core_src} is at {head}, not the pinned {scenario} "
            f"commit {expected}. Check out that exact commit (a separate "
            "worktree, not the shared checkout) before capturing."
        )


def _build_graph(core_src: Path, scenario: str):
    sys.path.insert(0, str(core_src))
    # Import after the sys.path insert so this resolves to the pinned checkout,
    # not whatever agent_workflow_core (if any) is already importable.
    from agent_workflow_core.adapters.langgraph.observer import observer_from_runtime
    from agent_workflow_core.observers import StepOutcome
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

    events: list[dict[str, Any]] = []

    if scenario == "main":
        from agent_workflow_core.events import InMemoryEventStore
        from agent_workflow_core.observers import EventGraphObserver

        store = InMemoryEventStore()
        graph_observer = EventGraphObserver(store)
        capture_kind = "core EventGraphObserver + InMemoryEventStore"

    else:
        # v0.1.0.beta.3 ships no EventGraphObserver/EventStore -- this is the
        # minimum a host must supply to use the Protocol at this commit,
        # mirroring agent-workflow-core's own `RecordingGraphObserver` test
        # helper (tests/adapters/test_observer.py).
        capture_kind = (
            "host-supplied GraphObserver/RunObserver Protocol implementation "
            "(no core event store exists at this commit)"
        )
        sequence_by_run: dict[str, int] = {}

        class RecordingRunObserver:
            def __init__(self, graph_id: str, run_id: str) -> None:
                self.graph_id = graph_id
                self.run_id = run_id

            def step(self, *, node_id, outcome, metadata=None) -> None:  # noqa: ANN001
                sequence_by_run[self.run_id] = sequence_by_run.get(self.run_id, 0) + 1
                events.append(
                    {
                        "sequence": sequence_by_run[self.run_id],
                        "eventType": "step." + outcome.value,
                        "graphId": self.graph_id,
                        "runId": self.run_id,
                        "nodeId": node_id,
                    }
                )

        class RecordingGraphObserver:
            def run(self, *, graph_id, run_id, **_ignored):  # noqa: ANN001
                return RecordingRunObserver(graph_id, run_id)

        graph_observer = RecordingGraphObserver()

    def node(node_id: str):
        def run_node(state: dict[str, Any], runtime: Any) -> dict[str, Any]:
            observer = observer_from_runtime(runtime)
            observer.step(node_id=node_id, outcome=StepOutcome.PASSED)
            return {"visited": [*state.get("visited", []), node_id]}

        return run_node

    from dataclasses import dataclass

    @dataclass(frozen=True)
    class RuntimeContext:
        graph_observer: Any
        graph_id: str
        subject_id: str
        subject_type: str
        semconv_version: str
        metadata: Any = None
        event_run_id: str | None = None

    builder = StateGraph(dict, context_schema=RuntimeContext)
    builder.add_node("plan", node("plan"))
    builder.add_node("act", node("act"))
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "act")
    builder.add_edge("act", END)
    compiled = builder.compile(checkpointer=InMemorySaver())

    def context(event_run_id: str | None) -> RuntimeContext:
        kwargs: dict[str, Any] = dict(
            graph_observer=graph_observer,
            graph_id="capture-demo",
            subject_id="subject-1",
            subject_type="example.subject",
            semconv_version="1",
        )
        if scenario == "main":
            kwargs["event_run_id"] = event_run_id
        return RuntimeContext(**kwargs)

    invocations = [
        {"label": "invocation-1", "run_id": "invocation-1"},
        {"label": "invocation-2 (resumed, same thread)", "run_id": "invocation-2"},
    ]
    for invocation in invocations:
        compiled.invoke(
            {},
            context=context(event_run_id="logical-run"),
            config={
                "configurable": {"thread_id": "thread-1"},
                "run_id": invocation["run_id"],
            },
        )

    if scenario == "main":
        # Real events live in the store, keyed by (graph_id, run_id). Because
        # event_run_id pins both invocations to "logical-run", every step
        # lands under one key regardless of the two distinct invoke run_ids.
        records = store.query(graph_id="capture-demo", run_id="logical-run")
        for record in records:
            events.append(
                {
                    "sequence": record.sequence,
                    "eventType": record.event.event_type,
                    "graphId": record.event.graph_id,
                    "runId": record.event.run_id,
                    "nodeId": record.event.node_id,
                }
            )

    return events, capture_kind, invocations


def capture(scenario: str, core_src: Path, output_dir: Path) -> Path:
    _verify_pinned_commit(core_src, scenario)
    events, capture_kind, invocations = _build_graph(core_src, scenario)

    trace = {
        "traceVersion": "1",
        "provenance": {
            "kind": "sanitized-source-pinned-capture",
            "consumer": {
                "repository": "https://github.com/milocosmopolitan/agent-workflow-core",
                "ref": REF[scenario],
                "commit": COMMITS[scenario],
            },
            "framework": {"name": "langgraph", "version": "1.2.11"},
            "generator": (
                "docs/research/internal-consumer/agent-workflow-core/capture/capture.py"
            ),
            "scenario": scenario,
            "captureMechanism": capture_kind,
            "generatedAt": FIXTURE_TIMESTAMP,
            "sanitization": [
                "run_id and thread_id are host-chosen literals, never real UUIDs",
                "no prompts, payloads, paths, or credentials enter observer metadata",
                (
                    "event_id/occurred_at (main only) are omitted; sequence "
                    "position is retained instead"
                ),
            ],
        },
        "invocations": invocations,
        "events": events,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / "trace.json"
    trace_path.write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return trace_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("tag", "main"), required=True)
    parser.add_argument(
        "--core-src",
        type=Path,
        required=True,
        help="path to <checkout>/src of an agent-workflow-core worktree at the pinned "
        "commit",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="defaults to fixtures/<scenario>-<short-commit>/ next to this script",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (
        CAPTURE_DIR
        / "fixtures"
        / (
            "tag-v0.1.0.beta.3"
            if args.scenario == "tag"
            else f"main-{COMMITS['main'][:8]}"
        )
    )
    trace_path = capture(args.scenario, args.core_src, output_dir)
    print(f"Wrote {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
