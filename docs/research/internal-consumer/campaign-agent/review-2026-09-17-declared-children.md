# Campaign consumer recheck — declared children — 2026-09-17

[Repository](https://github.com/milocosmopolitan/campaign-agent) ·
[11-factory inventory re-run](probe-2026-09-17-declared-children.json) ·
[Hierarchy-link verification](hierarchy-links-2026-09-17.json) ·
[Verification script](verify_declared_children.py) ·
[Prior recheck (superseded for R2)](review-2026-09-17.md)

Baseline: campaign-agent
[commit `a1532d5eed2d356792d5c3ee460d2bb8fb23db1e`](https://github.com/milocosmopolitan/campaign-agent/commit/a1532d5eed2d356792d5c3ee460d2bb8fb23db1e),
the merge of
[PR #63](https://github.com/milocosmopolitan/campaign-agent/pull/63) closing
[campaign-agent#62](https://github.com/milocosmopolitan/campaign-agent/issues/62).
No tag or release exists yet; this is remote main. Inspected against
agent-topology commit `b89a704d577d831d9991ef9cdb7b2150d89bcb9c` (main, past
[#185](https://github.com/agent-topology/agent-topology/issues/185)'s merge of
`declare_children`). LangGraph is unchanged at 1.2.11.

This supersedes [review-2026-09-17.md](review-2026-09-17.md)'s statement that
"the six wrapper nodes have unknown child identity" for `channel_concept` and
`channel_production` only; every other finding in that report (interrupts,
join/identity gaps, the other eight factories) is unaffected and remains
current.

## What changed in campaign-agent

[PR #63](https://github.com/milocosmopolitan/campaign-agent/pull/63) wraps
each factory's return value in `declare_children`, exactly as requested by
[campaign-agent#62](https://github.com/milocosmopolitan/campaign-agent/issues/62):
[`channel_concept/graph.py`](https://github.com/milocosmopolitan/campaign-agent/blob/a1532d5eed2d356792d5c3ee460d2bb8fb23db1e/src/campaign_agent/channel_concept/graph.py#L1714-L1723),
[`channel_production/graph.py`](https://github.com/milocosmopolitan/campaign-agent/blob/a1532d5eed2d356792d5c3ee460d2bb8fb23db1e/src/campaign_agent/channel_production/graph.py#L2717-L2725).
No node function, state schema, or invocation call site changed. `pyproject.toml`
now depends on the `agent-topology-langgraph` git revision that publishes
`declare_children` (`f569f27aa31a42ac8cfa142598f16c41df8f3d06`).

## Re-run of the 11-factory inventory

[`pre-beta-review-2026-09-17/probe.py`](../pre-beta-review-2026-09-17/probe.py)
was re-run unmodified against this commit
([full output](probe-2026-09-17-declared-children.json)). All ten factories
still compile, and every depth-0/1/2 document still passes
`agent_topology.spec.validate_document` with zero gaps, exact declared
edge/join counts, and full node retention — unchanged from the prior recheck.

The only behavior change is in `unknownChildNodes`: `channel_concept`'s
`prepare_brief`, `draft_copy`, `review_copy` and `channel_production`'s
`revise_copy`, `review_copy`, `prepare_copy_feedback` no longer appear in that
list at any depth. `graphs` count for both factories rises from 1 to 4 at
depth 1 and 2 (the parent plus its three now-materialized children) — as
before, a graph-count change alone does not prove the link points at the
correct child, which is why this recheck adds a dedicated verification below.

## Hierarchy links, verified per relationship

[`verify_declared_children.py`](verify_declared_children.py) checks each of
the six relationships two ways and asserts both hold
([full output](hierarchy-links-2026-09-17.json)):

1. At depth 0 (before materialization), the wrapped node's
   `x-topology-interpretation[].subgraph` fact is `status: known`,
   `evidence.kind: declared-child-call`, `evidence.source:
   compiled.__agent_topology_children__` — confirmed via
   [`_subgraph_interpretation`](https://github.com/agent-topology/agent-topology/blob/b89a704d577d831d9991ef9cdb7b2150d89bcb9c/packages/python/langgraph/src/agent_topology/langgraph/_describe.py#L301-L359),
   not inferred from name or position.
2. At depth 2, the node gains `structure.nodes[].subgraphId` (e.g.
   `channel_concept:prepare_brief`), the referenced entry in `graphs[]`
   materializes, and that materialized child's node id set is **identical**
   to the declared child factory's own independently compiled, standalone
   `describe()` output at depth 0 — proving the relationship points at the
   real `copy_brief_prepare`/`copy_draft`/`copy_review`/`copy_revision`/
   `copy_feedback_prepare` graphs, not merely incrementing a count.

| Parent | Node id | Declared child | Depth-0 evidence | Materialized subgraph id | Matches standalone factory |
| --- | --- | --- | --- | --- | --- |
| channel_concept | prepare_brief | copy_brief_prepare | declared-child-call | channel_concept:prepare_brief | yes (9/9 nodes) |
| channel_concept | draft_copy | copy_draft | declared-child-call | channel_concept:draft_copy | yes (9/9 nodes) |
| channel_concept | review_copy | copy_review | declared-child-call | channel_concept:review_copy | yes (9/9 nodes) |
| channel_production | revise_copy | copy_revision | declared-child-call | channel_production:revise_copy | yes (9/9 nodes) |
| channel_production | review_copy | copy_review | declared-child-call | channel_production:review_copy | yes (9/9 nodes) |
| channel_production | prepare_copy_feedback | copy_feedback_prepare | declared-child-call | channel_production:prepare_copy_feedback | yes (9/9 nodes) |

All six assertions passed; the script raises on any mismatch, so a clean run
is the evidence.

## Remaining boundaries, unchanged

`declare_children` is metadata-only and unverified against actual runtime
invocation (per ADR 0014's non-goals): a wrong declaration would be a
campaign-agent-owned correctness bug, the same way a wrong `graph_id` already
is. The seven dynamic `interrupt()` sites, the join-identity defect (R1), and
IC-01/03/05/06 from the prior reports are untouched by this change and remain
open. `channel_production` review/revision paths' retry/decision authority is
still structural-only, not attempt-count or authority proof.
