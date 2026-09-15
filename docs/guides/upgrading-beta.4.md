# Upgrade from beta.3 to beta.4

[Documentation home](../README.md) · [Release notes](../releases/v0.1.0-beta.4.md)

Status: **Prepared in source; not published.** The installation commands in
this repository's README, package READMEs, and quickstarts still select the
published beta.3 versions. This guide describes what changes for a beta.3
consumer once beta.4 passes registry verification; do not install these
candidate versions from a public registry before then.

## Select the packages

| Package | beta.3 → beta.4 candidate | Runtime | Framework |
| --- | --- | --- | --- |
| `agent-topology-spec` | `0.1.0b3` → `0.1.0b4` | Python 3.11–3.14 | None |
| `agent-topology-langgraph` | `0.1.0b3` → `0.1.0b4` | Python 3.11–3.14 | LangGraph 1.2.10–1.2.11 |
| `@agent-topology/spec` | `0.1.0-beta.3` → `0.1.0-beta.4` | Node.js 20+ | None |
| `@agent-topology/langgraph` | `0.1.0-beta.3` → `0.1.0-beta.4` | Node.js 20+ | LangGraph.js 1.4.14 |

Python uses PEP 440 `0.1.0b4`; npm uses SemVer `0.1.0-beta.4`. Package
versions remain independent of the document format (`0.1`) and structure-hash
algorithm (`1`), neither of which changes in this candidate. The Python
producer will require `agent-topology-spec>=0.1.0b4,<0.2.0`; the npm
producer's peer will be the exact `@agent-topology/spec@0.1.0-beta.4`.
LangGraph and LangGraph.js compatibility ranges are unchanged from beta.3.

## No core stability claim

Nothing below changes `topologyVersion` or `structureHash.algorithm`. Every
change is either additive (`graphs[]` gains entries it already had a schema
slot for, and a new experimental `x-topology-interpretation` revision) or a
documentation correction. This candidate does not claim vendor neutrality, a
stable v1 contract, or backward compatibility across a future format or
hash-algorithm transition. See the
[0.1 contract's known limitations](../0.1-contract.md#known-limitations-and-excluded-consumers).

## Depth-0 compatibility is explicit

If every call in your integration uses the default `depth=0` (or never passes
`depth`), **nothing observable changes**: schema shape, node/edge/join
content, `structureHash`, and `x-topology-interpretation` revision `"1"`
content are byte-identical to beta.3. A node holding a confirmed compiled
child keeps the `known/opaque-child` fact it has today; no `subgraphId` is
emitted and no child graph is materialized at depth 0. You can adopt beta.4
purely for this compatibility guarantee without changing any depth-consuming
code. The remainder of this guide only applies if you request `depth > 0`.

## Positive-depth document and address changes

Before this candidate, `depth = N` asked the framework's own `xray` traversal
to flatten `N` levels of nesting into one graph. That view **erased every
retained parent**: a node the runtime still executes under id `sub` vanished
from `structure.nodes`, replaced by a colon-joined name like `sub:grand`, and
the document recorded this loss as an `expanded-subgraph-metadata` gap. A
trace-correlation consumer could not match runtime execution against that
expanded shape.

Current source replaces that behavior:

- A node holding a confirmed compiled child — mapped by runtime identity,
  never by display name or wrapper inspection — **keeps its own declared id**
  in its containing graph's `structure.nodes` at every depth. It is never
  removed, renamed, or replaced by a flattened descendant id.
- Within the requested `depth` budget, that node additionally gains a core
  `subgraphId` addressing the child as its own first-class `graphs[]` entry,
  derived deterministically as `parentGraphId:parentNodeId`, applied
  recursively (a grandchild inside `main:sub` is `main:sub:grand`). The colon
  is a debugging convenience, not a parsing contract: resolve parentage only
  through core `subgraphId` and `graphs[].id`, never by splitting an id on a
  delimiter.
- Two node ids that happen to bind the same compiled child object — a reusable
  subgraph called from two sibling positions — receive two independently
  addressed, independently hashed materialized graphs (for example
  `main:left` and `main:right`). No shared-definition fact is asserted.
- If a derived id would collide with an existing graph id (including a
  caller-supplied `graph_id`, another derived id, or a node id that itself
  contains `:`), the child is **not** materialized. It stays exactly as at
  depth 0 — `opaque-child`, no `subgraphId` — and the parent node gains a new
  `child-graph-id-collision` gap. A producer's own output is therefore always
  valid; the collision case never relies on the validator to reject it.
- `expanded-subgraph-metadata` can no longer be emitted. Once a materialized
  child carries the same completeness contract as any other graph, the old
  blanket "shape only, not fully inspected" note has nothing left to qualify.

**This is an accepted breaking change to previously incomplete, already-gapped
experimental output.** No compatibility promise ever existed for positive
depth before this decision; depth-0 output — the only output with a standing
compatibility promise — does not move. If your integration reads positive-depth
documents today, expect node ids and the `graphs[]` array shape to differ from
beta.3. See
[ADR 0012](../decisions/0012-nested-graph-identity-traversal-and-compatibility.md)
for the full decision, including the minimum example matrix, and the
[consumer guide's opaque-children section](consuming-documents.md#experimental-opaque-children)
for the field-by-field consumption rules.

## Graph-ID selection is unchanged, only extended

[ADR 0011](../decisions/0011-document-local-consumer-addressable-graph-ids.md)
already made `graphs[].id` a document-local address you select at extraction
time (`graph_id` in Python, `graphId` in TypeScript, `--graph-id` on the CLI),
defaulting to `main`. This candidate does not change that call: it only
defines how a producer derives ids for *nested children it materializes
inside one call*, starting from the one root id you did supply. You still
choose exactly one address per top-level `describe` call; composing several
producer outputs into one document is still your responsibility, not a
producer feature. A duplicate `graphs[].id` remains a hard validation error
naming the repeated value.

## Hash and cache implications

- `structureHash.algorithmVersion` stays `"1"`. The version-1 projection
  already iterates every `graphs[]` entry and already selects `subgraphId` in
  its node projection, so materializing more graphs and populating that field
  is fully covered by the existing algorithm — no new hash version, exactly
  as adding a composed document's second graph already was under ADR 0011.
- Depth-0 hashes are unaffected by this candidate.
- Positive-depth hashes **do change**, because the structure genuinely
  changed — this is a real structural correction, not a hashing-rule change.
  Do not cache a positive-depth document, or anything keyed by its
  `structureHash`, across this upgrade without recomputing it.
- Two materialized graphs that happen to be structurally identical hash
  identically per graph. This is correct and requires no special case; it
  does not assert that they share one underlying compiled definition, which
  remains unobservable from structure alone.
- Equal structure hashes never established equal extension metadata under
  [ADR 0008](../decisions/0008-experimental-consumer-interpretation.md), and
  still do not here: two documents can hash identically while differing in
  which `subgraph` values are asserted, or in interpretation revision. A
  cache keyed only on `structureHash` will silently mix revision `"1"` and
  revision `"2"` extension content; key on `(structureHash,
  x-topology-interpretation revision)` if you cache interpretation-derived
  facts at all.

## `x-topology-interpretation` advances to revision `"2"` where materialization happens

Revision `"2"` is strictly additive: every revision-1 `branch`, `sentinel`,
and `entry` field, value, and rule carries forward unchanged. It adds exactly
one new `subgraph` value, `materialized-child` (evidence kind
`materialized-subgraph-reference`, naming the containing `graphs[].id` and the
node's own `subgraphId`). `materialized-child` is required, and
`opaque-child` is invalid, on any node carrying core `subgraphId`; the reverse
is also invalid. Depth-0 documents, and any positive-depth document that
materializes nothing, continue to emit revision `"1"` unchanged. Per ADR
0008's existing negotiation rule, a revision-1-only reader treats revision
`"2"` as an unrecognized, opaque extension — exactly as it already would for
any other unsupported revision. This is not a promotion of the experiment out
of `x-*` status. See the
[consumer guide](consuming-documents.md#experimental-opaque-children).

## Use `--depth` from the CLI

The Python CLI now exposes the API's traversal depth directly:

```bash
agt describe path/to/graph.py:graph --out topology.json --depth 1
```

`--depth` defaults to `0` (unchanged, opaque children) and accepts only a
non-negative integer; an invalid, missing, or negative value is a usage error
(exit status `2`). Output at a given depth is equivalent to calling the
Python API with the same `depth`, including `--strict` exit status `6` for an
actual graph-specific gap. The CLI still only imports and describes a
module-level compiled-object target; it never invokes the graph or calls a
factory to build one. See the [CLI reference](../reference/cli.md).

## Factory-owned graphs and the CLI target

`agt` accepts an existing, already-compiled module-level object — it does not
invoke a factory, and this candidate does not add factory-argument CLI
support. If your graph is built by a factory that requires policy, a model
gateway, or another invocation-time argument, `agt` cannot call it for you.
The supported pattern is a small, consumer-owned **import-safe export**
module: construct the compiled object once at import time, using safe
defaults or test doubles for whatever the factory needs, and export it as a
plain module-level attribute that `agt describe path/to/module.py:object` can
target — without invoking or scheduling the graph. See the
[import-safe export recipe](../research/internal-consumer/import-safe-export/README.md)
for a runnable example mapped to two real factory-shaped graphs.

## Minimum consumer replay

Before adopting positive depth in your own integration, replay the minimum
cases this candidate is verified against rather than reconstructing your own
fixture from scratch:

- **Address correlation across depth and repeated call sites.**
  [`test_addressing_conformance.py`](../../packages/python/langgraph/tests/test_addressing_conformance.py)
  exercises a parent/child/grandchild graph at `depth=2` (asserting `{"main",
  "main:child", "main:child:inner"}` stay independently addressable) and one
  compiled child reused at two sibling call sites at `depth=1` (asserting
  `{"main", "main:left", "main:right"}`). Run it with
  `uv run --project packages/python/langgraph --group test pytest packages/python/langgraph/tests`.
- **A real dynamic interrupt, resume, and repeated attempt.**
  [`docs/research/internal-consumer/agent-workflow-core/capture/README.md`](../research/internal-consumer/agent-workflow-core/capture/README.md#dynamic-interrupt-resume-and-repeated-attempt-issue-152)
  records an offline-replayable capture of a real `langgraph.types.interrupt`
  pausing and resuming via `Command(resume=...)`, and a separate real
  `RetryPolicy` repeated attempt distinguished by invocation count, pause
  state, and `attempt.number`. Regenerating or replaying it requires no
  network access or private checkout; exact commands and fixture hashes are
  recorded there.

Neither replay proves that *your* consuming application's own factories,
approval nodes, or resume wiring behave the same way — see the boundary
below.

## Topology vs. dynamic pauses, approval validity, and runtime effects

A complete document, or a successful strict extraction, does not prove
approval coverage, and this candidate does not change that boundary:

- A dynamic `interrupt()` raised inside a node body is still not a static
  interrupt declaration in the topology document. A consumer cannot build an
  approval-node inventory from the document alone; the current LangGraph
  producer limitation (`dynamic-interrupts`) is unchanged.
- Approval validity, effect receipts, and retry budgets are not structural
  facts and are not added by this candidate's extension. They belong in
  domain runtime evidence and vendor extensions, per
  [ADR 0001](../decisions/0001-scope-topology-extraction-and-trace-correlation.md)
  and [ADR 0002](../decisions/0002-record-what-could-not-be-observed.md).
- A materialized child's derived `graphs[].id` is a **static correlation
  key**, not a verbatim runtime checkpoint namespace. LangGraph's actual
  runtime namespace includes a runtime-generated task identifier that cannot
  be known statically. Correlate by matching the node-id portion of an
  observed checkpoint namespace against the document's call-site path, not by
  requiring byte equality with the full runtime string. When one static
  call site corresponds to more than one runtime invocation (for example
  under `Send` fan-out), the document cannot enumerate those invocations —
  an existing producer limitation, not a new gap.
- Unknown child identity does not prove a node has no child, and equal
  structure hashes do not prove equal policy, content, checkpoints, or
  interpretation.

See the
[internal-consumer research's interpretation boundaries](../research/internal-consumer/README.md#interpretation-boundaries)
and [final dispositions](../research/internal-consumer/README.md#final-dispositions-issue-154)
for the full evidence behind this boundary.

## Remaining uncertainty

- The collision fallback (leaving a colliding child opaque rather than
  exposing some other address) is a deliberate default, revisited only if a
  real consumer demonstrates it loses information an alternative address
  would have preserved. See
  [ADR 0012's revisiting section](../decisions/0012-nested-graph-identity-traversal-and-compatibility.md#revisiting).
- The call-site-derivation rule for materialized child ids is evidenced
  against LangGraph and LangGraph.js only. A structurally different framework
  that cannot independently extract a materialized child's own declarations
  is out of scope for this candidate; see
  [ADR 0005](../decisions/0005-vendor-neutrality-is-provisional-at-v0.md).
- The import-safe export recipe replaces the need for CLI factory-argument
  support by design, not because factory invocation was evaluated and
  rejected on technical grounds; a future factory-aware CLI mode remains
  future work if consumer evidence demonstrates the recipe pattern is
  insufficient.
- Graph/node topology correlation against a live, non-replayed event stream
  in a real consuming application (as opposed to the offline capture above)
  remains open; this candidate proves the correlation mechanism, not any
  specific consumer's wiring to it.
