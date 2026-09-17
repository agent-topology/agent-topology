# Internal consumer support research

Latest recheck: [2026-09-17 pre-beta review](pre-beta-review-2026-09-17/README.md)
compiles all 11 current campaign/git factories, records wrapped-child limitations,
and reproduces join identity collisions. The September 15 findings below are
historical; use the dated recheck for current consumer readiness.

The pre-beta review's R2 finding (wrapped children hidden by lambdas) is now
decided: [wrapped-child-contract-2026-09-17](wrapped-child-contract-2026-09-17/README.md)
is the probe evidence behind [ADR 0014](../../decisions/0014-explicit-construction-time-child-declaration.md),
which [#180](https://github.com/agent-topology/agent-topology/issues/180)
implements against campaign's real six call sites.

Recorded 2026-09-15. All three reference repositories are in development.
This is historical research, not a new support guarantee or an accepted design.

## Baselines

| Repository | Selected baseline | Inspected main commit | Report |
| --- | --- | --- | --- |
| agent-workflow-core | `v0.1.0.beta.3` → `94cd31f58d8e94d55ea2d952c6db5508539ea53f` | `876f6a8a4ba863424e1f85bc92f18dce59147957` | [Core](agent-workflow-core/README.md) |
| campaign-agent | main; no release or tag | `5593bb77558525f9292c11bcb77db43729dc0328` | [Campaign](campaign-agent/README.md) |
| git-agent | main; no release or tag | `d85d53fa0b24b198e9863c6027806f2440f38bd9` | [Git](git-agent/README.md) |

Each directory contains `snapshot.json` with full hashes and verification method.
The core tag is annotated: the commit above is its peeled commit, not the tag
object `3c1eed353757bc9eb461b8e66f9a4f43e0019467`.
The latest published release is a prerelease; no stable release was found.
Remote refs and GitHub release listings were checked, and local HEAD matched
remote main with clean worktrees at inspection.

The comparison target is agent-topology commit
`d9aee90a6259b5a4eaa874fdfa9da0d56c1ab082` (nearest tag `v0.1.0-beta.3`).
Claims below concern that source snapshot. We did not install released artifacts,
execute external workflows, or run an end-to-end integration probe. Findings are
`source-verified`, design statements are `documented`, and proposed integrations
remain `pending`, using the [research evidence rules](../README.md).

## Findings across consumers

| ID | Current support and missing behavior | Impact and ownership |
| --- | --- | --- |
| IC-01 | Python/TypeScript APIs already accept depth. Python CLI has no `--depth`. | agent-topology CLI usability gap for an already compiled export object; API is the workaround. |
| IC-02 | Positive depth extracts drawable shape into one graph; child joins, routing and interrupt declarations are not fully inspected. Separate child graph materialization is absent. | agent-topology producer research; relevant to campaign's future composition, not a demonstrated blocker in its current flat graph. |
| IC-03 | Dynamic `interrupt()` inside node bodies is not a static interrupt declaration. A pause-and-resume is now probed against `main`: [`agent-workflow-core/capture/README.md`](agent-workflow-core/capture/README.md#dynamic-interrupt-resume-and-repeated-attempt-issue-152) shows a real `langgraph.types.interrupt` pausing the graph, resuming via `Command(resume=...)`, and re-running the pre-interrupt node body on resume. | Current campaign/git approval nodes need runtime evidence; static absence must not mean no human gate. This narrow pause/resume-replay finding is verified; it does not prove campaign/git's own approval nodes are wired the same way. |
| IC-04 | Caller-selected graph IDs exist, but no integration here proves core observer events map to those IDs and nodes across resume or nesting. Resume identity specifically is now probed and pinned per commit: [`agent-workflow-core/capture/`](agent-workflow-core/capture/) shows `event_run_id` absent at `v0.1.0.beta.3` and stable across a re-entry on `main`. | Shared consumer/host adapter work, with core as an event-contract collaborator. Graph/node topology correlation and nesting remain unproved. |
| IC-05 | Factories require policy and return compiled objects; CLI accepts an existing object, not factory invocation/arguments. | Consumer-owned import-safe export recipe first; new factory CLI behavior is not automatically necessary. A runnable recipe mapped to both factories is recorded in [`import-safe-export/`](import-safe-export/README.md). |
| IC-06 | Loops and possible destinations are representable; profile changes, approval validity, effect receipts and retry budgets are not structural facts. A same-node repeated-attempt is now probed against `main`: a real LangGraph `RetryPolicy` re-attempts one node within a single invocation, recorded with an explicit `attempt.number`, structurally distinct from the IC-03 pause/resume case. | Keep these in domain runtime evidence/extensions; do not widen the core to policy or execution. The capture does not claim retry budgets, authorization, or effect success. |

Evidence: [CLI parser](https://github.com/agent-topology/agent-topology/blob/d9aee90a6259b5a4eaa874fdfa9da0d56c1ab082/packages/python/langgraph/src/agent_topology/langgraph/_cli.py#L49-L74),
[depth extraction and expanded-metadata gap](https://github.com/agent-topology/agent-topology/blob/d9aee90a6259b5a4eaa874fdfa9da0d56c1ab082/packages/python/langgraph/src/agent_topology/langgraph/_describe.py#L365-L505),
[child identity](https://github.com/agent-topology/agent-topology/blob/d9aee90a6259b5a4eaa874fdfa9da0d56c1ab082/packages/python/langgraph/src/agent_topology/langgraph/_describe.py#L232-L265),
and the consumer-specific permalinks below. The schema's ability to reference a
`subgraphId` does not establish that the producer emits separate child records.

All three lockfiles select LangGraph `1.2.11`, inside the current producer's
`1.2.10–1.2.11` supported range. Their broader `langgraph>=0.6` dependency
allowance is not evidence that agent-topology supports that entire range.
No current locked-version incompatibility was found.

## Suggested work sequence and minimum evidence

These are research follow-ups, not newly filed issues or implementation commitments.

1. **Prove the current integration boundary (IC-04/05).** Use one compiled
   two-node graph and two sanitized step events. Measure exact graph/node matching,
   no graph invocation during extraction, and distinction between graph display
   name and document ID. A host/core adapter owns runtime event normalization.
   The resume/`event_run_id` half of IC-04 is now probed separately per pinned
   commit in [`agent-workflow-core/capture/`](agent-workflow-core/capture/);
   graph/node topology matching against a live event stream remains open.
2. **Expose CLI depth parity (IC-01).** Reuse a parent with one compiled child and
   one child node. Measure that CLI depth reaches the producer and matches the API;
   test depth zero, one and invalid values. No full campaign workflow is needed.
3. **Investigate recursive metadata and identity (IC-02).** Use a two-level nested
   graph, one child conditional router, and a separate minimum all-join fixture.
   Measure depth 0/1/2 boundaries, local gaps, child declarations and parent/child
   trace addresses. Add a wrapper-hidden child as a distinct negative case.
   Materializing child records requires an explicit contract/ADR decision.
4. **Prove runtime enrichment (IC-03/06).** Use one dynamic interrupt and one
   resume, then a separate same-node retry. Measure pause evidence and distinct
   attempts without claiming topology proves authorization or effect success.
   This has run, pinned to `main`, in
   [`agent-workflow-core/capture/README.md`](agent-workflow-core/capture/README.md#dynamic-interrupt-resume-and-repeated-attempt-issue-152):
   a real interrupt pauses and resumes (with the pre-interrupt node body
   re-running on resume), and a separate real `RetryPolicy` repeated-attempt
   stays inside one invocation, distinguished by invocation count, pause
   state, and `attempt.number`. Campaign/git's own approval and routing
   wiring, and nested-graph behavior, remain open.

Before opening follow-up issues, inspect the destination repository's existing
issues and link this snapshot. Producer/CLI work belongs in agent-topology;
external event contracts and export fixtures belong to their owning repositories.
Read access and issue filing are authorized; external code edits are not.

## Final dispositions (issue #154)

Recorded 2026-09-15, closing [issue #154](https://github.com/agent-topology/agent-topology/issues/154)
against [#142](https://github.com/agent-topology/agent-topology/issues/142)
acceptance criterion 7 (and criterion 1's snapshot linkage). The four
coordinated Tasks consolidated here are closed:
[#150](https://github.com/agent-topology/agent-topology/issues/150) (fixture
verification), [#151](https://github.com/agent-topology/agent-topology/issues/151)
(source-pinned adapter/replay), [#152](https://github.com/agent-topology/agent-topology/issues/152)
(real dynamic-interrupt/resume/repeated-attempt capture), and
[#153](https://github.com/agent-topology/agent-topology/issues/153) (import-safe
export recipe). Each row below closes with exactly one of the three
dispositions #154 defines: **implementation delivered** (agent-topology itself
now does the thing the finding said was missing), **consumer evidence
delivered** (a committed, replayable fixture proves a specific claim, without
claiming a consuming repository's own integration code is wired the same
way), or **explicit limitation retained** (the gap is real and intentional
and stays recorded, not silently dropped).

| ID | Final disposition | Evidence |
| --- | --- | --- |
| IC-01 | Implementation delivered | [#141](https://github.com/agent-topology/agent-topology/issues/141) added `--depth` to the Python CLI, verified API-equivalent to `describe(depth=...)` by `test_depth_matches_python_api_at_each_level` in [`test_cli.py`](../../../packages/python/langgraph/tests/test_cli.py). The original "Python CLI has no `--depth`" gap no longer exists. |
| IC-02 | Implementation delivered | [#136](https://github.com/agent-topology/agent-topology/issues/136) retains parent identity and materializes children at positive depth ([ADR 0012](../../decisions/0012-nested-graph-identity-traversal-and-compatibility.md)); [#140](https://github.com/agent-topology/agent-topology/issues/140) preserves child joins, routing, and static-interrupt declarations inspected in their own scope (`conformance/subgraph-cases.json`, `test_branch.py`, `test_entry.py`, `test_sentinel.py`, `test_subgraph.py`). Separate child graph materialization, called out as absent in the original finding, now exists. |
| IC-03 | Consumer evidence delivered, with an explicit limitation retained | A real dynamic `interrupt()`/resume pair against `agent-workflow-core` main is captured and offline-replayable: [`capture/README.md`](agent-workflow-core/capture/README.md#dynamic-interrupt-resume-and-repeated-attempt-issue-152). The limitation is retained by design ([ADR 0002](../../decisions/0002-record-what-could-not-be-observed.md)): a dynamic interrupt raised inside a node body is still not a static interrupt declaration in the topology document, so a consumer cannot build an approval-node inventory from the document alone. |
| IC-04 | Consumer evidence delivered | Two independent halves of this finding now have committed evidence: resume identity (`event_run_id` collapsing two invocations into one logical run on `main`, confirmed absent at the pinned tag) in [`capture/README.md`](agent-workflow-core/capture/README.md#disposition); and graph/node topology addressing across depth 0/1/2, repeated child call sites, missing graph ids, unknown nodes, and ambiguous evidence in [`test_addressing_conformance.py`](../../../packages/python/langgraph/tests/test_addressing_conformance.py) (#150). Neither proves campaign-agent's or git-agent's own integration code sets `event_run_id` or emits qualified node addresses -- that stays an explicit, unverified gap in those repositories, not a claim this repository makes. |
| IC-05 | Consumer evidence delivered; CLI factory invocation is an explicit limitation retained by choice | [`import-safe-export/README.md`](import-safe-export/README.md) runs a standalone, import-safe recipe mapped, with source permalinks, to both campaign-agent's and git-agent's inspected factory surfaces. Per the original finding's own resolution direction ("consumer-owned import-safe export recipe first"), factory-argument CLI invocation was deliberately not built; the recipe pattern replaces the need for it rather than leaving it as an open gap. |
| IC-06 | Split: consumer evidence delivered for attempt/occurrence distinction; explicit limitation retained for policy/effect facts | A real LangGraph `RetryPolicy` repeated-attempt, distinguished from resume by invocation count, pause state, and an explicit `attempt.number`, is captured and offline-replayable in [`capture/README.md`](agent-workflow-core/capture/README.md#dynamic-interrupt-resume-and-repeated-attempt-issue-152). Profile changes, approval validity, effect receipts, and retry budgets remain, by design, outside the topology document -- domain runtime evidence and extensions own them, per [ADR 0001](../../decisions/0001-scope-topology-extraction-and-trace-correlation.md) and [ADR 0002](../../decisions/0002-record-what-could-not-be-observed.md). |

### New producer behavior exercised in this set

[#150](https://github.com/agent-topology/agent-topology/issues/150)'s
[`test_addressing_conformance.py`](../../../packages/python/langgraph/tests/test_addressing_conformance.py)
runs the shared `correlate` module against the current, real `describe()` --
i.e. against the parent-identity and materialized-child behavior #136 and
#140 delivered, not a pre-#136 flattened document.
`test_parent_child_grandchild_addresses_resolve_independently` exercises
`depth=2` and asserts `{"main", "main:child", "main:child:inner"}` stay
independently addressable; `test_repeated_child_call_sites_stay_distinct_addresses`
exercises `depth=1` with one compiled child reused at two call sites and
asserts `{"main", "main:left", "main:right"}`. This satisfies "new producer
behavior is exercised before #142 closes" for parent identity from within
this consolidated set. Child-metadata (joins/routing/static-interrupt) and
CLI-depth behavior are separately exercised by the dedicated conformance
suites #140 and #141 each shipped with their own delivery (`test_subgraph.py`,
`test_branch.py`, `test_entry.py`, `test_sentinel.py`,
`conformance/subgraph-cases.json`; `test_cli.py`'s
`test_depth_matches_python_api_at_each_level`), which run as part of the
standard `uv run --project packages/python/langgraph --group test pytest packages/python/langgraph/tests`
command -- confirmed passing, not newly added by this Task.

### Commands, hashes, and limitations consolidated

- **Source-pinned adapter/replay (#151):** exact generation and replay
  commands, and sha256 fixture hashes, are recorded in
  [`capture/README.md`](agent-workflow-core/capture/README.md#regenerating-requires-local-read-access-to-agent-workflow-core).
- **Real capture -- dynamic interrupt, resume, repeated attempt (#152):**
  exact generation and replay commands, and sha256 fixture hashes, are
  recorded in [`capture/README.md`](agent-workflow-core/capture/README.md#dynamic-interrupt-resume-and-repeated-attempt-issue-152).
- **Import-safe export recipe (#153):** the run command is recorded in
  [`import-safe-export/README.md`](import-safe-export/README.md#running-it).
  The recipe has no stored fixture hash: it produces a live canonical
  document from a compiled object on each run, checked with `--check`
  against the schema and `provenance.source.kind` rather than a
  byte-for-byte fixture.
- **Fixture verification (#150):** no external commands or hashes; the
  fixtures are ordinary pytest cases in
  [`test_addressing_conformance.py`](../../../packages/python/langgraph/tests/test_addressing_conformance.py),
  run by `uv run --project packages/python/langgraph --group test pytest packages/python/langgraph/tests`.
- **Limitations retained across all four Tasks:** no authorization, budget
  compliance, or successful-effect claim is made from topology or capture
  evidence alone; no campaign-agent or git-agent source is executed or
  vendored; offline replay requires no private checkout, external service,
  or network access.

## Interpretation boundaries

Follow [ADR 0001](../../decisions/0001-scope-topology-extraction-and-trace-correlation.md),
[ADR 0002](../../decisions/0002-record-what-could-not-be-observed.md),
[ADR 0008](../../decisions/0008-experimental-consumer-interpretation.md), and
[ADR 0011](../../decisions/0011-document-local-consumer-addressable-graph-ids.md).
A complete document or successful strict extraction does not prove approval
coverage. Unknown child identity does not prove a node has no child. Equal
structure hashes do not prove equal policy, content, checkpoints or interpretation.
