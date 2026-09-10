# Conventions

These conventions govern work in the `agent-topology` repository. They preserve
the boundaries established by the accepted architecture decisions without
prematurely choosing implementation tools.

## Authority and required context

Before a material change, read `README.md`, `ARCHITECTURE.md`, this file, and
`docs/decisions/DECISIONS.md`, then follow the router to every relevant ADR.

When documents disagree, use this order of authority:

1. accepted ADRs for the decision they govern;
2. `ARCHITECTURE.md` for the assembled system shape;
3. `CONVENTIONS.md` for repository-wide working rules;
4. `README.md` for the public introduction.

Do not use a convention or README edit to reverse an accepted architectural
decision. Propose a superseding ADR instead.

## Language

Public documentation, APIs, issue titles and bodies, release notes, and code
comments are written in English. Prefer established project terms such as
producer, consumer, limitation, gap, canonical form, and structure hash; do not
introduce synonyms for the same contract concept without a reason.

## Published names

Use the full project name for published packages and imports:

| Ecosystem | Specification | LangGraph producer |
| --- | --- | --- |
| PyPI distribution | `agent-topology-spec` | `agent-topology-langgraph` |
| Python import | `agent_topology.spec` | `agent_topology.langgraph` |
| npm package | `@agent-topology/spec` | `@agent-topology/langgraph` |

`agt` is reserved for the command-line entry point. Do not abbreviate published
or imported names.

Python distributions use the native `agent_topology` namespace. They must not
ship a shared `agent_topology/__init__.py`; each distribution owns only its
sub-package so the independently installed packages can coexist.

## Package boundaries

- The specification owns the document schema, canonical model, format version,
  hash contract, and language-neutral fixture meanings.
- The specification must not import a framework producer or framework runtime.
- A producer may depend on its framework and the specification, but producers
  do not depend on one another.
- A consumer reads the document contract and must not require producer internals
  or LangGraph.
- Canonical schemas and fixtures have one checked-in source of truth. Build-time
  packaging may copy them, but generated copies are not edited independently.
- Packages are independently versioned and released. Repository membership does
  not imply a coordinated version number.
- Python comes first. TypeScript consumers or packages remain deferred until the
  Python producer has stabilised the design described in ADR 0006.

## Public contracts and naming

JSON document fields use `camelCase`. Python identifiers use `snake_case`
except where an external framework contract requires its own spelling.
Framework-only document fields use a namespaced `x-*` key and never enter core
conformance by convenience.

Public APIs are exported deliberately from their owning sub-package. Internal
helpers use a leading underscore and are not imported across package boundaries.
The spec package must not expose LangGraph types in public annotations or return
values.

The format version, structure-hash algorithm version, and package versions are
separate axes:

- change the format version when the document contract changes;
- change the hash algorithm version when canonicalisation or hashed structural
  properties change;
- change only the affected package version for implementation or release work.

Do not infer one version from another or release the monorepo as a unit.

## Uncertainty and extensions

Producer limitations describe categories that a producer cannot observe in
principle. Graph-specific gaps identify the affected element and determine that
document's completeness. Do not turn a producer limitation into a permanent gap
or emit plausible structure when the producer could not determine it.

Before adding a core field, apply the ADR 0005 test: could a structurally
different framework without a declared edge list emit it? If evidence is
missing, keep the fact in a framework extension or write an ADR explaining why
the boundary should move.

## Tests and conformance

- A fixture is data and records one minimum graph needed to measure one contract
  behaviour. Do not enlarge input graphs to test runner mechanics.
- Every producer runner checks the same fixture meanings and expected documents.
- Producer-specific tests cover introspection and framework-version behaviour;
  they do not redefine the shared expected result.
- Ordering-sensitive declarations must prove that canonical output and hashes
  are stable under semantically equivalent declaration order.
- Multi-source joins and independent incoming edges require separate fixtures.
- Gap tests assert both the affected element and completeness behaviour.
- Test failures caused by an unsupported framework version must be explicit;
  silently accepting an untested range is not compatibility.

Choose build backends, formatters, linters, test runners, and supported runtime
versions when the first package is scaffolded. Record the selected commands here
after they exist; do not invent commands in advance.

## Documentation and decisions

The README explains user-facing purpose and limits. Architecture describes the
accepted system shape. ADRs own choices and rationale. Conventions describe how
repository work preserves those choices.

For a material architectural choice:

1. create or propose the ADR;
2. add it to both tables in the decision router;
3. update `ARCHITECTURE.md` after acceptance;
4. update public documentation only after the contract is coherent.

Do not settle a disputed architectural boundary only in an issue or pull-request
comment.

## Issues, branches, commits, and pull requests

Use `docs/ISSUE-PLANNING.md` for the Milestone → Epic → Feature → Task model.
Every Feature and Task has one native parent issue, while blocked-by relationships
express execution dependencies rather than hierarchy.

Implementation starts through `resolve-issue <NUMBER>` on a
`workbench/<NUMBER>-<slug>` branch. Until a pull request exists, every commit on
that branch has exactly `wip: #<NUMBER>` as its subject, with no body or trailers.
The repository's `ghpr` workflow owns creation of the final commit message and
pull request. Use `review-pr <NUMBER>` for the final pre-merge review.

Pull requests normally close Tasks or Bugs. A Feature may be closed by a pull
request only when it is already one bounded, independently reviewable change.
Closing all children triggers review of the parent outcome; it does not prove
that outcome automatically.
