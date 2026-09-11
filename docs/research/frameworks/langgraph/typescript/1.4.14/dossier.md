# LangGraph.js 1.4.14 research dossier

## Scope

This is the independent source and behavioural baseline for the TypeScript
LangGraph producer. It does not reuse Python compatibility evidence. The exact
npm release is `@langchain/langgraph@1.4.14`, published on 2026-09-04. Its tag
resolves to commit `9ae75600dd84d6b2bc736e33baaf66a556d61c49`.

The supported package range remains exactly 1.4.14. The runtime installation
hint, package dependency, and CI matrix are derived from or checked against
`packages/typescript/langgraph/src/compatibility.json`; widening package
metadata alone fails the compatibility-contract check.

## Verified source surfaces

| Topology question                              | 1.4.14 finding                                                                                                                               |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Can a compiled graph reach its builder?        | `StateGraph.compile()` passes `builder: this`, and `CompiledStateGraph` declares that builder.                                               |
| Where are nodes and ordinary edges stored?     | `Graph.nodes` and `Graph.edges` retain node specifications and source-target pairs.                                                          |
| Is a multi-source join distinguishable?        | `StateGraph.waitingEdges` stores the sources array and target separately from ordinary edges.                                                |
| How are conditional destinations represented?  | `Branch.ends` retains declared path maps; its absence distinguishes unknown targets. Node-level `ends` declarations are retained separately. |
| Is asynchronous drawable extraction available? | `Pregel.getGraphAsync()` is the preferred asynchronous graph accessor and delegates to the xray-capable drawable graph.                      |
| Are nested graphs retained?                    | Pregel-like node actions are recorded in the node specification's `subgraphs` collection.                                                    |
| Are static interrupts retained?                | `Pregel.interruptBefore` and `interruptAfter` preserve compile-time declarations.                                                            |

Immutable source links for every finding live in
[`catalog.yaml`](../../../../catalog.yaml). The executable
[introspection probe](probes/introspection.mjs) verifies the minimum builder,
drawable, branch, join, subgraph, and interrupt observations against the exact
installed release. The TypeScript conformance runner then constructs all eight
language-neutral fixtures and compares their complete normalized documents and
canonical UTF-8 bytes with the shared expectations.

## Compatibility policy

These observations include builder state that is visible in the released type
surface but is not promised as a stable public extraction API. Upstream semantic
versioning is therefore insufficient evidence for a wider producer range. Each
additional exact release must be added to the tested-version manifest only with
the same probe and shared-conformance results.

## Official entry points

- Release: <https://github.com/langchain-ai/langgraphjs/releases/tag/%40langchain/langgraph%401.4.14>
- Package: <https://www.npmjs.com/package/@langchain/langgraph/v/1.4.14>
- Immutable source: <https://github.com/langchain-ai/langgraphjs/tree/9ae75600dd84d6b2bc736e33baaf66a556d61c49/libs/langgraph-core>
