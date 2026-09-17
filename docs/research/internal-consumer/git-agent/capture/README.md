# git-agent human_approval interrupt/resume capture

Evidence for [issue #191](https://github.com/agent-topology/agent-topology/issues/191),
advancing [#181](https://github.com/agent-topology/agent-topology/issues/181)'s
first acceptance bullet ("capture a minimum path through git-agent's actual
human_approval node... with fake input/ports, then resume"). Recorded
2026-09-17. This is a research probe, not a new agent-topology contract; ADRs
[0001](../../../../decisions/0001-scope-topology-extraction-and-trace-correlation.md),
[0002](../../../../decisions/0002-record-what-could-not-be-observed.md), and
[0008](../../../../decisions/0008-experimental-consumer-interpretation.md)
remain authoritative, and [../README.md](../README.md) remains the parent
static review this follow-up advances.

Pinned to git-agent commit
[`b67cb35a6195609a5d89976768fb5a4884f17ca1`](https://github.com/milocosmopolitan/git-agent/tree/b67cb35a6195609a5d89976768fb5a4884f17ca1)
(remote main; no tag or release exists, matching `../README.md`'s baseline).

## Why this is not the earlier agent-workflow-core interrupt/resume capture

[`../../agent-workflow-core/capture/capture_dynamic.py`](../../agent-workflow-core/capture/capture_dynamic.py)
(issue #152) built a synthetic one-node demo graph around the real
`langgraph.types.interrupt()` primitive to prove a *mechanism*: LangGraph
re-runs a node's body on resume. That was accepted as evidence for the
mechanism, but issue #181 explicitly rules it out as evidence for a specific
consumer's wiring: "Do not substitute a generic synthetic interrupt for these
consumer wiring proofs." This capture instead drives git-agent's real,
approved `issue_resolution` graph
(`git_agent.graphs.issue_resolution.create_graph`) — the actual `human_approval`
node, not a stand-in — through fake input/ports already used by git-agent's
own test suite.

## What was captured

[capture.py](capture.py) reuses the exact fake-input/fake-port fixtures from
git-agent's own
[`tests/graphs/test_issue_resolution_nodes.py::test_complete_red_interrupt_observes_steps_and_model_attempts`](https://github.com/milocosmopolitan/git-agent/blob/b67cb35a6195609a5d89976768fb5a4884f17ca1/tests/graphs/test_issue_resolution_nodes.py#L519)
by loading that test module directly (read access only, no source is
modified or copied) and reusing its non-test helper objects
(`_policy`, `_context`, `_input`, fake ports). That fixture reaches
`human_approval`'s real `interrupt()` call via the shortest path through the
graph that git-agent's own tests already exercise: the RED-verification
route (2 model attempts, both scripted to succeed on their first try — no
retries; see [issue #194](https://github.com/agent-topology/agent-topology/issues/194)
for the separate minimal repeat-attempt case).

git-agent's production `create_graph` compiles with `checkpointer=None`
(checkpointing is host responsibility — see `../README.md`'s IC-03 row). This
script attaches its own `InMemorySaver` after compiling, exactly as a real
host integration would have to.

- `invoke()` #1 (`invocationRunId: "invocation-1"`) runs the graph on one
  checkpoint thread. It pauses at `human_approval`'s real `interrupt()` call
  (`__interrupt__` present in the result, sanitized away below).
- `invoke(Command(resume=...))` #2 (`invocationRunId: "invocation-2"`), same
  thread, resumes it with a fabricated `HumanApprovalResponse`
  (`decision: "approved"`). **LangGraph re-runs `human_approval`'s node body
  from its start on resume**: `human_approval` shows two `step.*` events (one
  per invocation) — `step.awaiting_approval` then `step.passed` — never
  conflated into one occurrence. The graph then continues for real, through
  `post_status_comment` (a scripted `FakeGitHubIssueMutatePort` receipt, no
  real GitHub call) to `finalize_result`, reaching outcome `red_reported`.

Every event records four independently distinct identities, per #181's third
acceptance bullet: `nodeId` (static call site), `runId` (logical run — the
one checkpoint thread both invocations share), `invocationRunId` (which
`invoke()` call — a fact the capture script itself knows, not derived from
git-agent's own state), and `nodeOccurrence` (this node's Nth *step*
occurrence, counted separately from its Nth *attempt* occurrence, so one real
step that happens to make one real model attempt is never miscounted as two
step occurrences). No retry attempt occurred in this scenario
(`retryAttemptsObserved: 0` in [expected.json](fixtures/human-approval-interrupt-resume/expected.json));
that is a separate, smaller fixture (#194), not grown from this one.

No missing, unknown, or ambiguous graph/node evidence occurred in this
capture — `provenance.unresolvedEvidence` is present as an explicit empty
list, not omitted, so a future capture that does hit missing identity has
somewhere structural to record it rather than a guessed match.

Sanitization: `thread_id`/`invocationRunId` are host-chosen literals, never
real UUIDs. The resume `HumanApprovalResponse` is a fabricated fixture value.
`plan_hash`/`policy_hash`/`authorization_hash` appear only as opaque hex
digests — git-agent's own observer metadata contract
(`agent_workflow_core.observers.MetadataField`) already forbids raw
plan/payload content from crossing into `metadata`, structurally, not by
anything this script does. No prompts, model completions, or credentials
appear anywhere in the capture. No real GitHub/git effect occurred: the only
write port exercised (`mutate_issue`) is `FakeGitHubIssueMutatePort`, the
same fake git-agent's own tests use.

## Regenerating (requires local read access to git-agent)

Capture is not run in CI and does not run against a shared checkout's working
tree unmanaged by this script — it only reads `git_agent`, `agent_workflow_core`,
and the pinned test fixture module; it never writes to the checkout:

```bash
# from a git-agent checkout at the pinned commit, using git-agent's own venv
# (this repo's uv/pytest tooling does not have langgraph 1.2.11 + git_agent
# installed; git-agent's .venv does)
/path/to/git-agent/.venv/bin/python capture.py --consumer-src /path/to/git-agent
```

`capture.py` refuses to run if `--consumer-src`'s checkout is not at the
exact pinned commit. It was run with git-agent's own `.venv`
(`langgraph 1.2.11`, matching git-agent's `uv.lock`).

`expected.json` was produced by, and must be regenerated with:

```bash
python3 -I -S replay.py --format json > fixtures/human-approval-interrupt-resume/expected.json
```

### Fixture hashes at generation (sha256)

```
6d708fb804136de63f8a2b4effc72e5a5ecbf63977ba74d42564ec6496eb170b  fixtures/human-approval-interrupt-resume/trace.json
84d67b3195f698adca5240c194bc815465f873b2c322070f0c45874cc14d122a  fixtures/human-approval-interrupt-resume/expected.json
```

Generated with `shasum -a 256 fixtures/human-approval-interrupt-resume/*.json`;
`tests/test_git_agent_human_approval_capture.py` re-checks these values.

## Offline replay (no checkout, no LangGraph, no network)

```bash
python3 -I -S replay.py --check
```

Reproduces, from the committed fixture alone, the same pause/resume/
occurrence facts recorded in `expected.json`.
`tests/test_git_agent_human_approval_capture.py` runs this as a subprocess
with `-I -S` (isolated, no site packages) to enforce that this stays true.

## Disposition

This advances IC-03 ("Dynamic `interrupt()` inside node bodies is not a
static interrupt declaration") from `pending` to `verified` specifically for
git-agent's own `human_approval` node: a real dynamic interrupt inside
git-agent's real graph pauses it, and `Command(resume=...)` on the same
checkpoint thread resumes it to real completion, re-running the node body as
predicted by ADR 0002. It does **not** prove: that any real GitHub/git
approval, authorization, or effect succeeded (every write port is scripted);
that campaign-agent's gates behave the same way (see
[#192](https://github.com/agent-topology/agent-topology/issues/192), which
has no equivalent fake-port harness yet); that nested/child correlation
works (see [#193](https://github.com/agent-topology/agent-topology/issues/193));
or that retries are distinguishable from resume beyond the structural
`nodeOccurrence`/`attemptNumber` split demonstrated here (see
[#194](https://github.com/agent-topology/agent-topology/issues/194) for the
dedicated minimal case). `ApprovalDecision`/`IssueMutationReceipt` values
here are fabricated fixture literals, not a real decision or a real GitHub
mutation.

## Minimal repeat-attempt fixture (issue #194)

[capture_repeat_attempt.py](capture_repeat_attempt.py) is the dedicated
"separate, smaller fixture" this scenario's `expected.json` already forward-
references (`retryAttemptsObserved: 0 ... see issue #194`). Per
[#181](https://github.com/agent-topology/agent-topology/issues/181)'s third
acceptance bullet, a retry-mechanics case must not grow the full campaign or
git-agent input, so this one does not reuse `human_approval` or
`issue_resolution` at all. It reuses only what's cheap to reuse: the
`_RecordingObserver` event shape from [capture.py](capture.py) (`nodeId`,
`runId`, `invocationRunId`, `nodeOccurrence`, attempt vs. step counted on
separate counters), applied to the smallest graph that can exercise a real
LangGraph retry -- one node, one `RetryPolicy(max_attempts=2)`, no
`interrupt()`, no `Command(resume=...)`, one `invoke()` call. campaign-agent's
fake-port harness ([#192](https://github.com/agent-topology/agent-topology/issues/192))
does not exist yet, so this is the cheaper of the two harnesses named in
#194.

Because the graph is entirely synthetic, no external consumer checkout is
read or pinned: `langgraph` (`1.2.11`, matching the version git-agent and
campaign-agent both resolve to) is already a direct dependency of this repo's
own `packages/python/langgraph` package, so that package's own environment
is all this capture needs.

```bash
uv run --project packages/python/langgraph python capture_repeat_attempt.py
python3 -I -S replay_repeat_attempt.py --format json > fixtures/repeat-attempt/expected.json
```

### Fixture hashes at generation (sha256)

```
8b11e14d0c05d43968686bd1e090429c11636f0a12dc765816a859859f3fd7c0  fixtures/repeat-attempt/trace.json
9b434c7bfcbfe85c6be7bf077c241d830ebcade6d10fbb2a8dbfc6fe75afc6e8  fixtures/repeat-attempt/expected.json
```

Generated with `shasum -a 256 fixtures/repeat-attempt/*.json`;
`tests/test_git_agent_repeat_attempt_capture.py` re-checks these values.

### Offline replay (no checkout, no LangGraph, no network)

```bash
python3 -I -S replay_repeat_attempt.py --check
```

Reproduces, from the committed fixture alone: one logical run, one
invocation (`paused: false` -- no resume in this fixture), attempt numbers
`[1, 2]` (`attempt.failed` then `attempt.passed`), and exactly one step
occurrence for the retried node (`stepOccurrencesByNode: {"flaky_step": [1]}`)
-- the node was stepped into once even though it took two attempts.
`tests/test_git_agent_repeat_attempt_capture.py` runs this as a subprocess
with `-I -S` to enforce that this stays true.

### Disposition

This closes #194: a repeat/retry attempt is now distinguishable from a
resume invocation in the normalized output, using the same five identities
(`nodeId`, `runId`, `invocationRunId`, `nodeOccurrence`, `attemptNumber`) the
human-approval capture above established, without growing either real
consumer's input. It does not prove anything about git-agent's or
campaign-agent's *own* retry-capable nodes specifically -- only that the
event shape keeps attempt and occurrence counters independent when a real
LangGraph `RetryPolicy` fires. A capture against a real consumer's own retry
path, if one is needed later, is separately scoped work.
