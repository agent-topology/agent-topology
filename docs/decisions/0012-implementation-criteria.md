# ADR 0012 implementation criteria

These requirements are part of [accepted ADR 0012](0012-nested-graph-identity-traversal-and-compatibility.md).
They refine the identity/addressing contract for
[#136](https://github.com/agent-topology/agent-topology/issues/136) and
[#140](https://github.com/agent-topology/agent-topology/issues/140) without
implementing either. They do not cover CLI depth parity (#141) or runtime
correlation evidence (#142), which depend on this contract but are scoped
separately.

## Shared gate for #136 and #140

- Never remove or rename a retained parent node. A node ADR 0008 would assert
  `opaque-child` for keeps its declared id in its containing graph's
  `structure.nodes` at every depth, including depths beyond the materialization
  budget.
- Derive a materialized child's `graphs[].id` as `f"{parent_graph_id}:{parent_node_id}"`
  (recursively for deeper levels), never from framework object identity and
  never by inspecting or splitting an existing id string.
- Before emitting a derived id, check it against every id already assigned in
  the document in deterministic depth-first, sorted-sibling order. On
  collision, do not materialize that node; record `child-graph-id-collision`
  on the parent node instead. Never emit a document that relies on the
  validator to catch a producer-caused collision, and never invent a
  disambiguating suffix.
- A materialized child graph carries the same completeness contract as any
  other `graphs[]` entry: its own gaps attach to its own elements via its own
  `graphId`, never as a blanket note on the parent.
- `depth = N` materializes levels `1..N`; level `N`'s own children remain
  governed by the unchanged depth-0 opaque-child contract. Depth 0 output is
  byte-identical to current output: no `subgraphId`, no additional `graphs[]`
  entries, `x-topology-interpretation` revision `"1"`.
- Node/router bodies must not be invoked while walking a nested compiled
  child's own declarations, exactly as at depth 0 today.
- Retire the `expanded-subgraph-metadata` gap once this contract ships; do not
  repurpose its code for a different meaning.

## Identity and addressing (#136)

| Minimum input | Required outcome |
| --- | --- |
| Parent/child/grandchild, depth 0 | Unchanged: `sub` retained, `subgraph: opaque-child`, no `subgraphId`, one graph. |
| Same graph, depth 1 | `sub` retained in `main`; `main:sub` materialized with `sub.subgraphId == "main:sub"`; `grand` retained opaque inside `main:sub`. |
| Same graph, depth 2 | `main:sub` and `main:sub:grand` both materialized; `leaf` retained opaque inside `main:sub:grand`. |
| One compiled child bound at node ids `left` and `right` | `main:left` and `main:right` materialized independently; equal structure, equal hash per graph, no shared-definition assertion. |
| Node id containing `:` at a nesting boundary, e.g. a top-level node literally named `sub:grand` | No parentage inferred from the collision; the real nested child at derived address `sub:grand` either materializes cleanly (if the literal node's id is not actually `graphs[].id`-shaped in a colliding way) or falls back under the collision rule below. Assert coverage for both a colliding and a non-colliding delimiter-containing name. |
| Wrapper-hidden child at any positive depth | Retained, `subgraph: unknown/identity-unavailable`, no `subgraphId`, identical to depth 0. |
| Ordinary node whose id or display name resembles a nested path (e.g. `"main:sub"` as a plain node, no compiled child) | No child graph invented; extends `test_display_name_is_not_child_evidence`. |
| Derived id collides with an existing `graphs[].id` (caller-supplied or previously derived) | Node stays retained and opaque; `child-graph-id-collision` gap on the parent node; document remains schema-valid. |
| Depth requested beyond actual nesting (e.g. depth=2 on a two-level graph) | No error; the deepest real level's children materialize, nothing further exists to materialize. |
| Authored: `subgraphId` referencing an absent `graphs[].id` | Rejected by existing ADR 0011 validation; shared oracle case, not producer output. |
| Authored: two graphs independently assigned the same id | Rejected by existing ADR 0011 validation; shared oracle case, not producer output. |

Validate at both languages: identical documents produce identical canonical
bytes and hash; source locators and package provenance may differ and must be
recorded as such. Reverse declaration order as a separate check, matching the
existing depth-0 and depth>0 fixture conventions.

## Recursive metadata and revision 2 (#140)

Populate `branch`, `sentinel`, and `entry` for a materialized child's own
nodes using the same evidence rules ADR 0008 already defines for a root graph
— a materialized child is not a degraded view. Populate `subgraph` for a
materialized parent node as `materialized-child` (revision `"2"`), with
evidence kind `materialized-subgraph-reference` and a source that names both
the containing `graphs[].id` and the node's `subgraphId`. Reject `opaque-child`
on any node carrying `subgraphId`; reject `materialized-child` on any node
without one. Depth-0 documents and any document with no materialized node
continue to use revision `"1"` unchanged; a revision-2 document only exists
once a `subgraphId` is actually emitted.

Add revision-2 authored contract cases alongside the existing ADR 0008 cases,
labeled separately from real producer fixtures, covering: a materialized
parent's `subgraph` fact, an invalid `opaque-child`-with-`subgraphId`
combination, and an invalid `materialized-child`-without-`subgraphId`
combination. Keep every revision-1 case passing unchanged under revision 2's
validator; a revision-1 reader must still treat a revision-2 document's
extension as unrecognized and opaque, never partially parsed.

## Non-goals for this pair of Tasks

- CLI `--depth` parity is [#141](https://github.com/agent-topology/agent-topology/issues/141).
- Sanitized runtime evidence, checkpoint-namespace correlation, and repeated
  dynamic invocation are [#142](https://github.com/agent-topology/agent-topology/issues/142).
- No package/version/release work belongs here.
