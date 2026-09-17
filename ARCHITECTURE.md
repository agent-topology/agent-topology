# Architecture

`agent-topology` publishes a derived, descriptive JSON document for the internal
shape of a compiled agent workflow. The document is the product boundary. A
framework producer observes a compiled graph, normalises what it can see, and
states what it could not see; consumers correlate or present that result without
changing its meaning.

This document describes the implemented public-preview architecture. The repository
contains the canonical schema and fixtures, Python and TypeScript specification
and LangGraph packages, the Python CLI, a trace-correlation consumer example,
release automation, documentation, and accepted decisions. All four initial beta
packages are recorded as published in the [release notes](docs/releases/v0.1.0-beta.1.md).
Each subsequent package publication remains a separate release operation.

## System context

```text
framework source
      │ compile (owned by the framework/application)
      ▼
compiled graph object
      │ inspect in the framework's runtime and language
      ▼
framework producer ───────► producer limitations
      │                    graph-specific gaps
      │ normalise
      ▼
agent-topology document
      │
      ├──► conformance runner / fixtures
      ├──► trace correlation (first intended consumer)
      └──► downstream consumers, such as renderers
```

The library does not author, execute, schedule, host, register, or render an
agent workflow. It describes a graph that another framework has already
compiled.

## Architectural boundaries

### Specification and conformance

The specification owns the JSON document shape, format version, canonical form,
structure-hash contract, schema, and language-neutral fixtures. It must not
depend on LangGraph or any other producer.

Fixtures are the executable compatibility boundary. Every producer is tested
against the same fixture meanings, while producer-specific test harnesses may be
written in the producer's language.

### Framework producers

A producer runs in the same process and language as the compiled graph it
inspects. It translates framework concepts into the core document and puts
framework-only facts under a namespaced `x-*` extension.

The first producer targets Python LangGraph, and the TypeScript producer targets
LangGraph.js through an idiomatic asynchronous API. Their agreement validates
cross-language extraction rather than vendor neutrality. Only a producer for a
structurally different framework can test the provisional core boundary.

### Consumers

Consumers depend on the document, never on producer internals. Trace
correlation is the first intended use. Rendering is a downstream consumer and
must surface local uncertainty; diagram output is not part of core conformance.

Policy verdicts and path-coverage generation remain out of scope until the
document can express the branch, join, and completeness semantics they require
without false confidence.

## Document invariants

- The document is derived from a compiled object, not maintained by hand.
- Core fields describe structural facts expected to survive across frameworks.
- Producer limitations describe categories the producer cannot observe in
  principle and do not make one document incomplete.
- Gaps describe graph-specific unknowns, attach to the affected element, and do
  affect completeness.
- Collections are canonicalised before output and hashing.
- The format version, hash-algorithm version, and package versions are separate.
- Multi-source joins remain distinct from several independent incoming edges.
- Graph identifiers are unique document-local addresses selected by producer callers;
  display names are independent and author-owned.
- Vendor neutrality is provisional while only one framework model is observed.

## Graph identity and composition

[ADR 0011](docs/decisions/0011-document-local-consumer-addressable-graph-ids.md)
defines `graphs[].id` as a document-local address. Producers accept a caller-supplied
identifier and retain `main` as the single-graph default. Derived `element.graphId`
references use that identifier, and both specification packages reject duplicates so
`element.graphId` and `subgraphId` resolve to exactly one graph.

Composition remains downstream: a caller chooses distinct identifiers before
extracting each graph, then combines graph records, gaps, and producer limitations
without rewriting derived identities. The compositor owns the new document's
provenance and retains input provenance separately or in a compositor-owned `x-*`
extension when needed. The optional `graphs[].name` is descriptive rather than
identifying. LangGraph authors supply it through `StateGraph.compile(name=...)`.
Changing an identifier changes the existing version-1 structure hash because graph
ids were already covered; no format or hash-algorithm transition is required.

## Accepted experimental interpretation

[ADR 0008](docs/decisions/0008-experimental-consumer-interpretation.md) defines
graph-level `x-topology-interpretation` revision 1 for evidence-backed branch,
opaque-child, sentinel and entry interpretation. Current source implements branch,
child, sentinel and entry facts (#97–#100). Published beta.2 does not emit this extension.
The specification owns its separate opt-in shape and semantic checks; producers
own version-pinned evidence. Core validation remains extension-agnostic.
Unknown interpretation does not change completeness or strict-mode behavior.
Equal structure hashes do not establish equal extension metadata. No core field,
hash algorithm, renderer, or vendor-neutrality claim is added by this decision.

[ADR 0013](docs/decisions/0013-sentinel-branch-promotion-bar-unmet-compatibility-floor.md)
reviewed ADR 0008's promotion bar against real consumer evidence (cordboard's
AT-2/AT-3) and declined promotion: a structurally different framework's
producer evidence, ADR 0005's still-unmet gate, remains the missing
requirement. It publishes a compatibility floor instead — no in-place
redefinition of a shipped revision, permanent forward opacity for
unrecognized revisions, and no silent removal without a superseding ADR and
migration notes — so a consumer can pin to revision `"1"`/`"2"` without
promotion ever happening.

## Nested graph identity and traversal

[ADR 0012](docs/decisions/0012-nested-graph-identity-traversal-and-compatibility.md)
defines how positive-depth expansion retains parent identity instead of
flattening it away. A node holding a confirmed compiled child stays in its
containing graph under its own id at every depth; within the requested depth
budget it additionally gains a core `subgraphId` addressing a materialized
child graph, a first-class `graphs[]` entry under ADR 0011 with its own
structure and gaps. The materialized graph's id is derived deterministically
from its call-site path (`parentGraphId:parentNodeId`), never from framework
object identity, so one compiled child reused at two call sites addresses
distinctly without asserting a shared-definition fact. A derived id that would
collide with an existing one is never emitted; the node stays opaque and a
`child-graph-id-collision` gap records why. `depth = N` now means levels
`1..N` are materialized; level `N`'s own children keep the unchanged depth-0
opaque-child contract, and depth-0 output remains byte-identical to today's.
`x-topology-interpretation` gains revision `"2"`'s `materialized-child`
subgraph value for this case; revision `"1"` and depth-0 documents are
unaffected. `expanded-subgraph-metadata` is retired once a producer
implements this contract. No `topologyVersion` or hash-algorithm change is
required: `subgraphId` and multi-graph hashing were already covered by
algorithm version `1`. A document's call-site address is a static correlation
key, not a LangGraph runtime checkpoint namespace; matching repeated dynamic
invocations of one static call site to runtime evidence remains downstream
work.

## Wrapped child calls: an explicit, construction-time declaration

[ADR 0014](docs/decisions/0014-explicit-construction-time-child-declaration.md)
adds a second, independent way to reach ADR 0012's materialized-child identity
for a real consumer shape ADR 0012 alone cannot see: a node whose bound
runnable is a plain function that itself calls a compiled child's
`.invoke(...)` (campaign-agent's six real call sites), rather than the
compiled child directly. A factory that already holds the child object states
the node-id-to-child mapping once, by direct reference, through
`declare_children(compiled_graph, {node_id: child, ...})`; this is read-only
metadata for `describe()` and changes nothing about how the node runs. Both
framework-native direct composition and LangGraph's own closure-based
subgraph detection were measured and rejected: neither preserves the input
projection, per-call-site context narrowing, or exception-to-state-field
translation these wrapped calls require, and closure detection is source/AST
inspection, the category ADR 0012 already excludes as evidence. ADR 0012's id
derivation, collision handling, and depth budget are unchanged; only the
`x-topology-interpretation` evidence-kind vocabulary gains a second value,
`declared-child-call`, alongside the existing `compiled-child`.

## Accepted numeric canonical form

[ADR 0009](docs/decisions/0009-numeric-canonical-form.md) defines the
canonical byte spelling for a JSON number (the ECMAScript `Number::toString`
/ RFC 8785 rule) and the supported numeric domain: finite `binary64` values,
full stop. [ADR 0010](docs/decisions/0010-numeric-domain-parsed-value-narrowing.md)
amends the domain boundary: an integer literal beyond `2^53` narrows to its
nearest `binary64` double in both languages (matching what `JSON.parse`
already does in TypeScript) rather than being rejected, so canonicalization
stays closed under its own JSON round trip. No core field is numeric today,
and the version-1 hash projection excludes every extension, so this is a
full-document canonicalisation change with no `structureHash.algorithmVersion`
or `topologyVersion` impact. It changes published beta.2 full-document byte
output for documents whose extensions carry numbers once the fixed
specification packages release; hashes and historical artifacts are
unaffected.

## Package and naming model

The repository is a monorepo of independently versioned packages. Package
boundaries follow responsibility and framework, not implementation language.

| Responsibility | Distribution | Public import/package path | Timing |
| --- | --- | --- | --- |
| Specification and document utilities | `agent-topology-spec` on PyPI | `agent_topology.spec` | Python foundation |
| Python LangGraph producer | `agent-topology-langgraph` on PyPI | `agent_topology.langgraph` | First producer |
| Specification for JavaScript consumers | `@agent-topology/spec` on npm | `@agent-topology/spec` | TypeScript expansion |
| LangGraph.js producer | `@agent-topology/langgraph` on npm | `@agent-topology/langgraph` | TypeScript expansion |

PyPI distribution names are globally unique installation identifiers. The
`agent_topology` namespace package is the Python equivalent of the npm
`@agent-topology` scope and keeps daily imports short and structured.

`agt` is the command name:

```bash
agt describe ./graph.py:graph --out topology.json
```

For Foundation, `agent-topology-langgraph` alone publishes the `agt` executable
and dispatches `describe` directly to its producer. Installing
`agent-topology-spec` alone does not expose `agt`, and no plugin or producer
discovery mechanism is part of the CLI. Future producer packages may coexist as
imports but must not publish a colliding `agt` console script.

`agt diff` is classified as a future producer-neutral document-consumer command
and remains outside Foundation. Scheduling it, or requiring one command to
select among multiple installed producers, triggers migration of the executable
to a dedicated CLI distribution rather than adding producer-neutral dispatch to
the LangGraph package. See ADR 0007.

## Dependency direction

```text
schema + canonical document model
              ▲
              │
language package for the specification
              ▲
              │
framework producer ─────► framework runtime

consumer ───────────────► schema/document only
conformance runner ─────► schema + shared fixtures + producer under test
```

A dependency in the reverse direction is an architecture violation: the spec
must not import a producer, and a document consumer must not require LangGraph.

## Repository shape

The repository uses these logical areas:

```text
spec/                    canonical schema and document validation cases
packages/
  python/
    spec/                agent-topology-spec
    langgraph/           agent-topology-langgraph
  typescript/
    spec/                @agent-topology/spec
    langgraph/           @agent-topology/langgraph
conformance/             shared cases and producer runners
docs/                    user guides, references, and maintainer documentation
docs/decisions/          accepted architectural decisions and router
```

Canonical fixtures must have one source of truth. Packaging may include or copy
them at build time, but checked-in duplicates must not become independent
authorities.

## Change rules

Before changing the core document, ask whether a framework with no declared edge
list could emit the proposed field. If not, prefer a framework extension. A
field should move into core only with evidence from multiple producers, not
because it is convenient for the first one.

A canonicalisation change requires a new hash algorithm version only when it
can alter the byte output of the version-1 hash projection, or when the set
of hashed structural properties changes; see
[ADR 0009](docs/decisions/0009-numeric-canonical-form.md) for the numeric
case. Changes to the document contract require a format-version decision.
Package releases follow their own versions and do not imply either.

Use [the decision router](docs/decisions/DECISIONS.md) to find the ADR governing
a change. If no accepted decision covers a material architectural choice, write
an ADR before implementation.

## Open architectural questions

- The first structurally different framework used to test the v0 core boundary.

This is intentionally not settled here; `ARCHITECTURE.md` records accepted
architecture and visible seams, while ADRs own new choices and rationale.
