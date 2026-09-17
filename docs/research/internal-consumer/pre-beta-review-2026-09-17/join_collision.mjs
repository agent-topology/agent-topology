// Run after building both local TypeScript packages. No workflow invocation.
import { Annotation, StateGraph, START, END } from "../../../../packages/typescript/langgraph/node_modules/@langchain/langgraph/dist/index.js";
import { describe } from "../../../../packages/typescript/langgraph/dist/index.js";
import { validateDocument } from "../../../../packages/typescript/spec/dist/index.js";

const State = Annotation.Root({ values: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] }) });
for (const [label, groups] of [
  ["reversed-sources", [["a", "b"], ["b", "a"]]],
  ["delimiter", [["a+b", "c"], ["a", "b+c"]]],
]) {
  const builder = new StateGraph(State);
  for (const name of [...new Set([...groups.flat(), "sink"])].sort()) {
    builder.addNode(name, () => ({ values: [] }));
    if (name !== "sink") builder.addEdge(START, name);
  }
  for (const sources of groups) builder.addEdge(sources, "sink");
  builder.addEdge("sink", END);
  try {
    const document = await describe(builder.compile(), { strict: true });
    console.log(JSON.stringify({ case: label, joins: document.graphs[0].structure.joins, errors: validateDocument(document) }));
  } catch (error) {
    console.log(JSON.stringify({ case: label, exception: error.name, message: error.message }));
  }
}
