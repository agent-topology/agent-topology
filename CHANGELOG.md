# Changelog

This file records user-visible changes to the independently versioned
`agent-topology` packages. Package versions do not version the document format or
the structure-hash algorithm, and repository membership does not promise that
future package versions will move together.

## Unreleased

- Fix both LangGraph producers emitting invalid, duplicate join identities:
  reversed, permuted, or repeated `add_edge(sources, target)` declarations of
  the same source set now collapse into one join instead of colliding, and a
  source id's own `+`/`\` characters can no longer forge a collision with a
  differently-grouped source set. No structure-hash algorithm version change;
  every existing valid fixture's join id and hash are unaffected. See
  [ADR 0015](docs/decisions/0015-join-identity-deduplication-and-unambiguous-encoding.md).
- Add a machine-readable release-state record and phase-specific documentation
  checks so artifact qualification cannot be mistaken for a completed public
  release.
- Require a separate post-publication closeout before a draft GitHub prerelease
  becomes public, and automatically reopen release issues closed as completed with
  missing acceptance criteria.
- Publish the [LangGraph version-range expansion
  policy](docs/reference/langgraph-version-policy.md): the seven-day review
  cadence for new stable releases, the exact evidence required before a
  version is added, the RC freeze rule, and where consumers can see pending
  qualification work.

## v0.1.0-beta.4 public preview — 2026-09-15

Prepared on `rc/0.1.0-beta.4`: Python distributions use `0.1.0b4`, npm
packages use `0.1.0-beta.4`, and the npm producer's spec peer uses beta.4.
All four registry packages, the immutable tag, the GitHub prerelease, and live
installation documentation identify the published and verified beta.4 release. See the
[release notes](docs/releases/v0.1.0-beta.4.md) and the
[beta.3 to beta.4 upgrade guide](docs/guides/upgrading-beta.4.md).

- The Python CLI exposes the `describe` API's traversal depth through
  `agt describe --depth N`, defaulting to `0` (backward compatible, opaque
  children) and accepting only non-negative integers; an invalid, missing, or
  negative value is a usage error (status `2`). `agt describe` output at a given
  depth is equivalent to calling the Python API with the same `depth`, including
  `--strict` status `6` for an actual graph-specific gap. The CLI still only
  imports and describes a module-level compiled-object target; it does not
  invoke the graph or call a factory to build one. See
  [ADR 0007](docs/decisions/0007-langgraph-owns-the-foundation-cli.md) and the
  [CLI reference](docs/reference/cli.md).
- Both LangGraph producers retain a confirmed compiled child's parent node under
  its own id at every depth instead of flattening it away. Within the requested
  `depth` budget, the parent node additionally gains a core `subgraphId`
  addressing the child as its own first-class `graphs[]` entry, deterministically
  derived as `parentGraphId:parentNodeId`; a derived id that would collide with an
  existing graph id is never emitted, and the node stays opaque with a new
  `child-graph-id-collision` gap instead. `depth = N` now materializes levels
  `1..N`; level `N`'s own children keep the unchanged depth-0 opaque-child
  contract, and depth-0 output remains byte-identical to today's.
  `expanded-subgraph-metadata` is retired: it can no longer be emitted. See
  [ADR 0012](docs/decisions/0012-nested-graph-identity-traversal-and-compatibility.md).
- Both LangGraph producers now populate `branch`, `sentinel`, and `entry`
  experimental interpretation facts for a materialized child's own nodes, using
  the same [ADR 0008](docs/decisions/0008-experimental-consumer-interpretation.md)
  evidence rules already used for a root graph — a materialized child is not a
  degraded view. `x-topology-interpretation` advances to revision `"2"` on any
  graph that materializes at least one child, adding a `subgraph` value of
  `materialized-child` (evidence kind `materialized-subgraph-reference`,
  referencing the containing `graphs[].id` and the node's `subgraphId`).
  `opaque-child` is invalid on any node carrying core `subgraphId`, and
  `materialized-child` is invalid without one. Depth-0 documents and any
  document with no materialized node continue to use revision `"1"` unchanged.
  See [ADR 0012](docs/decisions/0012-nested-graph-identity-traversal-and-compatibility.md).

## v0.1.0-beta.3 public preview — 2026-09-12

Prepared on `rc/0.1.0-beta.3`: Python distributions use `0.1.0b3`, npm
packages use `0.1.0-beta.3`, and the npm producer's spec peer uses beta.3.
All four registry packages, the immutable tag, the GitHub prerelease, and live
installation documentation identify the published and verified beta.3 release. See the
[release notes](docs/releases/v0.1.0-beta.3.md) and the
[beta.2 to beta.3 upgrade guide](docs/guides/upgrading-beta.3.md).

- Both specification packages explicitly test rejection of duplicate graph ids, and
  both LangGraph producers now accept a caller-supplied document-local graph id.
  Derived gap references follow the selected id; `main` remains the default. The
  Python CLI exposes the same choice through `--graph-id`. Graph authors continue to
  control the independent display name through `StateGraph.compile(name=...)`. See
  [ADR 0011](docs/decisions/0011-document-local-consumer-addressable-graph-ids.md).

- Both specification packages now spell `x-*` extension numbers per
  [ADR 0009](docs/decisions/0009-numeric-canonical-form.md)'s byte oracle
  instead of each runtime's default float formatting: `agent_topology.spec`
  no longer emits Python's `repr(float)` spelling (`0.0` for a document that
  should read `0`), and both packages narrow a bare JSON integer literal
  beyond magnitude `2^53` to its nearest `binary64` double, identically in
  both languages, per [ADR 0010](docs/decisions/0010-numeric-domain-parsed-value-narrowing.md).
  `structureHash` is unaffected; no core field is numeric. See the
  [contract's numeric canonical form section](docs/0.1-contract.md#numeric-canonical-form).

- Both LangGraph producers distinguish observed roots from confirmed execution
  entries with experimental revision 1 `entry` facts. START alone is confirmed;
  candidate uncertainty stays local without changing entry arrays, routing gaps
  or core hashes. See the [migration guide](docs/guides/consuming-documents.md#experimental-entry-interpretation).

- Both LangGraph producers emit experimental revision 1 sentinel roles from
  framework-owned identity and positive user-node membership. Unmapped expanded
  nodes remain unknown; nodes, connections, joins, gaps and core hashes are
  preserved. See the [consumer guide](docs/guides/consuming-documents.md#experimental-sentinel-roles).

- Both LangGraph producers emit experimental revision 1 branch interpretation
  from inspected declarations. Direct fan-out can be `all-declared`; conditional
  and dynamic routing remain unknown, as do unmapped expanded child branches.
  Core structure, hashes, completeness, and strict behavior are preserved.
  See the [consumer guide](docs/guides/consuming-documents.md#experimental-branch-interpretation).

- Documented the explicit boundary between ordinary-edge connectivity and
  first-trigger/once-only/reset firing policy at a multi-connection target: no
  convergence firing-policy fact is added by experimental interpretation
  revision 1, and this is not an OR-convergence implementation. See the
  [contract's known limitations](docs/0.1-contract.md#known-limitations-and-excluded-consumers)
  and the [consumer guide's OR convergence section](docs/guides/consuming-documents.md#or-convergence-and-first-trigger-firing).

## v0.1.0-beta.2 public preview — 2026-09-11

Prepared on `rc/0.1.0-beta.2`: Python distributions use `0.1.0b2`, npm
packages use `0.1.0-beta.2`, and the npm producer's spec peer uses beta.2.
All four packages are published and verified. See the
[release notes](docs/releases/v0.1.0-beta.2.md).

- Run package CI on `rc/**` as well as main. Release dispatches require a
  RC branch and versions matching the prepared source manifests; the npm
  producer also requires its prepared specification peer.

- Both LangGraph producers now record an `expanded-subgraph-metadata` gap when
  traversal expands child nodes whose join, routing, and interrupt declarations
  are not fully inspected. Python strict extraction rejects that incomplete view
  and retains the document in the exception. Opaque traversal and positive-depth
  traversal without expanded children retain their existing completeness behavior.
  This fixes a false claim of completeness without changing the document schema
  or hash projection.

- Correct Unicode code-point ordering in the TypeScript specification's join
  sources and entry/exit identifiers, and in LangGraph.js join IDs and gap order.
  The original beta.1 used UTF-16 order in those places, disagreeing with Python
  for some non-BMP identifiers. Affected canonical output and hashes change to
  match the existing Python contract; ASCII fixtures are unchanged. This repairs
  implementation parity, not the format or hash projection, so their versions
  remain `0.1` and `1`. The fix requires new versions of both affected npm packages.
- Pass Python release dispatch inputs as quoted environment-variable data rather
  than interpolating them into shell commands.
- Include the MIT notice in all four package artifacts, and add Python package
  README descriptions and documentation/repository links. Artifact inspection
  verifies the license text; source checks keep package notices aligned with the
  repository license. These packaging changes require a new release of each package.
- Add user documentation under `docs/`: executable Python/JavaScript quickstarts,
  consumer examples, concepts, API/CLI references, troubleshooting, and maintainer
  guides. Correct stale publication claims and the architecture's CLI example.
- Expand local documentation link checks and execute quickstart and consumer
  snippets in the producer test suites.

These changes are part of beta.2 and are not part of the immutable beta.1
registry artifacts. Qualification, publication and public-install evidence are
recorded in the beta.2 release notes.

## v0.1.0-beta.1 public preview — 2026-09-11

The initial public preview provides:

- the provisional v0.1 topology document contract and canonical utilities in
  `agent-topology-spec` and `@agent-topology/spec`;
- synchronous Python and asynchronous TypeScript producers for compiled LangGraph
  graphs in `agent-topology-langgraph` and `@agent-topology/langgraph`;
- the Python-owned `agt describe` command; and
- a deterministic topology-to-trace correlation example.

The core has been exercised by two implementations of the LangGraph model, not by
a structurally different framework. It is therefore not vendor-neutral or a stable
v1 contract. See the [0.1 contract](docs/0.1-contract.md) and the
[known limitations](README.md#known-limits) before adopting it.

The first beta uses Python version `0.1.0b1` and npm version `0.1.0-beta.1`.
The four packages are published independently. A release can be partially available
while that sequence is in progress; the coordinated GitHub release and announcement
are withheld until all four registry artifacts pass clean-install and provenance
verification. Maintainers follow the
[release and partial-publication recovery guide](docs/releasing.md). Public support
is best-effort through GitHub Issues, with security reports handled through the
private channel described in [SECURITY.md](SECURITY.md).

All four packages are available from their public registries and passed clean-install,
public-API, provenance, and integrity reconciliation. The coordinated tag, package
source commits, artifact digests, compatibility ranges, and verified commands are in
the [v0.1.0-beta.1 release notes](docs/releases/v0.1.0-beta.1.md).
