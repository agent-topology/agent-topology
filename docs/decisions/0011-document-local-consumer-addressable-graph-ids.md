# 0011. Document-local, consumer-addressable graph identifiers

- Status: Accepted
- Date: 2026-09-12

## Context

`graphs[].id` is the address used by `element.graphId` and `subgraphId`. The
validators already reject unknown references and duplicate graph identifiers, but
the LangGraph producers always emitted `main`. Combining two independently produced
documents therefore created an invalid or ambiguous multi-graph document unless a
consumer rewrote derived output after extraction.

Graph display names do not solve this problem. LangGraph graph authors already own
the optional `graphs[].name` value through `StateGraph.compile(name=...)`; names are
descriptive, need not be unique, and are excluded from structure hash version 1.
Identifiers are structural, are included in that hash, and must support exact
references.

## Decision

Graph identifiers are document-local addresses selected by the caller at extraction
time. They must be unique within one `graphs` array. Every `element.graphId` and
`subgraphId` resolves against that unique set.

Both LangGraph `describe` APIs accept an optional caller-supplied graph identifier.
Python spells it `graph_id`; TypeScript spells it `graphId` in `DescribeOptions`.
The Python `agt describe` command exposes the same choice as `--graph-id`. All three
surfaces retain `main` as the default for compatibility with existing single-graph
documents. A supplied identifier must be a non-empty string.

A caller that intends to compose several producer outputs assigns distinct, stable
identifiers while describing each compiled graph, then combines the resulting graph
records and associated gaps without rewriting either identity. Composition itself
remains a consumer responsibility and is not added to a producer API.

The producer-provided identifier is used by every derived gap reference, including
graph-local and node-local gaps. `graphs[].name` remains independent: for LangGraph
it comes from `compiled_graph.get_name()`, which reflects
`StateGraph.compile(name=...)` and is owned by the graph author.

## Consequences

- A composed document can address each graph and its gaps unambiguously.
- Duplicate graph identifiers remain a validation error in both specification
  packages, and the error names the repeated value.
- Existing callers that produce one graph keep receiving `main` without changes.
- Choosing a different identifier changes the existing version-1 structure hash
  because graph identifiers were already in its projection. Neither the document
  shape nor the hash projection changes, so `topologyVersion` remains `0.1` and
  `structureHash.algorithmVersion` remains `1`.
- Display-name uniqueness is neither required nor implied.

## What we are explicitly not doing

- Adding a multi-document composition helper or producer feature.
- Deriving identity from a display name, framework object identity, or structure
  hash.
- Changing the schema, canonical ordering, or structure-hash coverage.

## Revisiting

Revisit the default only in a future format transition with migration evidence.
Revisit document-local scope if a registry or cross-document reference contract
enters project scope; neither exists in the 0.1 candidate.
