# Changelog

This file records user-visible changes to the independently versioned
`agent-topology` packages. Package versions do not version the document format or
the structure-hash algorithm, and repository membership does not promise that
future package versions will move together.

## v0.1.0-beta.1 public preview — unreleased

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

`agent-topology-spec==0.1.0b1` and `agent-topology-langgraph==0.1.0b1` are now
available from PyPI. The two npm packages remain pending, so the coordinated public
preview is still unreleased.
