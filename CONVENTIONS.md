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
- Python comes first. The TypeScript specification package follows the stabilised
  Python contract; the LangGraph.js producer remains an independently versioned
  package under ADR 0006.

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
- change the hash algorithm version when a canonicalisation change can alter
  the version-1 hash projection's byte output, or when the set of hashed
  structural properties changes (see
  [ADR 0009](docs/decisions/0009-numeric-canonical-form.md) for the numeric
  case);
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

### Python toolchain

Python distributions use Hatchling 1.32.0 and support Python 3.11 through 3.14.
Each distribution owns its own `pyproject.toml`, source root, dependency group,
and build artifact. The repository uses Ruff 0.16.7 for Python formatting and
linting and pytest 9.1.1 for tests.

Run the package checks independently:

```bash
uv build packages/python/spec --out-dir dist/spec --clear
uv build packages/python/langgraph --out-dir dist/langgraph --clear
uv run --project packages/python/spec --group test pytest packages/python/spec/tests
uv run --project packages/python/langgraph --group test pytest packages/python/langgraph/tests
uv run --project packages/python/spec --group test python -m pytest tests/test_release_tools.py tests/test_public_docs.py
uvx --from ruff==0.16.7 ruff format --check packages/python
uvx --from ruff==0.16.7 ruff check packages/python scripts tests
```

CI builds and inspects each wheel and source distribution independently, then
installs both archive formats in clean environments and proves that the two native
`agent_topology` namespace portions coexist. The LangGraph compatibility workflow
derives its version matrix from `_compatibility.json`; package metadata and this
matrix must not be maintained as separate compatibility claims.

Python releases run through `release-python.yml`. A manual run selects exactly one
of `spec` or `langgraph` and supplies that distribution's PEP 440 version. Leave the
`publish` input false to exercise the complete release path without contacting
PyPI. Publishing uses a package-specific protected GitHub environment and PyPI
Trusted Publishing. The publish job accepts only artifacts accompanied by the
release receipt produced after the selected package's tests, quality checks,
artifact inspection, clean installation, namespace-coexistence check, and (for the
producer) supported-range conformance. The receipt binds those checks to the exact
commit, package, version, filenames, and SHA-256 digests; both authorization and
publication refuse a dirty checkout.

The Python packages are native portions of the `agent_topology` namespace.
Never add `packages/python/*/src/agent_topology/__init__.py`.

### TypeScript toolchain

The `@agent-topology/spec` and `@agent-topology/langgraph` packages support Node.js
20 and later and use TypeScript 7.0.2. The specification validates the canonical
Draft 2020-12 schema with Ajv 8.20.0; its build generates public document types from
the root schema and copies that schema into build output. Generated files are not
checked-in authorities. The producer targets only LangGraph.js releases listed in
its compatibility manifest; the initial exact release is 1.4.14.

Run its checks and build its independently installable tarball from the package:

```bash
npm --prefix packages/typescript/spec run check
npm --prefix packages/typescript/langgraph run check
npm pack ./packages/typescript/spec
npm pack ./packages/typescript/langgraph
```

CI packs and inspects both npm packages independently, installs the specification
alone, installs the producer against its specification peer, and proves that both
public APIs coexist in one clean project. `@agent-topology/langgraph` declares the
tested LangGraph.js release as a runtime dependency and its compatible
`@agent-topology/spec` release as a peer dependency; the local file reference is a
development-only dependency and is never the published compatibility contract.

TypeScript releases run through `release-npm.yml`. A manual run selects exactly one
of `spec` or `langgraph`, supplies that package's SemVer version, and supplies the
compatible specification version when releasing the producer. Leave `publish` false
to exercise the complete qualification path without contacting npm. The qualification
receipt binds the checks to the exact commit, package, version, tarball filename, and
SHA-256 digest. Publishing additionally requires the protected `npm-public-preview`
GitHub environment and revalidates the clean checkout and receipt before npm trusted
publication with provenance.

## Documentation and decisions

User guides and references start at `docs/README.md`. Follow
`docs/maintainers/documentation.md` for navigation, executable examples, and
relative-link conventions. Package-local `LICENSE` files reproduce the root
notice for independently distributed artifacts; the public documentation guard
checks byte equality, and artifact inspection checks the packaged notice.

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

From beta.2 onward, release preparation and stabilization use
`rc/<version>` (for example `rc/0.1.0-beta.2`). Package-version changes,
release notes, and candidate fixes are reviewed against that branch; publication
is dispatched from it after CI passes. Keep main as the integration line and
bring release corrections back through a PR. Tags name immutable qualified
commits. See [the RC branch policy](docs/releasing.md#release-candidate-branches-and-immutable-tags).

Use `docs/ISSUE-PLANNING.md` for the Milestone → Epic → Feature → Task model.
Every Feature and Task has one native parent issue, while blocked-by relationships
express execution dependencies rather than hierarchy.

Implementation starts through `resolve-issue <NUMBER>` on a
`workbench/<NUMBER>-<slug>` branch. Until a pull request exists, every commit on
that branch has exactly `wip: #<NUMBER>` as its subject, with no body or trailers.
The repository's `ghpr` workflow owns creation of the final commit message and
pull request. Use `review-pr <NUMBER>` for the final pre-merge review.

Immediately before implementing a Feature, run
`determine-feature <FEATURE_NUMBER>`. A decision-complete Feature that fits one
reviewable pull request remains the leaf work item. A broader Feature is split
into the minimum native Task sub-issues, and `resolve-issue` runs on those Task
leaves instead.

Pull requests normally close Tasks or Bugs. A Feature may be closed by a pull
request only when it is already one bounded, independently reviewable change.
Closing all children triggers review of the parent outcome; it does not prove
that outcome automatically.
