// Copy beside the installed packages; run with Node >=20. No graph is invoked.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { describe } from "@agent-topology/langgraph";
import {
  assertTopologyDocument,
  computeStructureHash,
  validateDocument,
} from "@agent-topology/spec";

const State = Annotation.Root({ value: Annotation() });
const noop = () => ({});
const single = (name) =>
  new StateGraph(State)
    .addNode(name, noop)
    .addEdge(START, name)
    .addEdge(name, END)
    .compile();
const output = { node: process.version, documents: {}, observations: {} };
async function record(name, graph, options) {
  const doc = await describe(graph, options);
  assertTopologyDocument(doc);
  assert.deepEqual(computeStructureHash(doc), doc.structureHash);
  // Only wall-clock provenance is normalized; all extracted facts are retained.
  doc.provenance.generatedAt = "2000-01-01T00:00:00Z";
  output.documents[name] = doc;
  return doc;
}
function branch(route) {
  return new StateGraph(State)
    .addNode("router", noop)
    .addNode("left", noop)
    .addNode("right", noop)
    .addEdge(START, "router")
    .addConditionalEdges("router", route, ["left", "right"])
    .addEdge("left", END)
    .addEdge("right", END)
    .compile();
}
const one = await record(
  "F1-one",
  branch(() => "left"),
);
const many = await record(
  "F1-many",
  branch(() => ["left", "right"]),
);
assert.deepEqual(one.graphs, many.graphs);
assert.deepEqual(one.structureHash, many.structureHash);
const trial = structuredClone(one);
trial.graphs[0].structure["x-topology-branch"] = [
  {
    id: "branch:router",
    sourceId: "router",
    mode: "exclusive",
    edgeIds: one.graphs[0].structure.edges
      .filter((e) => e.source === "router")
      .map((e) => e.id),
  },
];
assertTopologyDocument(trial);
assert.deepEqual(computeStructureHash(trial), one.structureHash);
output.documents["F1-consumer-trial"] = trial;
output.observations.F1 = {
  sameStructure: true,
  sameHash: true,
  trialValid: true,
  trialHashUnchanged: true,
};

const unknown = await record(
  "F2-unknown",
  new StateGraph(State)
    .addNode("router", noop)
    .addNode("target", noop)
    .addEdge(START, "router")
    .addConditionalEdges("router", () => "target")
    .addEdge("target", END)
    .compile(),
);
assert.deepEqual(unknown.graphs[0].structure.entryNodeIds, [START, "target"]);
assert.equal(unknown.completeness.gaps[0].element.id, "router");
output.observations.F2 = {
  entries: unknown.graphs[0].structure.entryNodeIds,
  gaps: unknown.completeness.gaps,
};

const nestedGraph = new StateGraph(State)
  .addNode("nested", single("inner"))
  .addEdge(START, "nested")
  .addEdge("nested", END)
  .compile();
const nested = await record("F3-nested", nestedGraph);
const ordinary = await record("F3-ordinary", single("nested"));
const coreNode = (doc) =>
  Object.fromEntries(
    Object.entries(
      doc.graphs[0].structure.nodes.find((n) => n.id === "nested"),
    ).filter(([key]) => !key.startsWith("x-")),
  );
assert.deepEqual(coreNode(nested), coreNode(ordinary));
const dangling = structuredClone(nested);
dangling.graphs[0].structure.nodes.find((n) => n.id === "nested").subgraphId =
  "absent";
assert.equal(validateDocument(dangling).valid, false);
output.observations.F3 = {
  nestedCore: coreNode(nested),
  ordinaryCore: coreNode(ordinary),
  danglingSubgraphRejected: true,
};

const joined = await record(
  "F4-join",
  new StateGraph(State)
    .addNode("left", noop)
    .addNode("right", noop)
    .addNode("joined", noop)
    .addEdge(START, "left")
    .addEdge(START, "right")
    .addEdge(["left", "right"], "joined")
    .addEdge("joined", END)
    .compile(),
);
const structure = joined.graphs[0].structure;
assert.equal(structure.joins.length, 1);
assert.equal(structure.edges.filter((e) => e.target === "joined").length, 0);
output.observations.F4 = { joins: structure.joins, incomingOrdinaryEdges: 0 };

const sentinel = await record("F5-sentinels", single("task"));
const sentinels = sentinel.graphs[0].structure.nodes.filter(
  (n) => n["x-langgraph"].sentinel,
);
assert.deepEqual(
  sentinels.map((n) => n.id),
  [END, START],
);
assert(sentinels.every((n) => !("type" in n)));
output.observations.F5 = { sentinels };

const require = createRequire(import.meta.url);
let requireCode;
try {
  require("@agent-topology/spec");
} catch (error) {
  requireCode = error.code;
}
assert.equal(requireCode, "ERR_PACKAGE_PATH_NOT_EXPORTED");
const specRoot = dirname(
  dirname(fileURLToPath(import.meta.resolve("@agent-topology/spec"))),
);
const metadata = JSON.parse(
  readFileSync(join(specRoot, "package.json"), "utf8"),
);
assert.deepEqual(metadata.dependencies, {
  ajv: "8.20.0",
  "ajv-formats": "3.0.1",
});
output.observations.F6 = {
  esmImport: "passed",
  requireCode,
  version: metadata.version,
  exports: metadata.exports,
  dependencies: metadata.dependencies,
};
console.log(JSON.stringify(output, null, 2));
