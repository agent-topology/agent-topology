# 0008. Experimental consumer interpretation

- Status: Accepted
- Date: 2026-09-11
- Scope: workspace
- Issue: [#96](https://github.com/agent-topology/agent-topology/issues/96)

## Context

The [reconciled F1–F6 record](../research/f1-f6-reproduction/README.md)
from PR #108 distinguishes measured facts from suggested remedies. F1's
fixture-name injection demonstrates extension acceptance and hash exclusion,
not producer knowledge of selection or scheduling. Single- and list-returning
routers with the same declared destinations yield the same static document.
F2 shows an unconfirmed root in `entryNodeIds`; it does not prove which router
would reach that root. F3 demonstrates an unmarked compiled child at depth 0.
F5 demonstrates framework sentinels without a common role contract.

F4 is an edges-only consumer trap: joins already preserve their own identity.
F6 reproduces an ESM consumption failure, but the missing-documentation and
zero-runtime-dependency claims were withdrawn. Neither needs a new topology
field. Airflow operator classes do not establish exclusive or concurrent
execution, and TaskGroup has not been shown equivalent to a compiled child.
Python/TypeScript agreement on LangGraph is not second-framework evidence.

Current Python `describe` and TypeScript `describeWithVersion` calculate entry
candidates by subtracting edge and join targets from visible nodes. They retain
root builder declarations but use drawable structure for expanded traversal.
The latter has a graph-level `expanded-subgraph-metadata` gap. This decision
preserves those core behaviors and existing `x-langgraph` metadata.

## Decision

Accept revision `1` of the graph-level `x-topology-interpretation` extension.
It is a common experimental vocabulary owned by the specification maintainers,
implemented by each producer, and read without importing a framework. Its
acceptance defines the contract for Tasks T3–T6; it does not claim those Tasks
are implemented or that published beta.2 packages emit it.

ADRs [0001](0001-scope-topology-extraction-and-trace-correlation.md),
[0002](0002-record-what-could-not-be-observed.md),
[0003](0003-canonical-ordering-and-versioned-structure-hash.md),
[0004](0004-rendering-is-not-part-of-the-core-document.md), and
[0005](0005-vendor-neutrality-is-provisional-at-v0.md) remain in force.
This adds a bounded interpretation experiment, not policy verdicts, coverage,
scheduling, rendering, or a claim that a common extension is a neutral core.

### Wire shape and ownership

The separate [extension schema](../../spec/experimental/interpretation-v1.schema.json)
is normative for shape; this ADR is normative for meaning and evidence.
It is not referenced by the core schema or shipped as a new public validator.
Only `graphs[i]["x-topology-interpretation"]` is a recognized placement:

```json
{
  "version": "1",
  "traversalDepth": 0,
  "nodes": [
    {
      "nodeId": "router",
      "branch": {"status": "unknown", "reason": "selection-not-observable"}
    }
  ]
}
```

`version` is the extension revision, independent of package, topology, and hash
versions. `traversalDepth` is the nonnegative requested extraction depth for this
snapshot, not a promise about how far expansion succeeded. Each record refers
to exactly one visible node in its containing graph. Records are unique and
sorted by Unicode code point order of `nodeId`. Omit records without facts.
The record's optional `branch`, `subgraph`, `sentinel`, and `entry` fields are
owned respectively by T3, T4, T5, and T6. Tasks merge their facts into the same
record; they must not replace other Tasks' fields. Nested shapes are closed in
revision 1. There are no graph references, edge copies, or synthetic nodes.

### Absent, unknown, and known

Absence of the extension, a record, or a fact means **no assertion**: legacy,
unsupported, not inspected, or not applicable are not distinguishable. It is
never evidence of a negative value. A recognized producer capability emits
`unknown` when it inspected an applicable node but cannot establish the fact.
Unknown has a reason and no value or evidence. Known has a value and evidence,
and no reason. `null`, empty objects, and invented statuses are invalid.

Known evidence is an object with `kind` and nonempty `source`. `source` is a
stable, producer-owned locator for the inspected structural surface (for example
`compiled.builder.edges`), not a filename heuristic or arbitrary user label.
The document's provenance supplies producer/framework versions. Each producer
must maintain version-pinned tests explaining how every emitted source locator
proves its fact, including disqualifying counterexamples. The schema validates
the assertion's shape; it cannot prove that the producer told the truth.
No callbacks, node bodies, router functions, or graph invocation may be run to
obtain these assertions. Additional framework-specific details stay in
`x-langgraph`; consumers do not need them to interpret known values.

| Fact | Known value | Required evidence kind | Unknown reasons |
| --- | --- | --- | --- |
| `branch` | `all-declared` | `unconditional-edges` | `selection-not-observable`, `scope-not-inspected` |
| `subgraph` | `opaque-child`, `not-child` | `compiled-child`, `ordinary-node` respectively | `identity-unavailable`, `scope-not-inspected` |
| `sentinel` | `start`, `end`, `ordinary` | `framework-sentinel` for start/end; `ordinary-node` otherwise | `identity-unavailable`, `scope-not-inspected` |
| `entry` | `confirmed`, `not-entry` | `framework-entry` | `entry-not-established`, `scope-not-inspected` |

`entry` additionally requires `observedRoot: boolean` in both known and unknown
states. It records a calculation from this snapshot, independent of the entry
assertion: true iff no core edge or join has this node as its target. Join
sources have outgoing connectivity; a join target has incoming connectivity.
Cycles may have no observed roots. An observed root can be unconfirmed, and a
confirmed entry can have incoming cycle edges.

### Branch destinations, selection, and scheduling

Core conditional edges record observable possible destinations; they do not
promise that the list is exhaustive where a routing gap exists. `branch` says
only what the producer can establish about selection at the named node.

`all-declared` means at least two outgoing **ordinary direct edges** were
observed as unconditional declarations at that scope. It asserts that those
declarations are not alternatives selected by a router. It does not assert
simultaneous scheduling, success, actual task execution, fan-out width, or a
selection rule for joins. Emit it only if the same node has no conditional
routing, dynamic destination declaration, or unresolved routing evidence.
The evidence review must establish that the inspected declaration surface is
complete for that node. A drawable edge marked direct alone is insufficient.

Emit `unknown` for every inspected conditional router, including single- and
list-returning callbacks, return-annotated routers, loops with routing, Send,
unknown targets, multiple routers, and mixed direct/conditional routing.
A node with only one direct edge or no outgoing routing has no `branch` fact.
A multi-source join does not prove the policy of its upstream divergence.
Revision 1 deliberately has no known `exclusive`, `concurrent`, or
`all-possible-targets` value. Adding one requires a new revision with a source
that proves selection separately from possible destinations and execution.
Fixture names, operator class alone, and return annotations do not supply that
proof. The testbed's `x-topology-branch` trial is not an alias for this contract.

### Child identity and sentinel roles

`opaque-child` means a node is confirmed to contain a compiled child graph and
that child is not represented as a separate graph document in this snapshot.
It permits a consumer to offer an expansion attempt; it promises neither
successful expansion nor complete child metadata. `not-child` requires an
inspected ordinary-node representation that rules out a compiled child at the
supported structural surface. Failed inspection, a wrapper that hides identity,
a display name, a callable class, and TaskGroup analogy cannot establish it.
There is no invented `subgraphId` and no placeholder child graph.

`start` and `end` identify framework-owned sentinels from the supported compiled
graph's identity and reserved sentinel mechanism. `ordinary` requires positive
ordinary-node membership. A producer may use its framework's actual sentinel
constants after verifying ownership; a consumer must not match literal IDs.
Names such as `start`, `end`, or `__start__-user` are not role evidence.
Presentation choices stay with consumers. Hiding a sentinel never authorizes
mutating the stored core or losing its edges, joins, gaps, or trace identity.

### Observed roots versus confirmed entries

Keep `entryNodeIds` exactly as the producer currently emits it. `confirmed`
means the framework declares that node an entry into this graph's execution,
not merely a node with no observed predecessor. For the current LangGraph
scope the framework START sentinel is the confirmed entry; its direct or
conditional successors are not thereby alternative confirmed entries.
`not-entry` requires affirmative framework evidence excluding that node as an
entry, not merely an incoming edge. For revision 1 LangGraph emits this only
for a confirmed END sentinel. Other inspected nodes use `unknown` unless a
future version-pinned structural proof establishes exclusion.

For F2, START is observed-root/confirmed and `target` is observed-root/unknown
with reason `entry-not-established`. The existing gap stays on `router`.
There is no `causedBy`, inferred router-to-orphan link, invented edge, or gap
on the target. Multiple unknown routers, disconnected candidates, joins, and
roots in a graph without routing gaps follow the same rule. A consumer may
show a candidate plus uncertainty; it must not promote it to an execution
entry. Legacy entry arrays alone remain candidates for this interpretation.

### Traversal scope and completeness

At depth 0, inspect the root compiled graph's structural declarations. At every
positive depth, annotate only visible nodes whose identities can be mapped
unambiguously to inspected structural evidence. Retained root nodes can retain
facts if that evidence still describes their visible connections. Rewritten,
flattened, or child nodes without that mapping use `scope-not-inspected` for
applicable facts; never inherit root selection or sentinel roles by name.
`entry.observedRoot` is still calculated from the emitted snapshot.
An opaque child still visible at a positive depth can remain `opaque-child`.
An expanded-away parent has no record. A separately materialized child graph
uses core `subgraphId` only when that graph actually exists; revision 1 does not
introduce a new materialization path or a known expanded-child value.

Unknown extension facts do not add core gaps, change completeness, or fail
strict extraction. Producer-wide inability remains a producer limitation under
ADR 0002; graph-specific existing routing and expanded-metadata gaps remain
unchanged. Local unknown facts communicate uncertainty without inventing a
new completeness contract. Unsupported structural evidence cannot be silently
replaced with a plausible known fact to satisfy a fixture.

### Independent validation and deterministic output

Validation has three distinct layers:

1. The existing core validator checks the topology, references and completeness.
   It remains extension-agnostic, even for malformed recognized extensions.
2. Opt-in extension validation checks revision/shape, placement, unique visible
   node references, sorted records, observed-root calculations, evidence-kind
   compatibility, and `all-declared` structural preconditions. A start/end
   sentinel cannot be an opaque child; a known start cannot be `not-entry`,
   and a known end cannot be `confirmed`.
3. Producer conformance checks the truth of evidence using real minimum graphs,
   no-user-execution assertions and supported framework versions. A document
   alone cannot prove the absence of hidden routing or identity of a callable.

A consumer distinguishes absent, supported-valid, unsupported-revision and
invalid extension results. Unsupported and invalid facts provide no trusted
interpretation; report their local status and continue exposing the valid core.
Do not coerce them to known or claim that core validation proved the extension.
The schema and [document cases](../../spec/experimental/interpretation-cases.json)
are shared across languages. They are authored contract examples, explicitly
not captured producer output. The repository's example tests provide a
framework-free reference check; production validator APIs are not added here.

Core canonicalization already sorts object keys and preserves extension arrays.
Producers sort records before finalization. Array order is an extension rule,
not a change to core canonicalization. Python and TypeScript must agree on
extension validation and canonical bytes for the same complete document;
producer documents may differ in provenance and evidence source locators.
Semantic parity compares states, values, node identities and evidence kinds,
with those expected language-specific differences recorded explicitly.

### Compatibility and promotion

Keep `topologyVersion: "0.1"`, hash algorithm `1`, all existing hashed fields,
and the core schema unchanged. Equal structure hashes do not establish equal
extension metadata, selection information, child identity, or sentinel/entry
interpretation. Adding, removing or changing this extension leaves a graph's
structure hash unchanged. Consumers caching interpretation must compare the
extension revision and canonical extension content as well as core identity;
structure hash alone is insufficient.

Revision 1 readers use exact version negotiation. Changes to fields, accepted
values, evidence meaning, or array semantics require a new revision and shared
migration cases, even during the experiment. A producer correction under an
unchanged definition changes its package version and must document that old
facts may differ; do not rewrite historical documents. Unrecognized revisions
are opaque. Removing experimental support requires package release/migration
notes. None of this alters published beta.2 history or qualifies beta.3 artifacts.

Promotion requires a follow-up ADR, a real consumer demonstrating the need,
independent producer evidence including a structurally different framework,
positive/negative/unknown fixtures in independent languages, a reproducible
validation story, and an explicit migration/version/hash-coverage decision.
Airflow source review and two LangGraph language implementations alone do not
meet that bar. Any required core field or hash change is deferred to that
separate follow-up, outside beta.3 and Tasks T3–T6.

## Consequences and implementation gates

The [T3–T6 acceptance matrix](0008-implementation-criteria.md) is part of this
accepted decision and supplies the concrete requirements for #97–#100. Their
implementation follows this contract on the beta.3 RC workflow. A schema-valid
invented known value is still a conformance failure. Static unknown is a valid
outcome and must remain visible to consumers.

This accepts a small vocabulary instead of the proposed trial modes. It costs
additional metadata and separate validation, and it cannot answer execution or
coverage questions. It makes the available evidence and its limits usable to
consumers without silently strengthening existing core fields.
