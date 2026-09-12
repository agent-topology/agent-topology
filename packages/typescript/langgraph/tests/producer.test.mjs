import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import {
  cpSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import {
  canonicalStringify,
  computeStructureHash,
  validateDocument,
} from "@agent-topology/spec";

import * as producer from "../dist/index.js";
import { UnsupportedLangGraphVersionError, describe } from "../dist/index.js";
import { describeWithVersion } from "../dist/internal.js";

const State = Annotation.Root({ value: Annotation });
/** @param {Record<string, unknown>} state */
const step = (state) => state;

test("documented JavaScript quickstart and consumer run end to end", () => {
  const packageRoot = fileURLToPath(new URL("../", import.meta.url));
  const docs = new URL("../../../../docs/", import.meta.url);
  const directory = mkdtempSync(join(packageRoot, ".docs-smoke-"));
  try {
    const quickstart = readFileSync(
      new URL("getting-started/typescript.md", docs),
      "utf8",
    );
    const source = quickstart.match(/```javascript\n([\s\S]*?)\n```/)?.[1];
    assert.ok(source);
    writeFileSync(join(directory, "graph.mjs"), source);
    const output = execFileSync(process.execPath, ["graph.mjs"], {
      cwd: directory,
      encoding: "utf8",
    });
    const validation = validateDocument(JSON.parse(output));
    assert.ok(validation.valid);
    const document = validation.document;
    assert.ok(document.graphs[0]);
    assert.deepEqual(
      document.graphs[0].structure.nodes.map((node) => node.id),
      [END, START, "greet"],
    );
    writeFileSync(join(directory, "topology.json"), output);
    const guide = readFileSync(
      new URL("guides/consuming-documents.md", docs),
      "utf8",
    );
    const consumer = guide.match(/```javascript\n([\s\S]*?)\n```/)?.[1];
    assert.ok(consumer);
    writeFileSync(join(directory, "inspect-topology.mjs"), consumer);
    const result = execFileSync(process.execPath, ["inspect-topology.mjs"], {
      cwd: directory,
      encoding: "utf8",
    });
    assert.match(result, /main 3 nodes/);
    assert.match(result, /Completeness: complete/);
    assert.match(result, /Limitation: dynamic-interrupts/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

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

  const document = await describe(compiled, { graphId: "linear-flow" });
  const graph = document.graphs[0];
  assert.ok(graph);
  assert.equal(validateDocument(document).valid, true);
  assert.equal(canonicalStringify(document), JSON.stringify(document));
  assert.equal(graph.name, "linear");
  assert.equal(graph.id, "linear-flow");
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
  const unknownDocument = await describe(unknown, { graphId: "routing" });
  assert.equal(unknownDocument.completeness.status, "incomplete");
  assert.deepEqual(unknownDocument.completeness.gaps, [
    {
      code: "unknown-routing-targets",
      message: "Not every destination of this router could be determined.",
      element: { graphId: "routing", kind: "node", id: "route" },
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

test("join identity uses the same Unicode order as Python", async () => {
  const document = await describe(
    new StateGraph(State)
      .addNode("\u{10000}", step)
      .addNode("\ue000", step)
      .addNode("joined", step)
      .addEdge(START, "\u{10000}")
      .addEdge(START, "\ue000")
      .addEdge(["\u{10000}", "\ue000"], "joined")
      .addEdge("joined", END)
      .compile(),
  );
  assert.equal(validateDocument(document).valid, true);
  assert.deepEqual(document.graphs[0]?.structure.joins, [
    {
      id: "join:\ue000+\u{10000}:joined",
      sources: ["\ue000", "\u{10000}"],
      target: "joined",
    },
  ]);
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
  const expanded = await describe(parent, {
    depth: 1,
    graphId: "parent-workflow",
  });
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
  assert.deepEqual(opaque.completeness, { status: "complete", gaps: [] });
  assert.deepEqual(expanded.completeness, {
    status: "incomplete",
    gaps: [
      {
        code: "expanded-subgraph-metadata",
        message:
          "Expanded child graphs expose drawable shape, but their join, routing, and interrupt declarations are not fully inspected.",
        element: {
          graphId: "parent-workflow",
          kind: "graph",
          id: "parent-workflow",
        },
      },
    ],
  });
  assert.equal(validateDocument(expanded).valid, true);
  assert.equal(
    (await describe(child, { depth: 1 })).completeness.status,
    "complete",
  );
});

test("rejects invalid caller-supplied graph ids", async () => {
  const compiled = new StateGraph(State)
    .addNode("step", step)
    .addEdge(START, "step")
    .addEdge("step", END)
    .compile();
  await assert.rejects(describe(compiled, { graphId: "" }), {
    name: "TypeError",
    message: "graphId must be a non-empty string",
  });
  await assert.rejects(
    describe(compiled, /** @type {any} */ ({ graphId: 1 })),
    {
      name: "TypeError",
      message: "graphId must be a non-empty string",
    },
  );
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

test("documented beta.2 migration retains gaps before consumer failure", () => {
  const packageRoot = fileURLToPath(new URL("../", import.meta.url));
  const directory = mkdtempSync(join(packageRoot, ".docs-migration-"));
  try {
    const guide = readFileSync(
      new URL("../../../../docs/guides/upgrading-beta.2.md", import.meta.url),
      "utf8",
    );
    const snippets = [...guide.matchAll(/```javascript\n([\s\S]*?)\n```/g)];
    assert.equal(snippets.length, 1);
    const source = snippets[0]?.[1];
    assert.ok(source);
    writeFileSync(join(directory, "upgrade.mjs"), source);
    const result = spawnSync(process.execPath, ["upgrade.mjs"], {
      cwd: directory,
      encoding: "utf8",
    });
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /Incomplete topology:/);
    const validation = validateDocument(JSON.parse(result.stdout));
    assert.ok(validation.valid);
    const document = validation.document;
    assert.equal(document.topologyVersion, "0.1");
    assert.equal(document.structureHash.algorithmVersion, "1");
    assert.deepEqual(document.structureHash, computeStructureHash(document));
    assert.equal(document.completeness.status, "incomplete");
    assert.deepEqual(
      document.completeness.gaps.map((gap) => gap.code),
      ["expanded-subgraph-metadata"],
    );
    assert.deepEqual(document.completeness.gaps[0]?.element, {
      graphId: "main",
      kind: "graph",
      id: "main",
    });
    assert.ok(document.producerLimitations.length > 0);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("built producer reads an independently bumped package manifest", async () => {
  const packageRoot = fileURLToPath(new URL("../", import.meta.url));
  const directory = mkdtempSync(join(packageRoot, ".version-fixture-"));
  try {
    cpSync(join(packageRoot, "dist"), join(directory, "dist"), {
      recursive: true,
    });
    writeFileSync(
      join(directory, "package.json"),
      JSON.stringify({
        type: "module",
        name: "@agent-topology/langgraph",
        version: "0.7.0-beta.3",
      }),
    );
    const { describe: describeFixture } = await import(
      join(directory, "dist/index.js")
    );
    const graph = new StateGraph(State)
      .addNode("step", step)
      .addEdge(START, "step")
      .addEdge("step", END)
      .compile();
    const document = await describeFixture(graph);
    assert.equal(document.provenance.producer.version, "0.7.0-beta.3");
    assert.equal(document.topologyVersion, "0.1");
    assert.equal(document.structureHash.algorithmVersion, "1");
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
