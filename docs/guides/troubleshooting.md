# Troubleshooting

See the [beta.1 to beta.2 upgrade guide](../guides/upgrading-beta.2.md) for candidate
package selections, hash baselines, and expanded-subgraph migration, and the
[beta.2 to beta.3 upgrade guide](../guides/upgrading-beta.3.md) for the current
published release, and the
[beta.3 to beta.4 upgrade guide](../guides/upgrading-beta.4.md) for the
current, unpublished candidate.

[Documentation home](../README.md) · [CLI exit codes](../reference/cli.md)

## `agt` is not found

Activate the environment where you installed `agent-topology-langgraph` and run
`python -m pip show agent-topology-langgraph`. Installing only the specification
or either npm package does not install `agt`.

## ESM installation errors

Both npm packages are ESM-only on Node.js 20+. An installation can succeed while
`require("@agent-topology/spec")` or `require("@agent-topology/langgraph")` fails
with `ERR_PACKAGE_PATH_NOT_EXPORTED` (often `No "exports" main defined`).
Their public root has an `import` condition and no `require` condition: this is a
module-format mismatch, not evidence of a missing installation. Synchronous
`require()` is unsupported, including on newer Node versions that can load some
other ESM packages through `require()`.

Use the [quickstart's `graph.mjs`](../getting-started/typescript.md#export-a-graph)
with `node graph.mjs`, or use `.js` with `"type": "module"` in your application's
`package.json`. If your application must remain CommonJS, follow the
[complete `graph.cjs` example](../getting-started/typescript.md#use-it-from-commonjs):
await `import()` and then await `describe()` inside an async function, with a
catch that reports failure and sets `process.exitCode = 1`.

The same exports error can also mean an unsupported deep import such as
`@agent-topology/spec/dist/validation.js`. Import named APIs from the package root;
do not bypass exports through `dist`, edit the installed package metadata, or look
for a default export. `Cannot use import statement outside a module` usually means
static ESM syntax was placed in a CommonJS file; the `.mjs` or async `import()`
paths above address that mismatch too.

Check `node --version` and `npm ls @agent-topology/spec @agent-topology/langgraph`
in the application's directory. Install the specification peer explicitly when
using the producer. The producer has LangGraph.js 1.4.14 as a runtime dependency;
the specification has Ajv and ajv-formats runtime dependencies and no framework
dependency. For document-only use, install just the specification and follow the
[consumer guide](consuming-documents.md).

## Unsupported framework version

Check `python -m pip show langgraph` or `npm ls @langchain/langgraph` in the running
application's environment. Install one of the [tested versions](../reference/compatibility.md).
Do not edit a compatibility manifest to silence the error: it protects extraction
from framework changes for which there is no conformance evidence.

## CLI import or target error

Use `graph.py:graph`, where `graph` is the result of `StateGraph.compile()` assigned
at module level. Install your application's dependencies in the same environment.
If the file uses package-relative imports, expose its compiled object through a
small wrapper that uses your application's absolute import path.

The CLI omits underlying import exception text from its diagnostic. Inspect the
trusted module directly in your development environment to find the cause. Be aware
that running the file as a script can also execute its main block.

## Strict mode fails but writes a file

This is intentional. Status `6` means the output records graph-specific gaps.
Find `completeness.gaps[].element` and read the corresponding message. For an
`unknown-routing-targets` gap, declare the real destinations in the framework
(for example, with a conditional-edge path map) if they are known. Otherwise
preserve the unknown; do not invent edges or delete the gap.

## Completeness is `complete` but limitations are present

These are different signals. A limitation describes a category the producer cannot
observe in any graph; a gap describes an unknown in this graph. Display both.
Completeness does not prove policy compliance, path coverage, or runtime behavior.

## Repeated exports differ

`provenance.generatedAt` changes on every extraction. Compare the full
`structureHash` descriptor for structural differences and inspect completeness
separately. Labels, extensions, and node implementation code are not part of the
structure hash.

The initial npm beta.1 has a known Unicode-ordering defect for some structural
identifier lists and generated join IDs. Current source corrects it to match the
Python implementation. Existing affected hashes may change with the fix; see
[Unreleased changes](../../CHANGELOG.md#unreleased).

## Expanded subgraphs are surprising

Use `depth=0` / `{ depth: 0 }` to keep subgraphs opaque. At positive depth,
current source retains each parent node's own id and materializes its confirmed
compiled children as separate `graphs[]` entries addressed by `subgraphId`,
instead of flattening them into the root graph — see
[ADR 0012](../decisions/0012-nested-graph-identity-traversal-and-compatibility.md).
A materialized child's own `branch`, `sentinel`, and `entry` interpretation
facts are populated from that child's own declarations, under the same rules
as any root graph — see [ADR 0012](../decisions/0012-nested-graph-identity-traversal-and-compatibility.md)'s
revision `"2"` `materialized-child` fact. Deep traversal can also fail in the
framework.

This correction is unreleased; the original beta.1–beta.3 releases instead
flattened expanded scope into the root graph and recorded an
`expanded-subgraph-metadata` gap for it.

## Validation succeeds but the hash is wrong

Validation checks shape and references, not the stored digest. Follow the
[consumer guide](consuming-documents.md) to recompute and compare it before using
the document as structural-change evidence.

## Ask for help

Use GitHub Issues for ordinary support. Include package and framework versions,
runtime version, the command or API call, and a minimal graph reproducing the
problem. Remove credentials and sensitive graph metadata. For vulnerabilities,
follow the [private reporting policy](../../SECURITY.md).
