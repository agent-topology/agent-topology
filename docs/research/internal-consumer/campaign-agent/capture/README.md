# campaign-agent await_decision interrupt/resume capture

Evidence for [issue #192](https://github.com/agent-topology/agent-topology/issues/192),
advancing [#181](https://github.com/agent-topology/agent-topology/issues/181)'s
first acceptance bullet's campaign half ("...and a campaign actual gate with
fake input/ports, then resume"). Recorded 2026-09-17. This is a research
probe, not a new agent-topology contract; ADRs
[0001](../../../../decisions/0001-scope-topology-extraction-and-trace-correlation.md),
[0002](../../../../decisions/0002-record-what-could-not-be-observed.md), and
[0008](../../../../decisions/0008-experimental-consumer-interpretation.md)
remain authoritative, and [../README.md](../README.md) remains the parent
static review this follow-up advances.

Pinned to campaign-agent commit
[`a1532d5eed2d356792d5c3ee460d2bb8fb23db1e`](https://github.com/milocosmopolitan/campaign-agent/tree/a1532d5eed2d356792d5c3ee460d2bb8fb23db1e)
(remote main; no tag or release exists, matching `../README.md`'s baseline;
this is the exact commit and `campaign_contract.py:449-469` line range the
issue names for `await_decision`).

## The fake-port harness

[capture.py](capture.py) *is* that harness: campaign-agent ships no
`dev/issue_resolution.py`-style adapter of its own (the issue's premise), and
this repository does not add one to campaign-agent's own tree -- per
`AGENTS.md`, agent-topology reads consumer repositories but does not modify
them. Instead, following the precedent set by
[../../git-agent/capture/capture.py](../../git-agent/capture/capture.py)
(issue #191), the harness lives here: it drives campaign-agent's real,
approved `campaign_contract` factory
(`campaign_agent.campaign_contract.create_graph`) through fake
input/ports already used by campaign-agent's own test suite -- reusing
[`tests/campaign_contract/test_campaign_contract.py::test_approve_produces_canonical_hash_with_no_duplicate_fields`](https://github.com/milocosmopolitan/campaign-agent/blob/a1532d5eed2d356792d5c3ee460d2bb8fb23db1e/tests/campaign_contract/test_campaign_contract.py#L67)
and its `support.py` fixtures (loaded read-only via `importlib`, registered as
a throwaway package so `test_campaign_contract.py`'s own
`from .support import ...` resolves; no source modified or copied) -- to
reach `await_decision`'s real `interrupt()` call and resume it, per #181:
"Do not substitute a generic synthetic interrupt for these consumer wiring
proofs."

## Why this needed a different mechanism than git-agent's capture

git-agent's `human_approval` node calls `agent_workflow_core`'s
`RunObserver.step()` directly, so #191's capture could record every node's
step lifecycle through one custom `RunObserver`. Grepping the identical
`agent_workflow_core` package (git-agent and campaign-agent both pin the same
commit,
[`876f6a8a`](https://github.com/milocosmopolitan/agent-workflow-core/tree/876f6a8a4ba863424e1f85bc92f18dce59147957))
shows `observe_step`/`observe_attempt` are only ever called from
`execution/contracts.py`, `execution/model_step.py`, and `routing.py`'s
`route_model_node` -- i.e. only from the two model nodes
(`draft_rules`, `draft_concept`) that `create_model_step` wraps.
`campaign_contract`'s own node functions (`validate_input`,
`gate_readiness_check`, `await_decision`, `apply_decision`, the terminal
outcome nodes) never touch `RunObserver` at all. A git-agent-style recorder
alone would see zero events for `await_decision` and could not show it ran
twice.

`capture.py` instead reads node/task identity from LangGraph's own
`stream_mode="debug"` `task_result` events, which exist for **every** node
regardless of whether that consumer's code touches the observer -- a
strictly more general mechanism than #191 needed, and the only one that
observes `await_decision` here. A `RunObserver` is still attached, to
independently record the two real model attempts
(`draft_rules`/`draft_concept`, via the `"node.id"` metadata field
`route_model_node` attaches -- the same field git-agent's capture reads).
`replay.py` cross-checks that both mechanisms agree on those two nodes'
occurrence counts (`observerAndTaskOccurrencesAgreeForModelNodes: true`);
this is genuine, discovered evidence about how thinly `campaign_contract`
adopts the shared observer contract, not an assumption carried over from
git-agent's capture.

## What was captured

- **invocation-1** (`invocationRunId: "invocation-1"`) runs the graph on one
  checkpoint thread from `validate_input` through `gate_readiness_check`,
  fabricated fixture rules/concept content accepted on the first model
  attempt (no retries; a separate minimal repeat-attempt fixture, analogous
  to [#194](https://github.com/agent-topology/agent-topology/issues/194)'s
  git-agent case, is not this issue's scope). It pauses at `await_decision`'s
  real `interrupt()` call: LangGraph's debug stream records a `task_result`
  for `await_decision` carrying a non-empty `interrupts` list
  (`task.awaiting_approval`, sanitized proposal payload retained in
  `invocations[0].interruptValue`).
- **invocation-2** (`invocationRunId: "invocation-2"`) resumes with
  `Command(resume=...)` on the same checkpoint thread, using a fabricated
  `DecisionInput`/`DecisionAuthorization` pair (`action: "approve"`). **The
  real LangGraph task scheduled for `await_decision` is the exact same task
  id as invocation-1's** (`taskId` identical across both `task.*` events for
  that node) -- proof that "which real LangGraph task" and "which resume
  invocation" are independently addressable identities, not one and the
  same, and that the node body re-runs from its start on resume (ADR 0002).
  The graph then continues for real through `apply_decision` to `approved`.
  No port beyond the fake model gateway and the in-memory checkpointer is
  exercised anywhere on this path -- unlike git-agent's `human_approval`,
  `campaign_contract`'s gate has no downstream write port at all in this
  scenario.

Every event records the four identities #181's third acceptance bullet asks
for: `nodeId` (static call site), `runId` (logical run -- the one checkpoint
thread both invocations share), `invocationRunId` (which `invoke`/`stream`
call -- a fact the capture script itself knows), and `nodeOccurrence` (this
node's Nth observed occurrence across the whole logical run, counted
separately for LangGraph's debug-stream `task.*` events and for
`RunObserver`'s `observer.step.*`/`observer.attempt.*` events, so a node
observed twice, as `await_decision` is here, is never conflated into one
occurrence). No retry attempt occurred in this scenario
(`retryAttemptsObserved: 0` in
[expected.json](fixtures/await-decision-interrupt-resume/expected.json)).

No missing, unknown, or ambiguous graph/node evidence occurred in this
capture -- `provenance.unresolvedEvidence` is present as an explicit empty
list, not omitted.

Sanitization: `thread_id`/`invocationRunId` are host-chosen literals, never
real UUIDs. The resumed `DecisionInput` and its `DecisionAuthorization` are
fabricated fixture values, not a real decision or authorization payload. The
captured interrupt proposal (`concept`/`rules`/`readiness`/`gate`) is
entirely derived from campaign-agent's own fake model-gateway fixture text
(`rules_outcome()`/`concept_outcome()`), never a real model completion or
real campaign content. `policy.hash`/`bundle.hash` appear only as opaque hex
digests, already treated as safe by `agent_workflow_core`'s own observer
metadata contract (`MetadataField`), structurally, not by anything this
script does. No prompts, model completions, or credentials appear anywhere
in the capture. No real campaign/GitHub effect occurred: this scenario
exercises no write port at all.

## Regenerating (requires local read access to campaign-agent)

Capture is not run in CI and does not run against a shared checkout's working
tree unmanaged by this script -- it only reads `campaign_agent` and
`agent_workflow_core`, plus the pinned test fixture module; it never writes
to the checkout:

```bash
# from a campaign-agent checkout at the pinned commit, using campaign-agent's
# own venv (this repo's uv/pytest tooling does not have langgraph 1.2.11 +
# campaign_agent installed; campaign-agent's own uv.lock does)
/path/to/campaign-agent/.venv/bin/python capture.py --consumer-src /path/to/campaign-agent
```

`capture.py` refuses to run if `--consumer-src`'s checkout is not at the
exact pinned commit. It was run against a checkout freshly cloned from
`https://github.com/milocosmopolitan/campaign-agent.git` (remote main, which
was at the pinned commit at capture time) with a `uv sync --group dev`
environment resolved from campaign-agent's own `pyproject.toml`/`uv.lock`
(`langgraph 1.2.11`, matching git-agent's).

`expected.json` was produced by, and must be regenerated with:

```bash
python3 -I -S replay.py --format json > fixtures/await-decision-interrupt-resume/expected.json
```

### Fixture hashes at generation (sha256)

```
58a2a55e798a919993433b8c08640b8161420e8454263e5cd76decf335327b07  fixtures/await-decision-interrupt-resume/trace.json
7f136fa4f3acb31b3c3438c95b886f227d6ff0a844a9b04da67cc56e616b1ec4  fixtures/await-decision-interrupt-resume/expected.json
```

Generated with `shasum -a 256 fixtures/await-decision-interrupt-resume/*.json`;
`tests/test_campaign_agent_await_decision_capture.py` re-checks these values.

## Offline replay (no checkout, no LangGraph, no network)

```bash
python3 -I -S replay.py --check
```

Reproduces, from the committed fixture alone, the same pause/resume/
occurrence facts recorded in `expected.json`.
`tests/test_campaign_agent_await_decision_capture.py` runs this as a
subprocess with `-I -S` (isolated, no site packages) to enforce that this
stays true.

## Disposition

This advances IC-03 ("human pause is dynamic": `await_decision` calls
`interrupt(proposal)` inside a wrapper-backed node, per
[../README.md](../README.md)'s gaps table) from `pending` to `verified`
specifically for campaign-agent's own `await_decision` node: a real dynamic
interrupt inside campaign-agent's real graph pauses it, and
`Command(resume=...)` on the same checkpoint thread resumes it to real
completion, re-running the node body as predicted by ADR 0002 -- and, unlike
[#191](https://github.com/agent-topology/agent-topology/issues/191)'s
git-agent capture, this required reading LangGraph's own debug stream rather
than the consumer's own `RunObserver` wiring, because `campaign_contract`
only wires that observer to its two model nodes. It does **not** prove: that
any real campaign approval, authorization, or downstream effect succeeded
(no write port is exercised on this path at all, fake or otherwise); that
nested/child correlation works (see
[#193](https://github.com/agent-topology/agent-topology/issues/193)); or that
retries are distinguishable from resume beyond the structural
`nodeOccurrence`/`attemptNumber` split demonstrated here (a dedicated minimal
repeat-attempt case, analogous to
[#194](https://github.com/agent-topology/agent-topology/issues/194), is out
of scope for this issue). `DecisionInput`/`DecisionAuthorization` values here
are fabricated fixture literals, not a real decision.
