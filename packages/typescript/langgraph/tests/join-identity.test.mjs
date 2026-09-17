// Join identity fixes for issue #182.
//
// conformance/fixtures/join-permuted-sources and join-repeated-declaration
// cover the shared, cross-language-equal dedup cases (see
// conformance/README.md). This file covers what cannot be a shared fixture:
// JavaScript's delimiter-bearing collision disposition (unlike Python, it
// does not fail upstream), general declaration-order stability for
// genuinely distinct joins, and a negative control against over-eager
// deduplication. See ADR 0014.

import assert from "node:assert/strict";
import { test } from "node:test";

import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { canonicalStringify, validateDocument } from "@agent-topology/spec";

import { describe } from "../dist/index.js";

const concat = /** @type {(a: string[], b: string[]) => string[]} */ (
  (a, b) => a.concat(b)
);
const State = Annotation.Root({
  values: Annotation({
    reducer: concat,
    default: () => /** @type {string[]} */ ([]),
  }),
});
/** @returns {{values: never[]}} */
const step = () => ({ values: [] });

test("delimiter-bearing distinct source sets stay distinct and valid", async () => {
  const names = [...new Set(["a", "a+b", "b+c", "c"])].sort().concat("sink");
  const builder = /** @type {any} */ (new StateGraph(State));
  for (const name of names) {
    builder.addNode(name, step);
    if (name !== "sink") builder.addEdge(START, name);
  }
  builder.addEdge(["a+b", "c"], "sink");
  builder.addEdge(["a", "b+c"], "sink");
  builder.addEdge("sink", END);

  const document = await describe(builder.compile());
  const validation = validateDocument(document);

  assert.ok(validation.valid, JSON.stringify(validation));
  const ids = document.graphs[0].structure.joins
    .map((/** @type {any} */ join) => join.id)
    .sort();
  assert.deepEqual(ids, ["join:a+b\\+c:sink", "join:a\\+b+c:sink"]);
});

test("reversed join declaration order yields identical document", async () => {
  /** @param {boolean} reverse */
  async function build(reverse) {
    const builder = /** @type {any} */ (new StateGraph(State));
    for (const name of ["a", "b", "c", "left", "right"]) {
      builder.addNode(name, step);
    }
    builder.addEdge(START, "a");
    builder.addEdge(START, "b");
    builder.addEdge(START, "c");
    const declarations = [
      [["a", "b"], "left"],
      [["b", "c"], "right"],
    ];
    for (const [sources, target] of reverse
      ? [...declarations].reverse()
      : declarations) {
      builder.addEdge(sources, target);
    }
    builder.addEdge("left", END);
    builder.addEdge("right", END);
    return describe(builder.compile());
  }

  const forward = await build(false);
  const reversed = await build(true);
  reversed.provenance = forward.provenance;

  assert.equal(canonicalStringify(forward), canonicalStringify(reversed));
  assert.ok(validateDocument(forward).valid);
  const ids = forward.graphs[0].structure.joins
    .map((/** @type {any} */ join) => join.id)
    .sort();
  assert.deepEqual(ids, ["join:a+b:left", "join:b+c:right"]);
});

test("distinct source sets sharing a source and target stay distinct", async () => {
  const builder = /** @type {any} */ (new StateGraph(State));
  for (const name of ["a", "b", "c", "sink"]) builder.addNode(name, step);
  builder.addEdge(START, "a");
  builder.addEdge(START, "b");
  builder.addEdge(START, "c");
  builder.addEdge(["a", "b"], "sink");
  builder.addEdge(["a", "c"], "sink");
  builder.addEdge("sink", END);

  const document = await describe(builder.compile());

  assert.ok(validateDocument(document).valid);
  const ids = document.graphs[0].structure.joins
    .map((/** @type {any} */ join) => join.id)
    .sort();
  assert.deepEqual(ids, ["join:a+b:sink", "join:a+c:sink"]);
});
