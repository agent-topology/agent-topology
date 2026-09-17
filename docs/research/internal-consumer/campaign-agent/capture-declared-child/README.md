# campaign-agent declared-child correlation capture

Evidence for [issue #193](https://github.com/agent-topology/agent-topology/issues/193),
advancing [#181](https://github.com/agent-topology/agent-topology/issues/181)
past [#192](https://github.com/agent-topology/agent-topology/issues/192)'s
campaign gate capture using the fake-port harness precedent it set. Recorded
2026-09-17. This is a research probe, not a new agent-topology contract; ADRs
[0001](../../../../decisions/0001-scope-topology-extraction-and-trace-correlation.md),
[0002](../../../../decisions/0002-record-what-could-not-be-observed.md), and
[0008](../../../../decisions/0008-experimental-consumer-interpretation.md) remain
authoritative, and [../README.md](../README.md) remains the parent static
review this follow-up advances.

Pinned to campaign-agent commit
[`a1532d5eed2d356792d5c3ee460d2bb8fb23db1e`](https://github.com/milocosmopolitan/campaign-agent/tree/a1532d5eed2d356792d5c3ee460d2bb8fb23db1e)
(remote main; no tag or release exists, matching `../README.md` and
[`../review-2026-09-17-declared-children.md`](../review-2026-09-17-declared-children.md)'s
baseline), and to the agent-topology commit recorded in
[`fixtures/prepare-brief-declared-child/trace.json`](fixtures/prepare-brief-declared-child/trace.json)'s
`provenance.core.commit`.

## The chosen relationship

`../review-2026-09-17-declared-children.md` already verified, statically, all
six of `channel_concept`/`channel_production`'s `declare_children`-wired
parent-to-child relationships. This capture picks the one issue #193 itself
names as the example: `channel_concept`'s `prepare_brief` node and its
declared child `copy_brief_prepare`. `capture.py` reruns that same static
check (`agent_topology.langgraph.describe()` at depth 0 and depth 2, exactly
as [`../verify_declared_children.py`](../verify_declared_children.py)
performs it), but on the *exact compiled object it goes on to execute for
real* -- not a separately recompiled standalone instance -- and then drives a
real invocation through it, correlating the static evidence with what
actually ran.

## The fake-port harness

[capture.py](capture.py) reuses [#192](https://github.com/agent-topology/agent-topology/issues/192)'s
precedent of driving a real, approved campaign-agent factory
(`campaign_agent.channel_concept.create_graph`) through fake input/ports
already used by campaign-agent's own test suite -- here,
[`tests/channel_concept/test_channel_concept.py::test_select_produces_approved_carrying_selection_and_comparison`](https://github.com/milocosmopolitan/campaign-agent/blob/a1532d5eed2d356792d5c3ee460d2bb8fb23db1e/tests/channel_concept/test_channel_concept.py#L110)'s
own `tests/channel_concept/support.py` and `tests/notifications/support.py`
fixtures (imported read-only via `sys.path`, never modified or copied) -- to
reach `prepare_brief`'s real `child.invoke()` call into the real, approved
`copy_brief_prepare` graph, per #181: "Do not substitute a generic synthetic
interrupt for these consumer wiring proofs." No model call, notification
send, or campaign/GitHub effect is real.

`describe()` is imported from *this repository's own*
`packages/python/langgraph/src`, ahead of campaign-agent's own pinned
`agent-topology-langgraph` git dependency, matching
[`../verify_declared_children.py`](../verify_declared_children.py)'s
precedent -- this capture demonstrates this repository's current
`_describe.py`, not whatever revision campaign-agent's lockfile pins.

## What was captured

1. **Static evidence, on the object about to be run.** With
   `CompiledStateGraph.invoke`/`ainvoke` patched to raise (confirming
   `describe()` itself never executes anything, the same guarantee
   `../verify_declared_children.py` established), `capture.py` calls
   `describe()` at depth 0 and depth 2 on the real compiled `channel_concept`
   graph. `prepare_brief`'s depth-0 `x-topology-interpretation` subgraph fact
   is `status: known`, `evidence.kind: declared-child-call`,
   `evidence.source: compiled.__agent_topology_children__`; at depth 2 it
   materializes as `channel_concept:prepare_brief`, whose node id set is
   identical to `copy_brief_prepare`'s own standalone `describe()` output
   (`staticEvidence.matchesStandaloneFactory: true` in
   [trace.json](fixtures/prepare-brief-declared-child/trace.json)).
2. **A real invocation through that same object.** `capture.py` then removes
   the invoke patch and drives one direction (`d1`) through
   `prepare_brief` &rarr; `draft_copy` &rarr; `review_copy`, pausing at the
   real `await_decision` `interrupt()` call, then resumes with
   `Command(resume=...)` (a fabricated `select` decision) through
   `apply_decision` to `finish`/`approved` -- the same pause/resume shape
   #192's capture established for `campaign_contract`, now shown for
   `channel_concept` too.
3. **Runtime identity correlation.** A `CompiledStateGraph.invoke` spy
   records, for each of the three nested `child.invoke()` calls
   `prepare_brief`/`draft_copy`/`review_copy` make, whether the object
   `.invoke()` was called on `is` (Python object identity) the declared child
   `describe()` resolved for that node id via
   `compiled.__agent_topology_children__` -- **never a string comparison
   between `"prepare_brief"` and `"copy_brief_prepare"`**, per issue #193's
   own instruction. All three confirm (`declaredChildIdentityConfirmed:
   true`); a mismatch would have raised rather than been silently
   recorded as a guess (see `capture.py`'s `_install_invoke_spy`).
4. **Nested child node identity, correlated by containment, not name.** The
   same `RunObserver` instance is threaded into every declared child's own
   `RuntimeContext.observer` (see `channel_concept/graph.py`'s
   `_prepare_brief` et al.), so the declared child's own node id
   (`select_evidence`, owned by `copy_brief_prepare`) is observable at all --
   tagged `nestedUnderNodeId: "prepare_brief"`, derived from the invoke spy's
   own push/pop bookkeeping around the nested call, not inferred from node
   naming. `draft_copy`/`review_copy`'s own declared children
   (`copy_draft`/`copy_review`) are exercised identically by the same run and
   recorded the same way, incidentally, alongside the one relationship this
   issue names.
5. **A real, discovered boundary.** LangGraph's own `stream_mode="debug"`
   `task_result` events -- which #192's capture showed are the only
   mechanism that observes every top-level node -- never carry a
   `nestedUnderNodeId`: a nested `child.invoke()` call runs entirely inside
   one parent node's synchronous execution, invisible to the outer graph's
   own debug stream. `copy_brief_prepare`'s other internal nodes (besides its
   one model node, `select_evidence`) are therefore not separately observed
   by this capture at all; only its model node is, because it is the only
   one that calls `RunObserver`.

Every event records the four identities #181's third acceptance bullet asks
for -- `nodeId` (static call site), `runId` (logical run, the one checkpoint
thread both invocations share), `invocationRunId` (which `stream()` call),
`nodeOccurrence` (this node's Nth observed occurrence) -- plus
`nestedUnderNodeId`, the parent/child correlation this issue adds. No retry
attempt occurred (`retryAttemptsObserved: 0`); a dedicated repeat-attempt
scenario is out of scope here, as it was for #192 (see
[#194](https://github.com/agent-topology/agent-topology/issues/194)).

No missing, unknown, or ambiguous graph or node evidence occurred --
`provenance.unresolvedEvidence` is an explicit empty list, computed from
`describe()`'s own `completeness.gaps` at both depths, not omitted or
filtered.

## Not filed as a new issue

Issue #193's fifth acceptance bullet asks that a missing required identity be
filed against the owning repository rather than fabricated. No identity was
missing here: `../review-2026-09-17-declared-children.md` already confirmed
all six relationships resolve cleanly, and this capture's own
`describe()` calls reconfirm `prepare_brief`'s specifically, with zero
completeness gaps at either depth. No campaign-agent-side issue was needed.

## Sanitization

`thread_id`/`invocationRunId` are host-chosen literals, never real UUIDs. The
resumed decision and its `DecisionAuthorization` are fabricated fixture
values, not a real decision or authorization payload. The captured
direction/brief/draft/review content is entirely derived from campaign-agent's
own fake model-gateway fixture text (`direction_outcomes()`/
`compare_candidate_outcome()`), never a real model completion or real
campaign content. The notification store is a throwaway SQLite file in a
temporary directory, discarded after capture, using
`tests.notifications.support`'s `FakeSender` -- no real notification is sent
(`notificationSendsObserved: 1` counts only that fake send).
`policy.hash`/`bundle.hash` appear only as opaque hex digests, already
treated as safe by `agent_workflow_core`'s own observer metadata contract
(`MetadataField`), structurally, not by anything this script does. No
prompts, model completions, or credentials appear anywhere in the capture. No
real campaign/GitHub effect occurred.

## Regenerating (requires local read access to campaign-agent)

Capture is not run in CI and does not write to the campaign-agent checkout --
it only reads `campaign_agent`, `agent_workflow_core`, and this repository's
own `agent_topology.langgraph`/`agent_topology.spec` sources:

```bash
# from a campaign-agent checkout at the pinned commit, using campaign-agent's
# own venv (this repo's uv/pytest tooling does not have langgraph 1.2.11 +
# campaign_agent installed; campaign-agent's own uv.lock does)
/path/to/campaign-agent/.venv/bin/python capture.py --consumer-src /path/to/campaign-agent
```

`capture.py` refuses to run if `--consumer-src`'s checkout is not at the
exact pinned commit. It was run against a checkout already present locally at
that commit.

`expected.json` was produced by, and must be regenerated with:

```bash
python3 -I -S replay.py --format json > fixtures/prepare-brief-declared-child/expected.json
```

### Fixture hashes at generation (sha256)

```
8e0c2968b85d81b83f8742941b31dc33e02b5df2ec353e959e2e601b4cd8603a  fixtures/prepare-brief-declared-child/trace.json
07ceb22777cce74a9b31ed8ca425d18a21c87a5dfb86ccb94f54761b5eb275b3  fixtures/prepare-brief-declared-child/expected.json
```

Generated with
`shasum -a 256 fixtures/prepare-brief-declared-child/*.json`;
`tests/test_campaign_agent_declared_child_correlation.py` re-checks these
values.

## Offline replay (no checkout, no LangGraph, no network, no describe())

```bash
python3 -I -S replay.py --check
```

Reproduces, from the committed fixture alone, the same correlation facts
recorded in `expected.json`, including
`declaredChildCallCorrelationConfirmed: true` for
`prepare_brief -> copy_brief_prepare`.
`tests/test_campaign_agent_declared_child_correlation.py` runs this as a
subprocess with `-I -S` (isolated, no site packages) to enforce that this
stays true.

## Disposition

This is the first *runtime* correlation of a `declare_children`-declared
relationship against a real consumer: `../review-2026-09-17-declared-children.md`
proved all six relationships hold statically (declaration confirmed, child
materializes, node id set matches); this capture proves that for one of
them, `prepare_brief -> copy_brief_prepare`, the object actually invoked at
runtime is identity-confirmed to be that same declared child, and that its
own real execution is observable, nested under the correct parent node. It
does **not** prove: that any real campaign approval or downstream effect
succeeded (the notification store and model gateway are fakes); that the
other five declared relationships behave identically at runtime (only
`prepare_brief` is this issue's demonstrated relationship, though
`draft_copy`/`review_copy` are incidentally exercised and recorded by the
same run); or that retries are distinguishable from resume in this scenario
(no retry occurred; see #194 for that). `DecisionInput`/`DecisionAuthorization`
values here are fabricated fixture literals, not a real decision.
