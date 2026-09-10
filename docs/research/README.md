# Research catalog

This directory records the evidence used to implement and maintain framework
producers. It exists so that a producer change starts from a known framework
version, the matching upstream source, and repeatable observations instead of
memory or rolling documentation alone.

The catalog is development evidence. It is not part of the agent-topology
document, a framework registry, or a substitute for an accepted architecture
decision. When evidence and an accepted ADR disagree, the ADR remains
authoritative until it is superseded.

## Contents

- `catalog.yaml` is the machine-readable index, grouped by framework,
  implementation language, and exact release.
- `frameworks/<framework>/<language>/<version>/` holds a version dossier and
  its minimum probes. Python and TypeScript versions are independent.
- `search/python_catalog.py` and `search/typescript_catalog.ts` are small,
  non-authoritative navigation adapters because graft 0.16 indexes supported
  code files but not Markdown or YAML. They expose search vocabulary and point
  back to the canonical catalog and dossiers.
- `probes/` directories hold minimum executable inputs that verify one
  introspection claim each. Probes are research evidence; conformance fixtures
  remain the product-level compatibility boundary.

## Evidence rules

Use evidence in this order:

1. behaviour observed by a minimum probe against the exact pinned package;
2. source at the exact release commit;
3. version-labelled official API reference;
4. rolling official guides;
5. an explicit, unresolved research question.

Do not copy whole upstream manuals into this repository. Record the relevant
URL, release or commit, symbol, finding, and the local probe or fixture that can
revalidate it. This keeps the catalog searchable without turning a changing
documentation site into an unaudited vendored snapshot.

## Verification states

- `verified`: reproduced by a checked-in minimum probe on the exact version.
- `source-verified`: confirmed in source at the recorded release commit but not
  yet reproduced by a checked-in probe.
- `documented`: stated by version-labelled official documentation but not yet
  checked against source or behaviour.
- `pending`: a research question or proposed surface with no sufficient
  evidence yet.

Only `verified` versions may be added to a producer's supported range. A
baseline version can remain narrower than the upstream semantic-versioning
range, as required by [ADR 0003](../decisions/0003-canonical-ordering-and-versioned-structure-hash.md).

## Updating the catalog

For a new framework implementation version:

1. resolve the release tag to an immutable commit;
2. record the package metadata and version-labelled official references;
3. inspect only the source surfaces needed by the producer;
4. run or add one minimum probe per topology behaviour;
5. connect each finding to a conformance fixture where applicable;
6. update `catalog.yaml` and the version dossier;
7. run `graft build` so the new evidence is searchable.

Rolling documentation must be marked as rolling. A page that currently
describes the baseline version is not assumed to remain a snapshot of it.

After changing a catalog entry, update its short record in the matching
`search/` adapter when the searchable concept or symbol changed. Do not copy
URLs or detailed evidence into adapters; `catalog.yaml` remains the single
structured authority. Never promote a finding from one implementation language
to another without independent evidence.
