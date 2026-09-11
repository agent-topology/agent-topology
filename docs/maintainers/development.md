# Local development

[Documentation home](../README.md) · [Contributing](../../CONTRIBUTING.md)

Use a source checkout to work on unreleased fixes. Install `uv`, a supported Python
runtime, and Node.js with npm. Run these commands from the repository root.
The pinned tools and full policy are in [CONVENTIONS.md](../../CONVENTIONS.md).

## Python

```bash
uv run --project packages/python/spec --group test python -m pytest packages/python/spec/tests tests/test_release_tools.py tests/test_public_docs.py spec/tests
uv run --project packages/python/langgraph --group test python -m pytest packages/python/langgraph/tests tests/test_trace_correlation_example.py
uvx --from ruff==0.16.7 ruff format --check packages/python scripts tests
uvx --from ruff==0.16.7 ruff check packages/python scripts tests
```

The producer project uses the local specification through its `tool.uv.sources`
configuration. Use `uv run --project packages/python/langgraph agt ...` to exercise
the checkout's CLI.

## TypeScript

Build the specification before installing/checking the producer, which uses the
local specification as a development dependency:

```bash
npm ci --prefix packages/typescript/spec
npm --prefix packages/typescript/spec run check
npm ci --prefix packages/typescript/langgraph
npm --prefix packages/typescript/langgraph run check
node --test tests/typescript-release-tools.test.mjs
```

Keep `uv` available: TypeScript contract tests invoke Python as a cross-language
oracle. Package `check` commands include build, formatting, type checks, and tests.
Do not edit generated schema copies, `dist/`, or generated declarations.

## Evidence for a release

Passing tests in a checkout is not artifact qualification. Packaging changes also
require wheel/sdist or npm tarball inspection and clean-install smoke tests. The
[release guide](../releasing.md) defines the protected workflows and receipts that
bind artifacts to a clean source commit.

Each package has its own version. Put fixes in the changelog's Unreleased section
until a new artifact is qualified. Never replace an already published beta artifact
with rebuilt bytes under the same version.

See the [decision router](../decisions/DECISIONS.md) before changing the contract,
completeness model, hash semantics, CLI ownership, or package boundaries.
