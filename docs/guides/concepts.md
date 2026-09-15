# Understanding a topology

[Documentation home](../README.md)

A topology is a snapshot of a workflow's structure at extraction time. A trace
records what happened during one execution. Reading both lets you relate an
observed node to the graph that declared it, while preserving what neither source
can establish.

## Producer, document, consumer

A **producer** inspects a compiled object in its framework's process and language.
Python LangGraph uses `agent_topology.langgraph`; LangGraph.js uses
`@agent-topology/langgraph`.

The **document** is JSON. It carries structural facts, provenance, a structure
hash, and uncertainty. It is generated from a compiled workflow, not maintained
by hand.

A **consumer** reads that JSON without importing the producer or framework. The
specification packages provide validation, canonical serialization, and hashing.
Examples include trace correlation and a separately built viewer.

## Structural fields

Each document contains one or more graphs. Inside each graph's `structure`:

| Field | Meaning |
| --- | --- |
| `nodes` | Identified workflow elements; may carry a type or static interrupt locations |
| `edges` | Direct or conditional connections from one node to another |
| `joins` | A declared connection from several source nodes to one target |
| `entryNodeIds` | Entry points recorded for the extracted structure |
| `exitNodeIds` | Terminal points recorded for the extracted structure |

A join with `sources: ["left", "right"]` is distinct from two independent edges
into the same target. Loops are cycles in the edge structure. A conditional edge
does not establish whether destinations are alternatives or all execute, nor how
many runtime tasks a fan-out produces.

Identifiers are scoped to their graph; use `(graphId, nodeId)` to correlate nodes.
The current producers use `main` as the root graph ID and retain `__start__` and
`__end__`. Sentinel markers, traversal depth, and framework names live in
`x-langgraph`. Consumers should tolerate extensions without treating them as core
facts.

The schema permits separate graphs connected with `subgraphId`. Current source's
LangGraph producers now populate exactly that at positive depth: a node holding a
confirmed compiled child keeps its own id in its containing graph and gains a
core `subgraphId` addressing a materialized child graph, a first-class `graphs[]`
entry with its own structure and gaps, derived deterministically as
`parentGraphId:parentNodeId`. At depth `0`, child contents stay opaque exactly as
before. See
[ADR 0012](../decisions/0012-nested-graph-identity-traversal-and-compatibility.md).
This correction is listed under [Unreleased](../../CHANGELOG.md#unreleased).

## Two kinds of uncertainty

`producerLimitations` records categories the producer cannot observe in principle.
For example, an interrupt raised inside a node function is invisible to static
inspection. These limitations do not make every document incomplete.

`completeness.gaps` records unknowns for this particular graph. Each gap identifies
an affected graph, node, edge, or join. An `unknown-routing-targets` gap names the
router whose destinations could not be determined. Completeness is `complete`
exactly when the gap list is empty.

Always present both kinds of uncertainty. `complete` means no recorded
graph-specific gaps at the requested scope; it does not prove that all runtime
behavior is known or that every possible blind spot was detected. In particular,
opaque children are not evidence about their internals.

## What a structure hash proves

The structure hash compares the contract's selected structural properties after
canonical ordering. Compare the entire hash descriptor: `algorithm`,
`algorithmVersion`, and `value`. Different algorithm versions are not comparable.

Generation time, graph names, completeness, limitations, and extensions are
excluded. Two documents can have the same hash and different uncertainty or
provenance. Read those fields separately. A changed node function with unchanged
topology can also keep the same hash: this is not a source-code or behavior hash.

The document format (`topologyVersion`), hash algorithm version, and four package
versions evolve independently. See the [0.1 contract](../0.1-contract.md) for the
precise change policy and the [schema reference](../../spec/README.md) for hash
coverage.
