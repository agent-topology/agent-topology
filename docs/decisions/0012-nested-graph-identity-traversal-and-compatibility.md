# 0012. Nested graph identity, traversal, and compatibility

- Status: Accepted
- Date: 2026-09-15
- Scope: workspace
- Issue: [#139](https://github.com/agent-topology/agent-topology/issues/139)

## Context

[Issue #136](https://github.com/agent-topology/agent-topology/issues/136)
reproduces the current positive-depth contract. A three-level nested compiled
graph (`outer` containing node `sub` bound to `child`, `child` containing node
`grand` bound to `grandchild`) produces these node id lists from
[`describe`](https://github.com/agent-topology/agent-topology/blob/d9aee90a6259b5a4eaa874fdfa9da0d56c1ab082/packages/python/langgraph/src/agent_topology/langgraph/_describe.py#L365-L505):

```text
depth=0  [__end__, __start__, sub]
depth=1  [__end__, __start__, sub:grand]
depth=2  [__end__, __start__, sub:grand:leaf]
```

At every positive depth the retained root node `sub` disappears and is
replaced by a colon-joined flattened name produced by LangGraph's own
`get_graph(xray=depth)` drawable traversal
([`_drawable_structure`](https://github.com/agent-topology/agent-topology/blob/d9aee90a6259b5a4eaa874fdfa9da0d56c1ab082/packages/python/langgraph/src/agent_topology/langgraph/_describe.py#L128-L163)).
A LangGraph runtime still executes the outer task under node id `sub`. A trace
correlation consumer — the first intended use under
[ADR 0001](0001-scope-topology-extraction-and-trace-correlation.md) — cannot
match that execution against the expanded document. The gap is not silent:
depth 0 already asserts `subgraph: opaque-child` for `sub` via
[ADR 0008](0008-experimental-consumer-interpretation.md)'s
`x-topology-interpretation`, and every positive-depth document already carries
an `expanded-subgraph-metadata` graph-specific gap. Nothing here was
undetected; it was recorded as incomplete and left for this decision.

The schema already has the field this needs. `node.subgraphId` has existed
since the original contract and is already part of the version-1 structure
hash projection
([`_NODE_HASH_FIELDS`](../../packages/python/spec/src/agent_topology/spec/_canonical.py)),
but no producer has ever emitted it; tests set it by hand
([`test_materialized_reference_rejects_opaque_assertion`](../../packages/python/langgraph/tests/test_subgraph.py)).
ADR 0008 anticipated this gap explicitly: "revision 1 does not introduce a new
materialization path or a known expanded-child value," and its
[T4 implementation criteria](0008-implementation-criteria.md) already require
rejecting an `opaque-child` assertion on a node linked by `subgraphId`, without
saying what should be asserted instead. [ADR 0011](0011-document-local-consumer-addressable-graph-ids.md)
made `graphs[].id` a caller-selected, document-local, unique address, but only
considered addresses chosen once per top-level `describe` call; it did not
consider a producer synthesizing additional addresses for nested children
inside one call.

[Internal-consumer research](../research/internal-consumer/README.md) (IC-02)
found the same open question from the demand side: "a reusable child appearing
in multiple parent positions will also need an explicit distinction between
graph definition ID, call-site identity and runtime checkpoint namespace,"
concluding that "materializing child records requires an explicit
contract/ADR decision." This is that decision.

## Decision

### Retain the parent; materialize the child

At every depth, a node that ADR 0008's `subgraph` interpretation would assert
`opaque-child` for — a node holding a confirmed compiled child, mapped by
runtime identity, never by display name or wrapper inspection — is retained in
its containing graph's `structure.nodes` under its own declared id. It is
never removed, renamed, or replaced by a flattened descendant id. This alone
satisfies #136's core requirement: a runtime-observable parent node never
becomes unaddressable because expansion was requested.

When the node's nesting level is within the caller's requested `depth` budget,
the producer additionally derives structure for that child from the child
compiled graph's own declarations — the same builder-level extraction already
used for the root graph at depth 0, not the framework's drawable/xray
flattening view that currently erases parents. That structure becomes a new
entry in the document's `graphs` array, and the parent node gains a core
`subgraphId` referencing it. A materialized child graph is a first-class
`graphs[]` entry under [ADR 0011](0011-document-local-consumer-addressable-graph-ids.md):
it has its own `id`, `structure`, `entryNodeIds`/`exitNodeIds`, and its own
graph-specific gaps. It is not a degraded or partial view, and it carries no
different completeness contract than a root graph. Concretely populating a
materialized child's branch/join/interrupt/sentinel/entry facts is the
recursive-extraction work owned by
[#140](https://github.com/agent-topology/agent-topology/issues/140); this ADR
fixes only the identity and addressing contract that work must satisfy.

`depth=0` is exactly the zero-levels-materialized case of this same rule: no
graph is materialized, no `subgraphId` is emitted, and the node's `subgraph`
fact remains `opaque-child` exactly as today. Depth-0 output — schema shape,
node/edge/join content, `structureHash`, `x-topology-interpretation` revision
`"1"` content — is unchanged, byte for byte.

### Deterministic, call-site-derived graph identifiers

A materialized child's `graphs[].id` is derived, not chosen freely:

```text
child_graph_id = f"{parent_graph_id}:{parent_node_id}"
```

applied recursively, so a grandchild materialized from `sub:grand` inside
graph `main:sub` (from root graph `main`, node `sub`) receives id
`main:sub:grand`. The colon is a debugging convenience, matching the informal
path shape LangGraph's own `xray` traversal already produces; it is not a
parsing contract. A consumer resolves parentage only through core
`subgraphId` and `graphs[].id`, never by splitting an id on a delimiter —
exactly the existing rule in #136's requested contract ("consumers do not
infer it by splitting flattened ids"), now also binding on producers'
internal reasoning about their own generated ids.

Deriving the id from **position** rather than from framework object identity
directly answers the "repeated child use" requirement. Two node ids that
happen to bind the same compiled child object — `left` and `right` both
holding the identical `retry_step` graph, say — receive distinct ids
`main:left` and `main:right`. No shared-definition fact is asserted or needed;
each materialized graph is independently addressed and independently hashed.
Two materialized graphs that happen to be structurally identical hash
identically per graph, which is correct and requires no special case: it is
the same behavior [ADR 0011](0011-document-local-consumer-addressable-graph-ids.md)
already gives two independently composed documents that describe the same
topology. This ADR does not assert, and a document must not assert, that two
equal-hash graphs share one underlying compiled definition; that remains
unobservable from structure alone.

### Collision handling

A derived id can collide with a caller-supplied `graph_id`, with another
derived id, or — deliberately included as a minimum test case — with a node
id that itself contains the delimiter, e.g. a top-level node literally named
`sub:grand` alongside a real nested child at derived address `sub:grand`.
[ADR 0011](0011-document-local-consumer-addressable-graph-ids.md) already
makes a duplicate `graphs[].id` a hard validation error naming the repeated
value; this decision does not weaken that. A producer must never emit a
document relying on the validator to catch its own collision, and must never
resolve one by inventing a disambiguating suffix — an arbitrary suffix would
be an unaddressed, consumer-invisible convenience value, exactly what "no
consumer-private core fields are introduced by convenience" rules out.

Instead: before emitting a derived id, the producer checks it against every
id already assigned in the document (the caller-supplied root id and every
derived id produced earlier in the same traversal, in deterministic
depth-first, sorted-sibling order). On collision, that node's child is **not**
materialized — it is retained exactly as at depth 0, `subgraph: opaque-child`,
no `subgraphId` — and the producer records a new graph-specific gap on the
parent node:

```json
{
  "code": "child-graph-id-collision",
  "message": "A materialized child graph id would collide with an existing graph id; the child was left opaque.",
  "element": {"graphId": "main", "kind": "node", "id": "sub"}
}
```

A producer's own output is therefore always valid and never ambiguous. An
*authored* document exercising the validator's collision rejection directly
(two graphs independently assigned the same id, with no producer in the loop)
remains a separate, explicitly invalid conformance example, consistent with
ADR 0008's practice of authored cases that are not captured producer output.

### Depth as a recursive materialization budget

`depth` keeps its existing type (non-negative integer) and its existing
depth-0 meaning, but its positive-depth meaning changes: it is no longer
passed through to the framework's own flattening traversal. `depth = N` means
levels `1..N` are materialized as separate addressable graphs by the rule
above; level `N`'s own children remain governed by the unchanged depth-0
opaque-child contract. This replaces the prior behavior, where `depth = N`
flattened the framework's view exactly `N` levels down while erasing every
shallower parent, including levels `1..N-1`. The prior behavior is not
preserved at any positive depth: it violated #136's addressability
requirement at every level it touched, and no consumer had a completeness
guarantee to rely on, since `expanded-subgraph-metadata` already marked every
positive-depth document incomplete. Retiring that gap code is a consequence of
this decision, not a separate one: once a materialized child carries the same
completeness contract as any other graph, a blanket "shape only, not fully
inspected" note on the parent has nothing left to qualify. A producer that has
not yet implemented recursive extraction may continue emitting the current
flattened, gapped shape at positive depth until it does; it must not emit
`subgraphId` without also switching to this identity model.

Traversal is always bounded by the caller-supplied finite integer; there is no
automatic or unbounded recursive expansion regardless of how deeply the
compiled structure actually nests, matching #136's explicit non-goal.

### Hidden and wrapped child identity

Materialization requires exactly the evidence ADR 0008 already requires for a
known `opaque-child` fact: positive `compiled-child` evidence from mapped
runtime identity. A wrapper function or other callable that hides a compiled
child — `subgraph: unknown/identity-unavailable` — is never materialized at
any depth. It is retained as an ordinary node with unknown subgraph status,
identically to how it already renders at depth 0 today. No expansion is
attempted, because LangGraph's own traversal cannot see through the wrapper
either; there is no false negative and no false `not-child` either. A future
producer for a different framework that cannot independently extract a
materialized child's own structure must not emit a half-materialized graph;
it either does not materialize (falls back to the depth-0 opaque contract for
that node, exactly as the collision case above does) or it materializes fully
under the same completeness contract as any other graph. No partial
materialization state exists.

### Recursive and cyclic structural references

Recursion is bounded by the finite requested `depth`, independent of whatever
cycles exist inside any one graph's own edges — a loop is an ordinary edge
relationship, already representable and already tested at depth 0, and does
not cause additional traversal. Depth exhaustion always terminates
materialization in at most `depth` levels of work, regardless of the compiled
structure's own shape. A structural self-reference — a compiled child object
appearing as its own descendant — is not specially detected, because building
one is not possible under the supported frameworks: compiling a parent graph
requires its child nodes to already be compiled and bound, so a child cannot
hold a reference to a parent that does not yet exist. If a future framework
can construct one anyway, this decision still bounds it: each level receives
its own call-site-derived id (`main:sub:sub:sub:...` grows with the requested
depth, never with the structure's own recursion), so the document stays
finite and well-defined at whatever depth was actually requested, and no node
body or callable is ever invoked to discover this.

### Relationship to runtime checkpoint namespaces

A materialized child's derived `graphs[].id` (equivalently, its parent node's
call-site path) is a **static correlation key**, not a verbatim runtime
checkpoint namespace. LangGraph builds its actual runtime checkpoint namespace
per invocation, and includes a runtime-generated task identifier segment that
cannot be known statically — this is exactly the dynamic fan-out boundary
[ADR 0001](0001-scope-topology-extraction-and-trace-correlation.md) already
draws between what a static document can and cannot see. A consumer
correlates runtime evidence to this document by matching the node-id portion
of an observed checkpoint namespace against the document's call-site path for
that node, not by requiring byte equality with the full runtime namespace
string. When one static call-site path corresponds to more than one runtime
task identifier — the same declared child node invoked more than once, for
example under `Send` fan-out — the document cannot enumerate those
invocations; that is an existing producer limitation under
[ADR 0002](0002-record-what-could-not-be-observed.md) (dynamic behavior is
invisible to static extraction), not a new gap this decision introduces, and
proving that correlation end to end remains
[#142](https://github.com/agent-topology/agent-topology/issues/142)'s
responsibility, not this ADR's.

### Reconciling ADR 0008

This is the follow-up ADR that 0008's "Compatibility and promotion" section
anticipated for a materialization path. It supersedes only that anticipation,
not any other part of 0008.

`x-topology-interpretation` advances to revision `"2"`. Revision 2 is
additive: every revision-1 field, value, and rule for `branch`, `sentinel`,
and `entry` carries forward unchanged. It adds exactly one new `subgraph`
value:

| Fact | Known value | Required evidence kind |
| --- | --- | --- |
| `subgraph` | `materialized-child` | `materialized-subgraph-reference` (source references `graphs[].id` and the node's `subgraphId`) |

`materialized-child` is required, and `opaque-child` is invalid, whenever core
`subgraphId` is present on that node — formalizing the rule ADR 0008's T4
criteria already stated informally. A document with `subgraphId` set and no
`subgraph` fact at all remains valid: the extension is optional everywhere, as
under revision 1.

Depth-0 documents continue to emit revision `"1"` unchanged, since
materialization never happens at depth 0. A producer that emits `subgraphId`
at positive depth must emit revision `"2"` wherever it emits the extension at
all, never revision `"1"` describing a materialized node as merely opaque.
Per ADR 0008's existing negotiation rule, revision `"2"` is a new, exact,
independently recognized revision; a revision-1-only reader treats it as
unrecognized and opaque, exactly as it already would for any other
unsupported revision. This is not a promotion of the experiment to core
status, and it changes no core field, schema, or hash-algorithm version.

### Reconciling ADR 0011

Derived child graph ids remain, in every sense ADR 0011 cares about, "document
local addresses... selected by the caller at extraction time": the producer
derives them deterministically from the one root address the caller did
supply, they are unique within the `graphs` array (enforced, with a defined
producer-side fallback on the rare collision), and every `element.graphId` and
`subgraphId` continues to resolve against that same unique set. ADR 0011 never
required manual selection of every graph id, only uniqueness, a non-empty
string, and a defined default; this decision narrows how positive-depth
producers satisfy that requirement for nested children without amending
ADR 0011's rule itself. `graphs[].name` remains independent, author-owned, and
untouched: a materialized child graph may carry a `name` sourced the same way
a root graph already does (`compiled_graph.get_name()` on the child object),
optional and non-identifying exactly as today.

### Depth=0 compatibility and positive-depth migration

- `topologyVersion` stays `"0.1"`. No schema shape changes: `subgraphId` and
  `graphs[]` already exist; this decision only makes producers populate them.
- `structureHash.algorithmVersion` stays `"1"`. The version-1 projection
  already iterates every `graphs[]` entry and already selects `subgraphId` in
  its node projection — materializing more graphs and populating that field
  is fully covered by the existing algorithm, exactly as adding a composed
  document's second graph already is under ADR 0011. Depth-0 hashes are
  unaffected. Positive-depth hashes change, because the structure genuinely
  changed — a real structural correction, in the sense ADR 0003 already
  distinguishes from drift, not a hashing-rule change.
- `x-topology-interpretation` advances to revision `"2"` only where a document
  materializes a child, as defined above.
- Positive-depth document *shape* changes for any existing caller: retained
  parent ids and additional `graphs[]` entries replace flattened colon-joined
  node ids, and `expanded-subgraph-metadata` stops appearing once a producer
  implements this contract. This is an accepted breaking change to
  previously-incomplete, already-gapped experimental output; no compatibility
  promise existed for positive depth before this decision, and depth-0 output
  — the only output with a compatibility promise — does not move.
- Equal structure hashes across documents never established equal extension
  metadata under ADR 0008, and still do not here: two documents can hash
  identically while differing in which `subgraph` values are asserted, or in
  interpretation revision, exactly as ADR 0008 already requires callers to
  check separately.

### Minimum example matrix

The following minimum cases are binding acceptance criteria for
[#136](https://github.com/agent-topology/agent-topology/issues/136) and
[#140](https://github.com/agent-topology/agent-topology/issues/140); shared
conformance fixtures for them are implementation work for those issues, not
this ADR, following the precedent of ADR 0008's T3–T6 tables versus its own
implementation-criteria companion.

| Minimum input | Required outcome |
| --- | --- |
| Parent/child/grandchild at depth 0, 1, 2 | Depth 0: unchanged opaque-child. Depth 1: `main:sub` materialized, `grand` inside it opaque. Depth 2: `main:sub` and `main:sub:grand` both materialized, `leaf` opaque inside the latter. |
| One compiled child bound at two sibling node ids | Two independent materialized graphs, `main:left` and `main:right`; no shared-definition fact asserted. |
| A node id containing `:` at a nesting boundary | No false parentage from string-splitting; the derived id is checked for collision like any other. |
| Two independently caused graphs sharing one id (authored, not producer output) | Rejected by the existing ADR 0011 duplicate-id validation. |
| An ordinary node with a display name or id resembling a nested path | No child graph invented; extends the existing display-name-is-not-evidence case. |
| A `subgraphId` referencing a graph id absent from `graphs[]` (authored) | Rejected by the existing ADR 0011 unknown-reference validation. |
| Depth exhausted at the deepest requested level | Deepest level's own child stays opaque, evidence `compiled-child`, no `subgraphId`. |
| Wrapper-hidden child at positive depth | Retained unmaterialized, `unknown/identity-unavailable`, identical to depth 0. |
| Derived id collides with an existing graph id | Not materialized; `child-graph-id-collision` gap recorded on the parent node; document remains valid. |

## Consequences

- [#136](https://github.com/agent-topology/agent-topology/issues/136) and
  [#140](https://github.com/agent-topology/agent-topology/issues/140) can now
  state decision-complete acceptance criteria referencing this ADR's id
  derivation, collision gap, retired `expanded-subgraph-metadata` code, and
  revision-2 extension, and are unblocked to begin implementation.
- Positive-depth output changes shape for any existing caller; depth-0 output,
  the only output with a standing compatibility promise, does not change.
- `topologyVersion` and `structureHash.algorithmVersion` are unaffected.
  `x-topology-interpretation` gains revision `"2"`, used only where a document
  materializes a child.
- A new graph-specific gap code, `child-graph-id-collision`, joins the
  existing vocabulary. `expanded-subgraph-metadata` becomes dead once a
  producer implements this contract; it is not repurposed.
- Both supported producers (Python and TypeScript) implement this identically,
  per the existing cross-language parity convention already established for
  ADR 0008's extension.

## What we are explicitly not doing

- Implementing [#136](https://github.com/agent-topology/agent-topology/issues/136),
  [#140](https://github.com/agent-topology/agent-topology/issues/140),
  [#141](https://github.com/agent-topology/agent-topology/issues/141), or
  [#142](https://github.com/agent-topology/agent-topology/issues/142). This is
  a decision record.
- Changing `topologyVersion`, the hash algorithm, or the core schema shape.
  `subgraphId` and `graphs[]` already exist; this decision only defines when
  and how a producer populates them.
- Promising unbounded or automatic recursive expansion. Depth remains a
  caller-chosen, finite budget.
- Asserting byte equality between a document's call-site address and a
  LangGraph runtime checkpoint namespace, or enumerating repeated dynamic
  invocations of one static call site. That remains runtime-evidence work
  under [#142](https://github.com/agent-topology/agent-topology/issues/142).
- Asserting that two structurally identical materialized graphs share one
  underlying compiled definition. That is unobservable from structure alone
  and is not claimed.
- Promoting `x-topology-interpretation` out of experimental status. Revision 2
  remains bound by ADR 0008's promotion bar.

## Revisiting

Revisit the collision fallback (falling back to opaque rather than exposing
the deepest reachable address) if a real consumer demonstrates it loses
information the fallback address would have preserved. Revisit the
call-site-derivation rule if a second, structurally different framework
cannot independently extract a materialized child's own declarations, per
[ADR 0005](0005-vendor-neutrality-is-provisional-at-v0.md)'s standing
provisional-core caveat.
