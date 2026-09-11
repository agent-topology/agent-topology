# LangGraph Python 1.2.11 research dossier

## Scope

This is the source baseline for the Python LangGraph producer. It links official
documentation and immutable upstream source to the topology questions that
agent-topology must answer. The producer tests and shared conformance fixtures
provide the corresponding behavioural verification.

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

The research baseline is 1.2.11. The supported range is 1.2.10 through 1.2.11
because both exact releases pass the same producer and shared-conformance matrix.
A version outside that range is added only after the same checks pass on it.

## Initial source findings

| Topology question                               | 1.2.11 source finding                                                                                 | State           |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------- | --------------- |
| Where are nodes stored?                         | `StateGraph.nodes` is a mapping of node names to node specifications.                                 | source-verified |
| Where are ordinary edges stored?                | `StateGraph.edges` is a set of source-target pairs.                                                   | source-verified |
| Is a multi-source join distinguishable?         | `StateGraph.waiting_edges` stores a tuple of sources with one target, separately from ordinary edges. | source-verified |
| Where are conditional routes stored?            | `StateGraph.branches` stores branch specifications by source and branch name.                         | source-verified |
| Can a compiled graph reach the builder?         | `compile()` passes `builder=self`; `CompiledStateGraph` stores it as `builder`.                       | source-verified |
| Is drawable graph extraction public?            | `Pregel.get_graph()` publicly returns a drawable representation.                                      | source-verified |
| Are subgraphs enumerable?                       | `Pregel.get_subgraphs()` publicly yields immediate or recursive subgraphs.                            | source-verified |
| Are static interrupts declared at compile time? | `StateGraph.compile()` accepts `interrupt_before` and `interrupt_after`.                              | source-verified |

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

## Executable evidence

The producer tests construct the minimum compiled graphs needed to inspect the
builder and drawable surfaces: a linear graph; declared and undeclared routes;
`Command[Literal[...]]` destinations; a multi-source join contrasted with
independent incoming edges; nested graphs at two depths; and static before/after
interrupts. The shared runner independently constructs all eight language-neutral
fixture recipes and compares canonical core output with the single expected
documents under `conformance/fixtures`.

The compatibility workflow derives its Python matrix from the producer's
`_compatibility.json` manifest and runs that complete suite at 1.2.10 and 1.2.11.
A failed or lossy observation remains useful evidence: it must be recorded as a
producer limitation or graph-specific gap rather than hidden by normalization.

## Official entry points

- Release: <https://github.com/langchain-ai/langgraph/releases/tag/1.2.11>
- Package: <https://pypi.org/project/langgraph/1.2.11/>
- API reference: <https://reference.langchain.com/python/langgraph/overview>
- LangGraph guide index: <https://docs.langchain.com/oss/python/langgraph/llms.txt>
- Versioning: <https://docs.langchain.com/oss/python/versioning>
- Release policy: <https://docs.langchain.com/oss/python/release-policy>
