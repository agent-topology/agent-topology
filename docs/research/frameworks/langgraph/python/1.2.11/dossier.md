# LangGraph Python 1.2.11 research dossier

## Scope

This is the initial research baseline for the Python LangGraph producer. It
links official documentation and immutable upstream source to the topology
questions that agent-topology must answer. Source findings are not yet treated
as behavioural verification; minimum probes are the next step.

The exact release is `langgraph==1.2.11`, tag `1.2.11`, resolved to commit
`644815f9e5bc52ad8f7a5227a456227e9c3e639b`. GitHub records the release on
2026-08-11. The official API reference reported 1.2.11 when this dossier was
created on 2026-09-10.

## Why the version is exact

LangGraph 1.x documents semantic-versioning and LTS guarantees for public APIs.
The producer may need structural data that public drawable APIs normalise or do
not expose. Any dependency on a builder attribute or another non-contractual
surface therefore needs its own compatibility evidence. Upstream semver is not
a replacement for that evidence.

The initial supported range stays at exactly 1.2.11. A later version is added
only after the same minimum probes and conformance cases pass on it.

## Initial source findings

| Topology question | 1.2.11 source finding | State |
| --- | --- | --- |
| Where are nodes stored? | `StateGraph.nodes` is a mapping of node names to node specifications. | source-verified |
| Where are ordinary edges stored? | `StateGraph.edges` is a set of source-target pairs. | source-verified |
| Is a multi-source join distinguishable? | `StateGraph.waiting_edges` stores a tuple of sources with one target, separately from ordinary edges. | source-verified |
| Where are conditional routes stored? | `StateGraph.branches` stores branch specifications by source and branch name. | source-verified |
| Can a compiled graph reach the builder? | `compile()` passes `builder=self`; `CompiledStateGraph` stores it as `builder`. | source-verified |
| Is drawable graph extraction public? | `Pregel.get_graph()` publicly returns a drawable representation. | source-verified |
| Are subgraphs enumerable? | `Pregel.get_subgraphs()` publicly yields immediate or recursive subgraphs. | source-verified |
| Are static interrupts declared at compile time? | `StateGraph.compile()` accepts `interrupt_before` and `interrupt_after`. | source-verified |

The exact source links for these findings live in
[`catalog.yaml`](../../../../catalog.yaml). Keeping the structured links in one file
prevents the prose dossier and automation from becoming competing authorities.

## Research risks

### Drawable output may be lossy

`get_graph()` is attractive because it is public, but its contract is a
drawable representation. The producer needs execution structure. A probe must
compare drawable output with builder state for ordinary edges, multi-source
joins, conditional routes, interrupts, and nested subgraphs before choosing it
as an extraction surface.

### Builder access may be non-contractual

The `builder` attribute is visible and preserves distinctions such as
`waiting_edges`, but visibility does not establish a cross-version stability
promise. If the producer uses it, the supported range must remain tied to the
versions exercised by the compatibility matrix.

### Conditional destinations can be unknown

The 1.2.11 `add_conditional_edges` documentation says that a route without a
path map or suitable return type hint may be drawn as capable of reaching any
node. That is a visualization assumption, not proof of actual destinations.
This must become a graph-specific gap rather than a complete-looking fan-out.

## Minimum probes to add next

Each probe should construct only the graph needed to answer its question and
should record both builder state and public drawable output.

1. one node with `START` and `END`;
2. three nodes connected linearly;
3. a conditional branch with an explicit path map;
4. a conditional branch with `Command[Literal[...]]` destinations;
5. a conditional branch with undeclared destinations;
6. one multi-source edge compared with independent incoming edges;
7. one immediate subgraph and one nested subgraph;
8. one `interrupt_before` and one `interrupt_after` declaration.

Probe results should update the corresponding catalog entry from
`source-verified` to `verified` and link the smallest applicable conformance
fixture. A failed or lossy observation is still a useful result and should be
recorded as a limitation or graph-specific gap rather than hidden.

## Official entry points

- Release: <https://github.com/langchain-ai/langgraph/releases/tag/1.2.11>
- Package: <https://pypi.org/project/langgraph/1.2.11/>
- API reference: <https://reference.langchain.com/python/langgraph/overview>
- LangGraph guide index: <https://docs.langchain.com/oss/python/langgraph/llms.txt>
- Versioning: <https://docs.langchain.com/oss/python/versioning>
- Release policy: <https://docs.langchain.com/oss/python/release-policy>
