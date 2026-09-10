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
| Monorepo/package boundaries, Python versus TypeScript, independent releases, published names/imports, or the `agt` command name | [ADR 0006](0006-repository-layout-and-language-boundaries.md) |

For a change spanning several rows, read every routed ADR. Common paths are:

- document-model change: 0001 → 0002 → 0003 → 0005
- new producer: 0001 → 0002 → 0005 → 0006
- renderer or visual consumer: 0001 → 0002 → 0004
- packaging or release automation: 0003 → 0006

## Decision index

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-scope-topology-extraction-and-trace-correlation.md) | Accepted | Limit the core to topology extraction, honest uncertainty, and trace correlation as the first intended use. |
| [0002](0002-record-what-could-not-be-observed.md) | Accepted | Separate producer-wide limitations from graph-specific, element-local gaps. |
| [0003](0003-canonical-ordering-and-versioned-structure-hash.md) | Accepted | Canonicalise output and use a versioned structural hash that distinguishes multi-source joins. |
| [0004](0004-rendering-is-not-part-of-the-core-document.md) | Accepted | Keep rendering outside the core document and conformance contract. |
| [0005](0005-vendor-neutrality-is-provisional-at-v0.md) | Accepted | Treat the core as provisional until a structurally different framework tests it. |
| [0006](0006-repository-layout-and-language-boundaries.md) | Accepted | Use independently versioned, framework-named packages with explicit published names and `agt` as the short CLI name. |

## Adding or changing a decision

1. Create the next zero-padded file: `NNNN-short-kebab-title.md`.
2. Record at least `Status`, `Date`, `Context`, `Decision`, and `Consequences`.
3. Link related or superseded ADRs explicitly; do not silently rewrite an
   accepted decision's rationale.
4. Add the ADR to both routing tables in this file.
5. Update `ARCHITECTURE.md` if the accepted system shape changed.

Use `Proposed`, `Accepted`, `Superseded`, or `Rejected` as status values. A
superseding ADR names the ADR it replaces, and the older ADR links back to it.
