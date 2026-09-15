# Source-pinned core capture

Evidence for [issue #151](https://github.com/agent-topology/agent-topology/issues/151),
advancing [#142](https://github.com/agent-topology/agent-topology/issues/142)
acceptance criteria 2 and 6. Recorded 2026-09-15. This is a research probe, not
a new agent-topology contract; ADRs
[0001](../../../../decisions/0001-scope-topology-extraction-and-trace-correlation.md),
[0002](../../../../decisions/0002-record-what-could-not-be-observed.md),
[0008](../../../../decisions/0008-experimental-consumer-interpretation.md), and
[0011](../../../../decisions/0011-document-local-consumer-addressable-graph-ids.md)
remain authoritative, and [the cross-consumer findings](../../README.md#suggested-work-sequence-and-minimum-evidence)
(work item 1, IC-04/05) remain the parent research context.

Both pinned commits report package version `0.1.0b3`; that version alone is
not commit identity (see [../snapshot.json](../snapshot.json)). This probe
pins to, and separates evidence for, two exact commits:

| Scenario | Ref | Commit | What differs |
| --- | --- | --- | --- |
| `tag` | `v0.1.0.beta.3` | `94cd31f58d8e94d55ea2d952c6db5508539ea53f` | `observers.py` has no `EventGraphObserver`/`EventStore`; `observer_from_runtime` has no logical-run override. |
| `main` | `main` | `876f6a8a4ba863424e1f85bc92f18dce59147957` | `observers.py` ships `EventGraphObserver`/`InMemoryEventStore`; `observer_from_runtime` prefers `context.event_run_id` over the LangGraph runtime run ID. |

Full source diff: [94cd31f...876f6a8a](https://github.com/milocosmopolitan/agent-workflow-core/compare/94cd31f58d8e94d55ea2d952c6db5508539ea53f...876f6a8a4ba863424e1f85bc92f18dce59147957).
[fixtures/commits.json](fixtures/commits.json) records the pin and its peeled
tag commit.

## What was captured

[capture.py](capture.py) compiles one real two-node LangGraph 1.2.11 graph
(`plan` → `act`, an `InMemorySaver` checkpointer, `thread_id="thread-1"`), each
node calling the real `observer_from_runtime` bridge and emitting one
`StepOutcome.PASSED` step. The graph is invoked twice with the same thread
(`run_id="invocation-1"`, then `run_id="invocation-2"`, a re-entry standing in
for a resumed run) and `context.event_run_id="logical-run"` on both calls. No
node body performs I/O, and no prompts, payloads, paths, or credentials cross
the observer boundary (`ObserverMetadata` is not used).

- On `tag`, `event_run_id` doesn't exist as a concept and no core event store
  exists; the probe supplies its own minimal `GraphObserver`/`RunObserver`
  (mirroring agent-workflow-core's own `RecordingGraphObserver` test helper in
  `tests/adapters/test_observer.py`) and records only `step.*` events. The two
  invocations land under two different run IDs (`invocation-1`,
  `invocation-2`) with sequences resetting to 1 in each — **no resume identity
  is preserved** at this commit.
- On `main`, the real `EventGraphObserver` + `InMemoryEventStore` are used.
  Each node call also mints a `run.observed` envelope event (an
  `EventGraphObserver.run()` side effect, not part of this probe). Because
  `event_run_id="logical-run"` overrides the runtime run ID, **all 8 events
  from both invocations land under one run ID**, sequences 1–8 unbroken.

Sanitization: `run_id`/`thread_id` are host-chosen literals (`"invocation-1"`,
`"thread-1"`, …), never real UUIDs. `event_id`/`occurred_at`, which
`EventGraphObserver` mints from `uuid4()`/`datetime.now()` on `main`, are
dropped from the fixture; sequence position is retained instead, which is
sufficient to prove ordering and grouping without embedding a nondeterministic
value. No private source is vendored: the checked-in fixtures are captured
*output*, not agent-workflow-core source.

## Regenerating (requires local read access to agent-workflow-core)

Capture is not run in CI and does not run against the shared checkout's
working tree — a detached worktree per pinned commit keeps that checkout
untouched:

```bash
# from an agent-workflow-core checkout at main (876f6a8a...)
git worktree add --detach /tmp/awc-tag-v0.1.0.beta.3 94cd31f58d8e94d55ea2d952c6db5508539ea53f

# main scenario, using the checkout already at 876f6a8a...
.venv/bin/python capture.py --scenario main --core-src /path/to/agent-workflow-core/src

# tag scenario, using the isolated worktree (same venv: only observers.py,
# events.py and observer.py differ between commits; langgraph/pydantic do not)
.venv/bin/python capture.py --scenario tag --core-src /tmp/awc-tag-v0.1.0.beta.3/src

git worktree remove /tmp/awc-tag-v0.1.0.beta.3
```

`capture.py` refuses to run if `--core-src`'s checkout is not at the exact
pinned commit for `--scenario`. It was run with agent-workflow-core's own
`.venv` (`langgraph 1.2.11`, `pydantic 2.13.5`, matching `uv.lock` and the
locked version recorded in [../snapshot.json](../snapshot.json)).

`expected.json` for each scenario was produced by, and must be regenerated
with:

```bash
python3 -I -S replay.py --scenario tag --format json   # → fixtures/tag-v0.1.0.beta.3/expected.json
python3 -I -S replay.py --scenario main --format json  # → fixtures/main-876f6a8a/expected.json
```

### Fixture hashes at generation (sha256)

```
0798b78dcdcc0d0a254f17126222ea9be1bf51050d001c7f5a18adf070fa8e93  fixtures/tag-v0.1.0.beta.3/expected.json
a78752b1df9fd40494e0d95c8827fbc3c4ad3fc3511bad09c7522c1a40dcfc29  fixtures/tag-v0.1.0.beta.3/trace.json
96c299c3eaba8e8557903c37fef7e7cf3f67aba9376ee8ca9972e072d82a5a7c  fixtures/main-876f6a8a/expected.json
a46818476423d39cd9929ceb8e325bd7bc389aef3f9131fca8960b67820e29e9  fixtures/main-876f6a8a/trace.json
8131afc336233c7cf477410520e6231c5aa8af5b7ff0f69111264e246a469d9b  fixtures/commits.json
```

Generated with `shasum -a 256 fixtures/*/*.json fixtures/commits.json`;
`tests/test_internal_consumer_capture.py` re-checks these values.

## Offline replay (no checkout, no LangGraph, no network)

```bash
python3 -I -S replay.py --scenario tag --check
python3 -I -S replay.py --scenario main --check
```

Both reproduce, from the committed fixtures alone, the same
`resumeIdentityPreserved: false` (tag) / `true` (main) result recorded in each
scenario's `expected.json`. `tests/test_internal_consumer_capture.py` runs
both as a subprocess with `-I -S` (isolated, no site packages) to enforce that
this stays true.

## Disposition

This advances IC-04 ("no integration here proves core observer events map to
those IDs and nodes across resume or nesting") from `pending` to `verified`
for the pinned-commit resume-identity question specifically: `event_run_id` is
confirmed, by a real two-invocation capture through the real bridge and event
store, to collapse two runtime run IDs into one logical run on `main`, and
confirmed absent (both the field and the mechanism) at the `v0.1.0.beta.3`
release. It does not prove campaign-agent or git-agent's own integration code
sets `event_run_id`, does not cover nesting, and does not claim graph/node
topology correlation -- only run identity across a re-entry. The dynamic
interrupt, resume, and same-node retry follow-up (item 4) is separately
recorded in [`interrupt-resume/` and `repeated-attempt/`](#dynamic-interrupt-resume-and-repeated-attempt-issue-152)
below.

## Dynamic interrupt, resume, and repeated-attempt (issue #152)

[capture_dynamic.py](capture_dynamic.py) and [replay_dynamic.py](replay_dynamic.py)
cover [item 4](../../README.md#suggested-work-sequence-and-minimum-evidence)
("Prove runtime enrichment (IC-03/06). Use one dynamic interrupt and one
resume, then a separate same-node retry.") against the same pinned `main`
commit (`876f6a8a4ba863424e1f85bc92f18dce59147957`) already captured above.
Interrupt/resume and retry are LangGraph-level mechanisms, not commit-specific
behavior, so only `main` is pinned here -- unlike the tag/main split above,
which exists specifically to compare `event_run_id` availability.

Two scenarios, each its own one-node graph and fixture directory:

- [`fixtures/interrupt-resume/`](fixtures/interrupt-resume/): the node calls
  the real `agent_workflow_core.adapters.langgraph.approval.request_approval`,
  which calls the real `langgraph.types.interrupt`. `invoke()` #1 pauses the
  graph (`__interrupt__` present in the result, sanitized away below);
  `invoke(Command(resume=...))` #2 on the same thread resumes it. **LangGraph
  re-runs the node body from its start on resume**: the observer call issued
  before `interrupt()` fires again on invocation 2, so `approve` shows two
  `step.awaiting_approval` events (one per invocation) but only one
  `step.passed` (after the actual resume). This is measured, not assumed --
  ADR 0002 already predicted it ("Interrupts raised inside a node body do not
  appear in node metadata"); this capture is the runtime evidence for it.
- [`fixtures/repeated-attempt/`](fixtures/repeated-attempt/): the node has a
  real LangGraph `RetryPolicy(max_attempts=2)` attached. It raises a
  retryable `ConnectionError` on attempt 1 and succeeds on attempt 2, both
  within **one** `invoke()` call -- no checkpoint pause, no
  `Command(resume=...)`, no second invocation. `observe_attempt` (the same
  helper `agent_workflow_core.routing.route_model_node` uses in production)
  records each attempt with an explicit `attempt.number` metadata field,
  which is what distinguishes the two occurrences -- `RunObserver.attempt`
  does not auto-populate `node_id` the way `RunObserver.step` does, so
  `node.id` metadata is supplied explicitly, mirroring the real
  `routing._attempt_metadata` call site.

Each event additionally carries `invocationRunId`, a fact the capture script
itself knows (which `invoke()` call was in flight), not something derived
from the event store -- distinguishing "which logical run" (`runId`,
`event_run_id`-collapsed) from "which invocation" (`invocationRunId`) from
"which attempt" (`metadata.attemptNumber`, repeated-attempt scenario only).

Sanitization matches the pattern above: `run_id`/`thread_id`/`event_run_id`
are host-chosen literals, never real UUIDs; the resume `ApprovalEnvelope` is a
fabricated fixture value (hash-shaped literals), not a real decision or
authorization payload; the LangGraph-minted interrupt id and
`event_id`/`occurred_at` are omitted, sequence position is retained instead;
no prompts, payloads, paths, or credentials enter observer metadata.

### Regenerating

```bash
# from the agent-workflow-core checkout, already at main (876f6a8a...)
.venv/bin/python capture_dynamic.py --scenario interrupt-resume \
  --core-src /path/to/agent-workflow-core/src
.venv/bin/python capture_dynamic.py --scenario repeated-attempt \
  --core-src /path/to/agent-workflow-core/src

python3 -I -S replay_dynamic.py --scenario interrupt-resume --format json \
  > fixtures/interrupt-resume/expected.json
python3 -I -S replay_dynamic.py --scenario repeated-attempt --format json \
  > fixtures/repeated-attempt/expected.json
```

`capture_dynamic.py` refuses to run if `--core-src`'s checkout is not at the
exact pinned main commit. It was run with agent-workflow-core's own `.venv`
(`langgraph 1.2.11`), matching `uv.lock`.

#### Fixture hashes at generation (sha256)

```
732f9d8cefbbc7bffee83a058e679f067eac8a650dbb42d4d031e225abe77705  fixtures/interrupt-resume/expected.json
08de54ace84c3f17c137172a36e72f5c89d44dfe95eeed3c697c08a316fd000a  fixtures/interrupt-resume/trace.json
bad52bea3208381f54afa95c81c2d1c076e6c8d8d7c6eb607e28254cddbc5685  fixtures/repeated-attempt/expected.json
249bf3cc808f0466fa8887d876ad9e0a04fd7891dd65ad35e37033c9b0ffa934  fixtures/repeated-attempt/trace.json
```

Generated with `shasum -a 256 fixtures/interrupt-resume/*.json
fixtures/repeated-attempt/*.json`; `tests/test_internal_consumer_dynamic_capture.py`
re-checks these values.

### Offline replay (no checkout, no LangGraph, no network)

```bash
python3 -I -S replay_dynamic.py --scenario interrupt-resume --check
python3 -I -S replay_dynamic.py --scenario repeated-attempt --check
```

Both reproduce, from the committed fixtures alone, the same pause and
attempt facts recorded in each scenario's `expected.json`.
`tests/test_internal_consumer_dynamic_capture.py` runs both as a subprocess
with `-I -S` to enforce that this stays true.

### Disposition

This advances IC-03 ("Dynamic `interrupt()` inside node bodies is not a
static interrupt declaration") and the retry/attempt half of IC-06 from
`pending` to `verified` for the specific claims made above: a real dynamic
interrupt pauses a `main`-pinned graph and is resumable via
`Command(resume=...)`; the pre-interrupt node body re-runs on resume; a real
LangGraph `RetryPolicy` re-attempts the same node within one invocation,
distinguishable from resume by invocation count, pause state, and an explicit
`attempt.number`. It does not prove campaign-agent or git-agent's own
approval/routing nodes are wired the same way, does not cover nested graphs,
and -- per [issue #152](https://github.com/agent-topology/agent-topology/issues/152)
-- makes no claim that this evidence proves authorization, budget compliance,
or successful effects; `ApprovalDecision`/`AttemptOutcome` values here are
fabricated fixture literals, not a real approval or a real retry policy
decision.
