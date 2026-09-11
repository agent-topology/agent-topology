# Contributing to agent-topology

Thank you for helping improve the 0.1 public preview. The contract is provisional:
changes should preserve honest uncertainty and avoid presenting the current
LangGraph-shaped evidence as vendor neutrality or v1 stability.

## Before opening a change

- Use GitHub Issues for reproducible bugs, compatibility evidence, and focused
  proposals. Public support is best-effort; the project makes no response-time or
  long-term-support commitment.
- Report suspected vulnerabilities privately as described in
  [SECURITY.md](SECURITY.md), not in a public issue.
- Read [ARCHITECTURE.md](ARCHITECTURE.md), [CONVENTIONS.md](CONVENTIONS.md), and the
  [decision router](docs/decisions/DECISIONS.md). A material boundary change needs
  an ADR rather than an undocumented convention.

Keep fixtures to the minimum graph that measures one contract behavior. Core fields
must remain framework-neutral in shape; producer-specific facts belong under a
namespaced `x-*` extension. Tests must preserve the distinction between producer
limitations and graph-specific gaps, as well as canonical output and hashing.

## Development checks

The authoritative commands and pinned tool versions live in
[CONVENTIONS.md](CONVENTIONS.md#tests-and-conformance). Run the checks for every
package you change. Changes to packaging, compatibility, or release behavior also
require artifact inspection and clean-install smoke tests.

Pull requests should explain the observable change, its verification, and any
compatibility impact. By contributing, you agree that your contribution is licensed
under the repository's [MIT License](LICENSE).

## Releases

The four packages are independently versioned and published. Do not infer a package
version from the topology format, the hash algorithm, or another package. Maintainers
must use the protected workflows and follow the
[release and partial-publication recovery guide](docs/releasing.md); publishing one
artifact is not authority to announce the coordinated preview.
