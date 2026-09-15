# Internal consumer support research

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
| IC-03 | Dynamic `interrupt()` inside node bodies is not a static interrupt declaration. | Current campaign/git approval nodes need runtime evidence; static absence must not mean no human gate. |
| IC-04 | Caller-selected graph IDs exist, but no integration here proves core observer events map to those IDs and nodes across resume or nesting. Resume identity specifically is now probed and pinned per commit: [`agent-workflow-core/capture/`](agent-workflow-core/capture/) shows `event_run_id` absent at `v0.1.0.beta.3` and stable across a re-entry on `main`. | Shared consumer/host adapter work, with core as an event-contract collaborator. Graph/node topology correlation and nesting remain unproved. |
| IC-05 | Factories require policy and return compiled objects; CLI accepts an existing object, not factory invocation/arguments. | Consumer-owned import-safe export recipe first; new factory CLI behavior is not automatically necessary. A runnable recipe mapped to both factories is recorded in [`import-safe-export/`](import-safe-export/README.md). |
| IC-06 | Loops and possible destinations are representable; profile changes, approval validity, effect receipts and retry budgets are not structural facts. | Keep these in domain runtime evidence/extensions; do not widen the core to policy or execution. |

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

Before opening follow-up issues, inspect the destination repository's existing
issues and link this snapshot. Producer/CLI work belongs in agent-topology;
external event contracts and export fixtures belong to their owning repositories.
Read access and issue filing are authorized; external code edits are not.

## Interpretation boundaries

Follow [ADR 0001](../../decisions/0001-scope-topology-extraction-and-trace-correlation.md),
[ADR 0002](../../decisions/0002-record-what-could-not-be-observed.md),
[ADR 0008](../../decisions/0008-experimental-consumer-interpretation.md), and
[ADR 0011](../../decisions/0011-document-local-consumer-addressable-graph-ids.md).
A complete document or successful strict extraction does not prove approval
coverage. Unknown child identity does not prove a node has no child. Equal
structure hashes do not prove equal policy, content, checkpoints or interpretation.
