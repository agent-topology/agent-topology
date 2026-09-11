# agent-topology documentation

Turn a compiled agent workflow into a JSON description of its nodes, connections,
joins, and known unknowns. Use that document to compare structure, build a viewer,
or relate a runtime trace to the workflow that produced it.

The library inspects a graph without invoking it. Your application still owns
graph construction and execution. The 0.1 public preview supports Python LangGraph
and LangGraph.js; the format remains provisional.

## Start here

| Your task | Read |
| --- | --- |
| Export your first Python graph, with no model or API key | [Python quickstart](getting-started/python.md) |
| Export a LangGraph.js graph in Node.js | [TypeScript / JavaScript quickstart](getting-started/typescript.md) |
| Choose a package or check framework support | [Installation and compatibility](reference/compatibility.md) |
| Understand nodes, joins, completeness, and hashes | [Concepts](guides/concepts.md) |
| Validate JSON or build a document consumer | [Consuming documents](guides/consuming-documents.md) |
| Look up function signatures and errors | [API reference](reference/api.md) |
| Automate extraction from a Python file | [CLI reference](reference/cli.md) |
| Diagnose an installation or extraction failure | [Troubleshooting](guides/troubleshooting.md) |

## Learn from a consumer

The [trace-correlation example](../examples/trace-correlation/README.md) combines a
topology with sanitized execution evidence. It distinguishes matched, unmatched,
unobserved, ambiguous, and insufficient evidence. Replay runs offline with Python's
standard library. It makes no path-coverage or policy-verdict claim.

## Contract and release history

- [0.1 contract and change policy](0.1-contract.md)
- [Schema and hash specification](../spec/README.md)
- [Shared conformance fixtures](../conformance/README.md)
- [Initial public-preview release](releases/v0.1.0-beta.1.md)
- [Beta.2 release candidate — not published](releases/v0.1.0-beta.2.md)
- [Changelog](../CHANGELOG.md)

Documentation in the default branch describes the current source. Fixes under
**Unreleased** in the changelog are not included in the pinned beta.1 registry
packages. Use a release tag when you need documentation for an exact published
artifact.

## Contribute and maintain

- [Local development](maintainers/development.md), [contributing](../CONTRIBUTING.md), and [security reporting](../SECURITY.md)
- [Architecture](../ARCHITECTURE.md), [conventions](../CONVENTIONS.md), and [architecture decisions](decisions/DECISIONS.md)
- [Package release and recovery](releasing.md)
- [Documentation maintenance and future hosting](maintainers/documentation.md)
- [Release-readiness review](reviews/2026-09-11-release-readiness.md)
- [Issue planning](ISSUE-PLANNING.md)

Research under `research/`, retrospectives under `retrospectives/`, and ADR context
sections record evidence at the time they were written. Use the guides and reference
pages for current behavior; historical plans are not installation instructions.
