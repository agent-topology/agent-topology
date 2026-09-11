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
- Vendor neutrality is provisional while only one framework model is observed.

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

Changes to canonicalisation or hashed structural properties require a new hash
algorithm version. Changes to the document contract require a format-version
decision. Package releases follow their own versions and do not imply either.

Use [the decision router](docs/decisions/DECISIONS.md) to find the ADR governing
a change. If no accepted decision covers a material architectural choice, write
an ADR before implementation.

## Open architectural questions

- The first structurally different framework used to test the v0 core boundary.

This is intentionally not settled here; `ARCHITECTURE.md` records accepted
architecture and visible seams, while ADRs own new choices and rationale.
