# Changelog

This file records user-visible changes to the independently versioned
`agent-topology` packages. Package versions do not version the document format or
the structure-hash algorithm, and repository membership does not promise that
future package versions will move together.

## Unreleased

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
