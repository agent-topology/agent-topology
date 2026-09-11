# Release-readiness review — 2026-09-11

[Documentation home](../README.md) · [Changelog](../../CHANGELOG.md)

The review covered the working tree based on commit
`0e127d84d77904dd0a909fab0ea58862282ceae8`: both specification implementations,
both LangGraph producers, the Python CLI, shared conformance, release guards,
artifact contents, and public documentation. The findings below were corrected
in source. They are not corrections to the already published beta.1 artifacts.

## Findings and changes

| Finding | User impact | Correction and evidence |
| --- | --- | --- |
| Expanded child graphs could be marked complete although child declarations were not fully inspected | Consumers and Python strict mode could accept an incomplete expanded view | Both producers emit an `expanded-subgraph-metadata` gap on the containing graph. Tests cover opaque versus expanded views, strict rejection, and positive depth without expanded children. |
| TypeScript used UTF-16 ordering for some structural lists and generated join IDs | Non-BMP identifiers could yield different canonical bytes and hashes from Python | Use the existing Unicode code-point comparator for join sources, entry/exit IDs, join identity, and router-gap ordering. A two-identifier cross-language case and a minimal producer join reproduce the original failures and pass after correction. |
| Distribution artifacts omitted the MIT license notice | Independently installed packages did not carry the repository's permission notice | Include a package-local copy in all four distributions. Tests compare copies with the root, and wheel/sdist/npm inspectors verify packaged license text. |
| Python distributions had no package README description or project links | Registry users had little guidance after discovering a package | Add package-specific README files and documentation, repository, and issue URLs in distribution metadata. Wheel inspection requires a Markdown description; sdist inspection requires the README. |
| Python release workflow interpolated dispatch input directly into shell source | Release input handling depended on prior validation and shell quoting | Pass values through environment variables and quoted shell arguments. A workflow guard checks both release workflows for direct dispatch-input interpolation in `run` blocks. This is hardening; no exploitability claim is made. |
| Architecture, contract, and schema guide disagreed with release history | Readers were told packages were unpublished or shown a non-working command | Align current guides with recorded publication history, correct `graph.py:graph`, and keep `agt diff` explicitly deferred. Historical ADR context and release receipts remain historical. |
| Documentation had no beginner path and link checking covered only six pages | New users had to infer graph construction and consumer behavior from fragments | Add a documentation home, runnable quickstarts, concepts, consumer guides, references, troubleshooting, and maintainer guidance. Check local links throughout docs and execute quickstart/consumer code from Markdown in producer tests. |

The schema and hash projection are unchanged. Unicode ordering repairs the
TypeScript implementation's agreement with the existing Python contract. The
expanded-subgraph correction changes completeness, which is excluded from the
structure hash. Consumers must inspect completeness separately even when hashes
match.

## Verification

Local verification used macOS, Python 3.11.16 for specification/repository tests,
Python 3.14.7 for producer tests, Python 3.12.14 for clean Python artifact installs,
and Node.js 22.16.0 for TypeScript checks.

- Python specification, schema, release guards, documentation guards, producer,
  CLI, and trace-correlation tests.
- Python LangGraph conformance and producer checks on both supported framework
  releases, 1.2.10 and 1.2.11.
- Both npm package `check` commands: build, format, type checking, shared
  conformance, Python parity, producer behavior, and executable documentation.
- Node release-tool tests and repository Python/TypeScript formatting and linting.
- Independent builds and inspection of both Python wheels and source distributions
  and both npm tarballs, including license notices and package metadata.
- Clean installation of Python wheel and sdist artifacts, specification-only
  imports followed by producer/API/CLI and namespace-coexistence smoke checks.
- Clean npm specification-only, producer-with-peer, and coexistence import smoke
  checks against the packed tarballs.
- Local Markdown targets/fragments and Git whitespace checks.

The repeatable checkout commands are in [local development](../maintainers/development.md).
The complete runtime matrix, protected release authorization, and registry
publication are separate CI/release operations; this local review did not run
those remote workflows or publish packages.

## Remaining boundaries

Expanded child metadata is now reported as unknown, not recursively reconstructed.
Describe a compiled child separately when its joins, routers, or interrupts matter.
Deep drawable traversal may still raise a framework error. The project still does
not promise vendor neutrality, policy verdicts, path coverage, or observation of
runtime-only behavior. These boundaries are documented in the
[concepts guide](../guides/concepts.md) and [0.1 contract](../0.1-contract.md).

The working tree retains the initial beta package version numbers. New immutable
versions of all four packages are required before distributing these changes,
including the specification peer selection for the npm producer. Qualify them from
the final clean release commit using the [release guide](../releasing.md). Local
review builds under beta.1 are test artifacts only and must not replace the
published files or their recorded integrity values.

The documentation is organized for future rendering, but no wiki, static-site
generator, S3 bucket, or CloudFront distribution was created. Follow the
[documentation maintenance guide](../maintainers/documentation.md) when choosing
hosting, URL rewriting, versioned pages, and publication automation.
