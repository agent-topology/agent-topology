# Troubleshooting

[Documentation home](../README.md) · [CLI exit codes](../reference/cli.md)

## `agt` is not found

Activate the environment where you installed `agent-topology-langgraph` and run
`python -m pip show agent-topology-langgraph`. Installing only the specification
or either npm package does not install `agt`.

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

Use `depth=0` / `{ depth: 0 }` to keep subgraphs opaque. Expanded traversal relies
on the framework's drawable graph, flattens child identifiers, and is not a complete
recursive extraction of child builder metadata. Child join, interrupt, and unknown
router details should not be inferred from the expanded picture alone. Describe
a compiled child separately when those details matter. Deep traversal can also
fail in the framework.

Current source records an `expanded-subgraph-metadata` gap on the containing graph
when child nodes are expanded, so Python strict mode raises for that result. This
correction is unreleased; the original beta.1 can report such a view as complete.

## Validation succeeds but the hash is wrong

Validation checks shape and references, not the stored digest. Follow the
[consumer guide](consuming-documents.md) to recompute and compare it before using
the document as structural-change evidence.

## Ask for help

Use GitHub Issues for ordinary support. Include package and framework versions,
runtime version, the command or API call, and a minimal graph reproducing the
problem. Remove credentials and sensitive graph metadata. For vulnerabilities,
follow the [private reporting policy](../../SECURITY.md).
