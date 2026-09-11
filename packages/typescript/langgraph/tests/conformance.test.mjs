import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { canonicalStringify, canonicalizeDocument } from "@agent-topology/spec";

import { describe } from "../dist/index.js";

const fixturesRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../conformance/fixtures",
);
const expectedCases = [
  "conditional-routing",
  "interrupt-before",
  "linear-flow",
  "loop",
  "multi-source-join",
  "nested-subgraph",
  "parallel-fanout",
  "unknown-routing-targets",
];
const State = Annotation.Root({ value: Annotation });
/** @param {Record<string, unknown>} state */
const step = (state) => state;

/** @param {string} value */
function nodeId(value) {
  return { $start: START, $end: END }[value] ?? value;
}

/** @param {any} recipe */
function compileFixture(recipe) {
  const builder = /** @type {any} */ (new StateGraph(State));
  for (const node of recipe.nodes) {
    builder.addNode(
      node.id,
      node.subgraph === undefined ? step : compileFixture(node.subgraph),
    );
  }
  for (const edge of recipe.directEdges ?? []) {
    builder.addEdge(nodeId(edge.source), nodeId(edge.target));
  }
  for (const route of recipe.conditionalRoutes ?? []) {
    const targets = route.targets;
    const normalizedTargets = /** @type {string[] | undefined} */ (
      targets?.map((/** @type {string} */ target) => nodeId(target))
    );
    builder.addConditionalEdges(
      route.source,
      () => normalizedTargets?.[0] ?? END,
      normalizedTargets === undefined
        ? undefined
        : Object.fromEntries(
            normalizedTargets.map((target) => [target, target]),
          ),
    );
  }
  for (const join of recipe.joins ?? []) {
    builder.addEdge(join.sources.map(nodeId), nodeId(join.target));
  }
  return builder.compile({
    interruptBefore: recipe.interruptBefore,
    interruptAfter: recipe.interruptAfter,
  });
}

/** @param {any} value @returns {any} */
function withoutExtensions(value) {
  if (Array.isArray(value)) return value.map(withoutExtensions);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !key.startsWith("x-"))
        .map(([key, item]) => [key, withoutExtensions(item)]),
    );
  }
  return value;
}

/** @param {any} document @param {string} fixtureCase */
function normalizeProducerDocument(document, fixtureCase) {
  const normalized = withoutExtensions(structuredClone(document));
  normalized.provenance = {
    framework: { name: "conformance-fixture", version: "1" },
    generatedAt: "2000-01-01T00:00:00Z",
    producer: { name: "agent-topology-conformance", version: "1" },
    source: { kind: "conformance-fixture", locator: fixtureCase },
  };
  normalized.producerLimitations = [];
  for (const graph of normalized.graphs) delete graph.name;
  return canonicalizeDocument(normalized);
}

const cases = (await readdir(fixturesRoot, { withFileTypes: true }))
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort();

test("the TypeScript runner covers every shared fixture", () => {
  assert.deepEqual(cases, expectedCases);
});

for (const fixtureCase of cases) {
  test(`shared conformance: ${fixtureCase}`, async () => {
    const fixtureDirectory = resolve(fixturesRoot, fixtureCase);
    const recipe = JSON.parse(
      await readFile(resolve(fixtureDirectory, "fixture.json"), "utf8"),
    );
    const expected = JSON.parse(
      await readFile(resolve(fixtureDirectory, "expected.json"), "utf8"),
    );
    const actual = normalizeProducerDocument(
      await describe(compileFixture(recipe)),
      fixtureCase,
    );

    assert.deepEqual(actual.graphs, expected.graphs, "core graph structure");
    assert.deepEqual(
      actual.structureHash,
      expected.structureHash,
      "structure hash",
    );
    assert.deepEqual(
      actual.completeness,
      expected.completeness,
      "completeness and gaps",
    );
    assert.deepEqual(
      actual.graphs.flatMap(
        (/** @type {any} */ graph) => graph.structure.joins,
      ),
      expected.graphs.flatMap(
        (/** @type {any} */ graph) => graph.structure.joins,
      ),
      "multi-source joins",
    );
    assert.deepEqual(actual, expected, "complete normalized document");
    assert.deepEqual(
      Buffer.from(canonicalStringify(actual)),
      Buffer.from(canonicalStringify(expected)),
      "canonical UTF-8 bytes",
    );
  });
}
