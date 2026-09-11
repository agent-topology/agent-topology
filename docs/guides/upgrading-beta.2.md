# Upgrade from beta.1 to beta.2

[Documentation home](../README.md) · [Release notes](../releases/v0.1.0-beta.2.md)

Status: **Published and verified.** Install the exact beta.2 versions below;
[release notes](../releases/v0.1.0-beta.2.md) record public artifacts and verification.

## Select the packages

| Package | beta.1 → beta.2 selection | Runtime | Framework |
| --- | --- | --- | --- |
| `agent-topology-spec` | `0.1.0b1` → `0.1.0b2` | Python 3.11–3.14 | None |
| `agent-topology-langgraph` | `0.1.0b1` → `0.1.0b2` | Python 3.11–3.14 | LangGraph 1.2.10–1.2.11 |
| `@agent-topology/spec` | `0.1.0-beta.1` → `0.1.0-beta.2` | Node.js 20+ | None |
| `@agent-topology/langgraph` | `0.1.0-beta.1` → `0.1.0-beta.2` | Node.js 20+ | LangGraph.js 1.4.14 |

Python uses PEP 440 `0.1.0b2`; npm uses SemVer `0.1.0-beta.2`. Package versions
are independent of document versions. Specification-only consumers need only
their ecosystem's spec package. The Python producer installs
`agent-topology-spec>=0.1.0b2,<0.2.0`; pin both to `0.1.0b2` to reproduce this
release. The npm producer requires the exact `@agent-topology/spec@0.1.0-beta.2`
peer: select both npm packages explicitly. Keep LangGraph.js at `1.4.14` when
importing it directly. Verify resolved versions in your lockfile/environment;
producers refuse framework versions outside these tested boundaries. Node packages
are ESM and do not support browser execution. Only the Python producer supplies `agt`.

## Review canonical output and hash baselines

The beta.1 TypeScript implementation used UTF-16 ordering for some structural
identifier lists and generated join IDs. Beta.2 uses Unicode code-point order,
matching Python. For example, U+E000 sorts before the non-BMP U+10000 in beta.2;
UTF-16 ordering placed them the other way around. Affected join source lists,
entry/exit identifier lists, and generated join IDs can change canonical output
and `structureHash`. Not every non-BMP identifier produces a changed hash.

1. Preserve beta.1 snapshots and record package/framework versions and traversal
   depth. Identify documents with affected non-BMP structural identifiers.
2. Re-extract the same compiled graphs with beta.2 at the same depth. This also
   refreshes producer-generated join IDs; merely recomputing an old document's
   digest does not repair those IDs.
3. Validate the new documents and recompute their hashes with beta.2 specification
   utilities, following the [consumer guide](consuming-documents.md). Review the
   structural fields and gaps, then regenerate affected snapshots and cache
   baselines. Re-key or invalidate affected cache entries after review.
4. Compare future exports against the reviewed beta.2 baseline. Do not present a
   hash change alone during this upgrade as evidence that the topology changed.

The document format remains `0.1` and the structure-hash algorithm version remains
`1`: these fixes implement the existing contract and hash projection. They do not
promise compatibility with beta.1's erroneous output. Inspect completeness
separately from hashes; gaps and producer limitations are not hashed structure.

## Retain incomplete expanded documents

Beta.1 could report expanded child views as complete. Beta.2 records an
`expanded-subgraph-metadata` gap on the containing graph when child nodes are
actually expanded. Child join, routing, and interrupt declarations are not fully
inspected through the drawable view. A positive depth alone does not imply a gap
if no child nodes expand.

Save this minimal Python example as `upgrade.py` and run `python upgrade.py`:

```python
from langgraph.graph import END, START, StateGraph

from agent_topology.langgraph import IncompleteTopologyError, describe
from agent_topology.spec import canonical_json

child = StateGraph(dict)
child.add_node("step", lambda state: state)
child.add_edge(START, "step")
child.add_edge("step", END)

parent = StateGraph(dict)
parent.add_node("child", child.compile())
parent.add_edge(START, "child")
parent.add_edge("child", END)
graph = parent.compile()

try:
    document = describe(graph, depth=1, strict=True)
except IncompleteTopologyError as error:
    document = error.document

# Preserve the canonical result, including gaps and its computed hash.
print(canonical_json(document))
```

With beta.2 this catches `IncompleteTopologyError` and prints the retained
incomplete document. Update strict-mode callers to save/report `error.document`
before enforcing their failure policy. Do not retry extraction or discard gaps
just to make a check pass.

The TypeScript API has no `strict` option or incomplete-topology exception. Inspect
`completeness.gaps` and retain the returned document. This JavaScript example uses
the same public API. Two child nodes are needed here because LangGraph.js keeps a
one-node child opaque. Save it as `upgrade.mjs` and run `node upgrade.mjs`:

```javascript
import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { describe } from "@agent-topology/langgraph";
import { canonicalStringify } from "@agent-topology/spec";

const State = Annotation.Root({ value: Annotation() });
const child = new StateGraph(State)
  .addNode("step", (state) => state)
  .addEdge(START, "step")
  .addNode("finish", (state) => state)
  .addEdge("step", "finish")
  .addEdge("finish", END)
  .compile();
const graph = new StateGraph(State)
  .addNode("child", child)
  .addEdge(START, "child")
  .addEdge("child", END)
  .compile();

const document = await describe(graph, { depth: 1 });
console.log(canonicalStringify(document));
if (document.completeness.gaps.length > 0) {
  console.error("Incomplete topology:", document.completeness.gaps);
  process.exitCode = 1;
}
```

Expect canonical JSON on stdout and exit status `1` from this example's consumer
policy. Verify that the gap code is `expanded-subgraph-metadata`, its element is
`{ graphId: "main", kind: "graph", id: "main" }`, and the document is incomplete.
Use `depth=0` / `{ depth: 0 }` when an opaque child is sufficient; describe the
compiled child separately when its declarations matter. Expanded output does not
provide complete recursive metadata.

Producer-wide limitations, including `dynamic-interrupts`, are unchanged. Display
them separately: they do not make a document incomplete or cause Python strict
mode to fail. Verify that your ordinary complete/opaque graphs still pass your
completeness gate and that expanded graphs retain their local uncertainty.
