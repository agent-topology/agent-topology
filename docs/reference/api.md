# API reference

See the [beta.1 to beta.2 upgrade guide](../guides/upgrading-beta.2.md) for beta.2
package selections, hash baselines, and expanded-subgraph migration, and the
[beta.2 to beta.3 upgrade guide](../guides/upgrading-beta.3.md) for the current
published release.

[Documentation home](../README.md) · [Compatibility](compatibility.md)

The two ecosystems share a document contract and idiomatic APIs. JSON field names
are camelCase in both; Python utility names use snake_case.

## Python producer

Import from `agent_topology.langgraph`:

```python
describe(compiled_graph, *, graph_id="main", depth=0, strict=False) -> dict
```

The input must be a `CompiledStateGraph` returned by `StateGraph.compile()`.
`graph_id` is a non-empty document-local address; choose a distinct stable value
when the output will be composed with other graphs.
`depth` is a non-negative integer; `0` leaves subgraphs opaque. `strict` must be a
boolean. The function returns a canonical document with a computed structure hash.
It inspects the graph without invoking node functions.

| Exception | Condition |
| --- | --- |
| `UnsupportedLangGraphVersionError` | Installed framework release has no conformance evidence |
| `TypeError` | Input is not a compiled state graph, graph id is not a string, depth is not an integer, or strict is not a boolean |
| `ValueError` | Graph id is empty or depth is negative |
| `IncompleteTopologyError` | Strict mode found graph-specific gaps; `.document` retains the canonical result |

The compatibility exception exposes `installed_version`, `supported_specifier`,
and `tested_versions`. A supported framework may still raise an introspection
error, especially during expanded traversal.

## TypeScript producer

Import from `@agent-topology/langgraph`:

```typescript
describe(compiledGraph: CompiledStateGraph, options?: { graphId?: string; depth?: number }): Promise<TopologyDocument>
```

Use `await`. `graphId` is the same non-empty document-local address and defaults to
`main`. Invalid graph inputs, graph ids, or depths reject with `TypeError`;
unsupported framework versions reject with `UnsupportedLangGraphVersionError`.
That exception exposes `installedVersion`, `supportedRange`, and `testedVersions`.
There is no strict option or incomplete-topology exception; inspect the returned
document's gaps. Expanded traversal may reject with a framework error.

## Specification utilities

| Python: `agent_topology.spec` | TypeScript: `@agent-topology/spec` | Purpose |
| --- | --- | --- |
| `load_schema()` | `loadSchema()` | Load a copy of the packaged canonical schema |
| `validate_document(value, schema=None)` | `validateDocument(value)` | Check schema, references, uniqueness, and completeness |
| `canonicalize_document(document)` | `canonicalizeDocument(document)` | Return a canonical copy without mutating the input |
| `canonical_json(document)` | `canonicalStringify(document)` | Serialize canonical JSON |
| `compute_structure_hash(document, *, algorithm_version="1")` | `computeStructureHash(document, algorithmVersion="1")` | Compute the structural hash descriptor |
| `finalize_document(document, *, algorithm_version="1")` | `finalizeDocument(document, algorithmVersion="1")` | Replace the hash and return a canonical copy |

Python validation returns a list of path-qualified error strings; an empty list
means valid. TypeScript returns `{ valid: true, document }` or
`{ valid: false, errors }`, with each error carrying `path` and `message`.
TypeScript also provides `isTopologyDocument(value)` as a type guard and
`assertTopologyDocument(value)`, which throws `TopologyValidationError` with an
`.errors` array.

Both packages export `STRUCTURE_HASH_ALGORITHM` and
`STRUCTURE_HASH_ALGORITHM_VERSION`. Unsupported hash algorithm versions raise
`ValueError` in Python or `RangeError` in TypeScript. Validation does not recompute
the stored hash, and canonicalization does not validate the input. See
[consumer examples](../guides/consuming-documents.md) for the correct sequence.

The [schema reference](../../spec/README.md) owns field definitions and hash
coverage. Internal modules are implementation details, not supported imports.
