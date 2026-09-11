# TypeScript / JavaScript quickstart

See the [beta.1 to beta.2 upgrade guide](../guides/upgrading-beta.2.md) for candidate
package selections, hash baselines, and expanded-subgraph migration.

[Documentation home](../README.md) · [Compatibility](../reference/compatibility.md)

Export a compiled LangGraph.js workflow in Node.js 20 or later. These packages
publish ES modules. The example uses JavaScript so you can run it without a
TypeScript build step; the same imports have TypeScript declarations.

## Install

In a new directory:

```bash
npm init -y
npm install @agent-topology/spec@0.1.0-beta.1 @agent-topology/langgraph@0.1.0-beta.1 @langchain/langgraph@1.4.14
```

Install both agent-topology packages: the producer declares the specification as
a peer dependency. LangGraph.js is listed explicitly because the example imports
it directly.

## Export a graph

Save this as `graph.mjs`:

```javascript
import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { describe } from "@agent-topology/langgraph";
import { canonicalStringify } from "@agent-topology/spec";

const State = Annotation.Root({ message: Annotation() });
const graph = new StateGraph(State)
  .addNode("greet", (state) => ({ message: `Hello, ${state.message}!` }))
  .addEdge(START, "greet")
  .addEdge("greet", END)
  .compile();

const document = await describe(graph);
console.log(canonicalStringify(document));
```

```bash
node graph.mjs > topology.json
```

The node function is not invoked. The resulting document contains `main`, three
nodes including the framework's start and end sentinels, and two direct edges.
Its completeness status is `complete`; the separate `dynamic-interrupts`
producer limitation is expected.

`describe` is asynchronous, so use `await`. There is no TypeScript `agt` executable
and no `strict` option. A caller that requires completeness should check
`document.completeness.gaps.length` and retain the document when reporting failure.

## Use it from TypeScript

The public producer returns `Promise<TopologyDocument>`. Use the exported document
type when defining a consumer interface:

```typescript
import type { TopologyDocument } from "@agent-topology/spec";

function nodeCount(document: TopologyDocument): number {
  return document.graphs.reduce(
    (total, graph) => total + graph.structure.nodes.length,
    0,
  );
}
```

For a TypeScript application, use an ESM-compatible compiler configuration and
compile before running with Node. The published specification package currently
uses `node:crypto` for hashing; browser execution is not a supported package target.

Next: [understand the document](../guides/concepts.md),
[validate it as a consumer](../guides/consuming-documents.md), or
[look up the API](../reference/api.md).
