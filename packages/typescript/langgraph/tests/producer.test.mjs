import assert from "node:assert/strict";
import { test } from "node:test";

import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { canonicalStringify, validateDocument } from "@agent-topology/spec";

import * as producer from "../dist/index.js";
import { UnsupportedLangGraphVersionError, describe } from "../dist/index.js";
import { describeWithVersion } from "../dist/internal.js";

const State = Annotation.Root({ value: Annotation });
/** @param {Record<string, unknown>} state */
const step = (state) => state;

test("the public root exposes only the producer API", () => {
  assert.deepEqual(Object.keys(producer).sort(), [
    "UnsupportedLangGraphVersionError",
    "describe",
  ]);
});

test("describes direct structure, entry and exit points, and static interrupts", async () => {
  const compiled = new StateGraph(State)
    .addNode("first", step)
    .addNode("last", step)
    .addEdge(START, "first")
    .addEdge("first", "last")
    .addEdge("last", END)
    .compile({
      name: "linear",
      interruptBefore: "*",
      interruptAfter: ["last"],
    });

  const document = await describe(compiled);
  const graph = document.graphs[0];
  assert.ok(graph);
  assert.equal(validateDocument(document).valid, true);
  assert.equal(canonicalStringify(document), JSON.stringify(document));
  assert.equal(graph.name, "linear");
  assert.deepEqual(
    graph.structure.nodes.map((node) => node.id),
    [END, START, "first", "last"],
  );
  assert.deepEqual(
    graph.structure.edges.map((edge) => [edge.source, edge.target, edge.kind]),
    [
      [START, "first", "direct"],
      ["first", "last", "direct"],
      ["last", END, "direct"],
    ],
  );
  assert.deepEqual(graph.structure.entryNodeIds, [START]);
  assert.deepEqual(graph.structure.exitNodeIds, [END]);
  assert.deepEqual(
    graph.structure.nodes.find((node) => node.id === "first")?.interrupts,
    ["before"],
  );
  assert.deepEqual(
    graph.structure.nodes.find((node) => node.id === "last")?.interrupts,
    ["after", "before"],
  );
  assert.deepEqual(document.producerLimitations, [
    {
      code: "dynamic-interrupts",
      message:
        "Interrupts raised inside node bodies cannot be observed statically.",
    },
  ]);
  assert.deepEqual(document.completeness, { status: "complete", gaps: [] });
  assert.deepEqual(graph["x-langgraph"], { traversalDepth: 0 });
  assert.deepEqual(
    graph.structure.nodes.find((node) => node.id === START)?.["x-langgraph"],
    { name: START, sentinel: true },
  );
});

test("extracts declared branches and reports undeclared targets as a local gap", async () => {
  const declared = new StateGraph(State)
    .addNode("route", step)
    .addNode("left", step)
    .addNode("right", step)
    .addEdge(START, "route")
    .addConditionalEdges("route", () => "left", {
      left: "left",
      right: "right",
    })
    .addEdge("left", END)
    .addEdge("right", END)
    .compile();
  const declaredDocument = await describe(declared);
  const declaredEdges = declaredDocument.graphs[0]?.structure.edges.filter(
    (edge) => edge.source === "route",
  );
  assert.deepEqual(
    declaredEdges?.map((edge) => [edge.target, edge.kind]),
    [
      ["left", "conditional"],
      ["right", "conditional"],
    ],
  );

  const unknown = new StateGraph(State)
    .addNode("route", step)
    .addNode("target", step)
    .addEdge(START, "route")
    .addConditionalEdges("route", () => "target")
    .addEdge("target", END)
    .compile();
  const unknownDocument = await describe(unknown);
  assert.equal(unknownDocument.completeness.status, "incomplete");
  assert.deepEqual(unknownDocument.completeness.gaps, [
    {
      code: "unknown-routing-targets",
      message: "Not every destination of this router could be determined.",
      element: { graphId: "main", kind: "node", id: "route" },
    },
  ]);
  assert.ok(
    !unknownDocument.graphs[0]?.structure.edges.some(
      (edge) => edge.source === "route" && edge.kind === "conditional",
    ),
  );
});

test("keeps a multi-source join distinct from independent incoming edges", async () => {
  const joined = new StateGraph(State)
    .addNode("left", step)
    .addNode("right", step)
    .addNode("joined", step)
    .addEdge(START, "left")
    .addEdge(START, "right")
    .addEdge(["right", "left"], "joined")
    .addEdge("joined", END)
    .compile();
  const joinedDocument = await describe(joined);
  assert.deepEqual(joinedDocument.graphs[0]?.structure.joins, [
    {
      id: "join:left+right:joined",
      sources: ["left", "right"],
      target: "joined",
    },
  ]);
  assert.ok(
    !joinedDocument.graphs[0]?.structure.edges.some(
      (edge) => edge.target === "joined",
    ),
  );

  const independent = new StateGraph(State)
    .addNode("left", step)
    .addNode("right", step)
    .addNode("joined", step)
    .addEdge(START, "left")
    .addEdge(START, "right")
    .addEdge("left", "joined")
    .addEdge("right", "joined")
    .addEdge("joined", END)
    .compile();
  const independentDocument = await describe(independent);
  assert.deepEqual(independentDocument.graphs[0]?.structure.joins, []);
  assert.notDeepEqual(
    joinedDocument.structureHash,
    independentDocument.structureHash,
  );
});

test("expands nested graphs only to the requested depth", async () => {
  const child = new StateGraph(State)
    .addNode("innerFirst", step)
    .addNode("innerLast", step)
    .addEdge(START, "innerFirst")
    .addEdge("innerFirst", "innerLast")
    .addEdge("innerLast", END)
    .compile({ name: "child" });
  const parent = new StateGraph(State)
    .addNode("before", step)
    .addNode("child", child)
    .addNode("after", step)
    .addEdge(START, "before")
    .addEdge("before", "child")
    .addEdge("child", "after")
    .addEdge("after", END)
    .compile({ name: "parent" });

  const opaque = await describe(parent);
  assert.ok(
    opaque.graphs[0]?.structure.nodes.some((node) => node.id === "child"),
  );
  const expanded = await describe(parent, { depth: 1 });
  assert.ok(
    expanded.graphs[0]?.structure.nodes.some(
      (node) => node.id === "child:innerFirst",
    ),
  );
  assert.ok(
    !expanded.graphs[0]?.structure.nodes.some((node) => node.id === "child"),
  );
  assert.deepEqual(expanded.graphs[0]?.["x-langgraph"], {
    traversalDepth: 1,
  });
});

test("refuses unsupported versions before inspecting the graph", async () => {
  const untouched = new Proxy(
    {},
    {
      get() {
        assert.fail("the graph was inspected before compatibility refusal");
      },
    },
  );
  await assert.rejects(
    describeWithVersion(untouched, "9.9.9"),
    (error) =>
      error instanceof UnsupportedLangGraphVersionError &&
      error.message.includes("npm install @langchain/langgraph@1.4.14"),
  );
});

test("validates options and rejects uncompiled graph builders", async () => {
  const compiled = new StateGraph(State)
    .addNode("step", step)
    .addEdge(START, "step")
    .addEdge("step", END)
    .compile();
  await assert.rejects(
    describe(compiled, { depth: -1 }),
    /non-negative integer/,
  );
  await assert.rejects(
    describe(/** @type {any} */ (new StateGraph(State))),
    /CompiledStateGraph returned by StateGraph\.compile/,
  );
});
