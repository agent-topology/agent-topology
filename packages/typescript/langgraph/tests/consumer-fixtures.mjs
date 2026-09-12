// Generate actual public producer output. Expected meanings are never loaded here.
import { readFileSync } from "node:fs";
import { Annotation, StateGraph } from "@langchain/langgraph";
import { describe } from "../dist/index.js";

const State = Annotation.Root({ value: Annotation });
function forbidden() {
  throw new Error("Extraction executed a user node or router");
}
function single() {
  forbidden();
  return "left";
}
function multiple() {
  forbidden();
  return ["left", "right"];
}
function compileRecipe(recipe, reverse) {
  const ordered = (values) => (reverse ? [...values].reverse() : values);
  const builder = new StateGraph(State);
  for (const node of ordered(recipe.nodes))
    builder.addNode(
      node.id,
      node.child ? compileRecipe(node.child, reverse) : forbidden,
    );
  for (const [source, target] of ordered(recipe.edges))
    builder.addEdge(source, target);
  for (const [sources, target] of ordered(recipe.joins ?? []))
    builder.addEdge(ordered(sources), target);
  for (const route of ordered(recipe.routes ?? []))
    builder.addConditionalEdges(
      route.source,
      route.returns === "list" ? multiple : single,
      route.targets ? ordered(route.targets) : undefined,
    );
  return builder.compile();
}
const recipes = JSON.parse(
  readFileSync(
    new URL("../../../../conformance/consumer/recipes.json", import.meta.url),
    "utf8",
  ),
);
const documents = {};
for (const [name, recipe] of Object.entries(recipes)) {
  documents[name] = [];
  for (const reverse of [false, true])
    documents[name].push(await describe(compileRecipe(recipe, reverse)));
}
process.stdout.write(JSON.stringify(documents));
