# Architecture decision router

Start here when a change affects the document contract, package boundaries,
producer behaviour, conformance, or supported consumers. Read the routed ADR
before designing or implementing the change.

`README.md` explains the project to users. `ARCHITECTURE.md` assembles the
accepted decisions into the current system shape. The ADRs below are the
authority for why a choice was made and when it may be revisited.

## Route by question

| If the work concerns... | Read |
| --- | --- |
| Project scope, the first consumer, trace correlation, or excluded policy/coverage work | [ADR 0001](0001-scope-topology-extraction-and-trace-correlation.md) |
| Completeness, producer limitations, graph-specific gaps, strict mode, or unknown routing targets | [ADR 0002](0002-record-what-could-not-be-observed.md) |
| Stable output, canonical ordering, structure hashes, join identity, or supported framework-version ranges | [ADR 0003](0003-canonical-ordering-and-versioned-structure-hash.md) |
| Diagram data, renderers, visual output, or what conformance compares | [ADR 0004](0004-rendering-is-not-part-of-the-core-document.md) |
| Core versus `x-*` extensions, vendor neutrality, v0 status, or the evidence required from a second framework | [ADR 0005](0005-vendor-neutrality-is-provisional-at-v0.md) |
| Experimental consumer interpretation, branch selection evidence, opaque children, sentinel roles, or observed roots versus confirmed entries | [ADR 0008](0008-experimental-consumer-interpretation.md) |
| Numeric canonical byte spelling, the supported numeric domain, or whether a canonicalisation change requires a new hash algorithm version | [ADR 0009](0009-numeric-canonical-form.md) |
| Monorepo/package boundaries, Python versus TypeScript, independent releases, published names/imports, or the `agt` command name | [ADR 0006](0006-repository-layout-and-language-boundaries.md) |
| Ownership of the `agt` executable, `describe` dispatch, CLI producer discovery, command collisions, or `agt diff` ownership | [ADR 0007](0007-langgraph-owns-the-foundation-cli.md) |

For a change spanning several rows, read every routed ADR. Common paths are:

- document-model change: 0001 → 0002 → 0003 → 0005
- new producer: 0001 → 0002 → 0005 → 0006
- renderer or visual consumer: 0001 → 0002 → 0004
- packaging or release automation: 0003 → 0006
- CLI command or ownership change: 0001 → 0006 → 0007

## Decision index

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-scope-topology-extraction-and-trace-correlation.md) | Accepted | Limit the core to topology extraction, honest uncertainty, and trace correlation as the first intended use. |
| [0002](0002-record-what-could-not-be-observed.md) | Accepted | Separate producer-wide limitations from graph-specific, element-local gaps. |
| [0003](0003-canonical-ordering-and-versioned-structure-hash.md) | Accepted | Canonicalise output and use a versioned structural hash that distinguishes multi-source joins. |
| [0004](0004-rendering-is-not-part-of-the-core-document.md) | Accepted | Keep rendering outside the core document and conformance contract. |
| [0005](0005-vendor-neutrality-is-provisional-at-v0.md) | Accepted | Treat the core as provisional until a structurally different framework tests it. |
| [0006](0006-repository-layout-and-language-boundaries.md) | Accepted | Use independently versioned, framework-named packages with explicit published names and `agt` as the short CLI name. |
| [0007](0007-langgraph-owns-the-foundation-cli.md) | Accepted | Let the LangGraph distribution alone publish the Foundation `agt describe` command and defer a unified CLI until evidence requires one. |
| [0008](0008-experimental-consumer-interpretation.md) | Accepted | Define revision 1 of the experimental graph interpretation extension, independent validation, and T3–T6 implementation criteria without changing core/hash semantics. |
| [0009](0009-numeric-canonical-form.md) | Accepted | Define the canonical numeric byte spelling and its supported domain, and confirm neither requires a new hash algorithm version. |

## Adding or changing a decision

1. Create the next zero-padded file: `NNNN-short-kebab-title.md`.
2. Record at least `Status`, `Date`, `Context`, `Decision`, and `Consequences`.
3. Link related or superseded ADRs explicitly; do not silently rewrite an
   accepted decision's rationale.
4. Add the ADR to both routing tables in this file.
5. Update `ARCHITECTURE.md` if the accepted system shape changed.

Use `Proposed`, `Accepted`, `Superseded`, or `Rejected` as status values. A
superseding ADR names the ADR it replaces, and the older ADR links back to it.
