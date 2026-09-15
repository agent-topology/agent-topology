import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { Annotation, StateGraph, START, END, Send } from "@langchain/langgraph";
import {
  canonicalStringify,
  computeStructureHash,
  validateDocument,
} from "@agent-topology/spec";
import { RunnableLambda } from "@langchain/core/runnables";
import { describe } from "../dist/index.js";
const { interpretationStatus } = await import(
  new URL("../../spec/tests/interpretation-helper.mjs", import.meta.url).href
);

const cases = JSON.parse(
  readFileSync(
    new URL("../../../../conformance/branch-cases.json", import.meta.url),
    "utf8",
  ),
);
const key = "x-topology-interpretation";
const State = Annotation.Root({ value: Annotation });
/** @returns {never} */
function forbidden() {
  throw new Error("user node executed");
}
/** @param {string} mode @returns {() => string | string[] | Send[]} */
function router(mode) {
  /** @returns {"left" | "right"} */
  function single() {
    throw new Error("single router executed");
    return "left";
  }
  /** @returns {Array<"left" | "right">} */
  function multiple() {
    throw new Error("list router executed");
    return ["left", "right"];
  }
  function send() {
    throw new Error("Send router executed");
    return [new Send("left", {}), new Send("right", {})];
  }
  return mode === "send"
    ? send
    : ["list", "annotated-list"].includes(mode)
      ? multiple
      : single;
}
/** @param {any} recipe @param {boolean} reverse */
function compileCase(recipe, reverse = false) {
  const builder = new StateGraph(State);
  /** @param {any[]} values */
  const ordered = (values) => (reverse ? [...values].reverse() : values);
  for (const name of ordered(recipe.nodes)) {
    builder.addNode(
      name,
      forbidden,
      recipe.dynamic && name in recipe.dynamic
        ? { ends: recipe.dynamic[name] }
        : {},
    );
  }
  for (const [source, target] of ordered(recipe.edges))
    builder.addEdge(source, target);
  for (const [sources, target] of ordered(recipe.joins ?? []))
    builder.addEdge(ordered(sources), target);
  for (const route of ordered(recipe.routers ?? [])) {
    const path = RunnableLambda.from(router(route.mode));
    path.name = route.mode;
    builder.addConditionalEdges(route.source, path, route.targets);
  }
  return builder.compile();
}
/** @param {any} document */
function meaning(document) {
  const records = structuredClone(document.graphs[0][key].nodes).filter(
    /** @param {any} record */ (record) => record.branch !== undefined,
  );
  for (const record of records) {
    if (record.branch.evidence) {
      assert.equal(
        record.branch.evidence.source,
        "compiled.builder.edges+branches+nodes.ends",
      );
      delete record.branch.evidence.source;
    }
  }
  return Object.fromEntries(
    records.map(
      /** @param {any} record */ (record) => [record.nodeId, record.branch],
    ),
  );
}
/** @param {any} document @param {number} depth */
function check(document, depth) {
  assert.equal(validateDocument(document).valid, true);
  assert.equal(interpretationStatus(document), "valid");
  assert.equal(document.graphs[0][key].traversalDepth, depth);
  const stripped = structuredClone(document);
  delete stripped.graphs[0][key];
  assert.deepEqual(computeStructureHash(stripped), document.structureHash);
  assert.equal(document.structureHash.algorithmVersion, "1");
  assert.equal(document.provenance.framework.version, "1.4.14");
}
for (const recipe of cases) {
  for (const depth of [0, 1, 2]) {
    test(`branch: ${recipe.name}, depth ${depth}`, async () => {
      const document = await describe(compileCase(recipe), { depth });
      check(document, depth);
      assert.deepEqual(meaning(document), recipe.expected);
      const reversed = await describe(compileCase(recipe, true), { depth });
      reversed.provenance = document.provenance;
      assert.equal(canonicalStringify(reversed), canonicalStringify(document));
    });
  }
}
for (const nesting of [1, 2]) {
  for (const depth of [0, 1, 2]) {
    test(`expanded child branch scope at depth ${depth}, nesting ${nesting}`, async () => {
      const leaf = compileCase(cases[0]);
      const child =
        nesting === 2
          ? new StateGraph(State)
              .addNode("inner", leaf)
              .addEdge(START, "inner")
              .addEdge("inner", END)
              .compile()
          : leaf;
      const builder = new StateGraph(State)
        .addNode("child", child)
        .addNode("retained", forbidden)
        .addNode("left", forbidden)
        .addNode("right", forbidden)
        .addEdge(START, "child")
        .addEdge("child", "retained")
        .addEdge("retained", "left")
        .addEdge("retained", "right")
        .addEdge("left", END)
        .addEdge("right", END);
      const document = await describe(builder.compile(), { depth });
      check(document, depth);
      const facts = meaning(document);
      assert.equal(facts.retained.value, "all-declared");
      delete facts.retained;
      // Branch/sentinel/entry facts for a materialized child's own nodes are
      // populated by #140, not here: root's own extension never leaks them.
      assert.deepEqual(facts, {});
      assert.ok(
        !document.completeness.gaps.some(
          (gap) => gap.code === "expanded-subgraph-metadata",
        ),
      );
      const childNode = document.graphs[0].structure.nodes.find(
        (n) => n.id === "child",
      );
      if (depth >= 1) {
        assert.equal(childNode.subgraphId, "main:child");
        const expectedGraphs = nesting === 1 || depth < 2 ? 2 : 3;
        assert.equal(document.graphs.length, expectedGraphs);
      } else {
        assert.equal(childNode.subgraphId, undefined);
        assert.equal(document.graphs.length, 1);
      }
    });
  }
}
for (const depth of [0, 1, 2]) {
  test(`rewritten root branch at depth ${depth}`, async () => {
    const child = new StateGraph(State)
      .addNode("step", forbidden)
      .addNode("next", forbidden)
      .addEdge(START, "step")
      .addEdge("step", "next")
      .addEdge("next", END)
      .compile();
    const outer = new StateGraph(State)
      .addNode("child", child)
      .addNode("right", forbidden)
      .addEdge(START, "child")
      .addEdge(START, "right")
      .addEdge("child", END)
      .addEdge("right", END)
      .compile();
    const document = await describe(outer, { depth });
    check(document, depth);
    // Root's own branch facts are unaffected by materialization at any depth:
    // the framework's flattening view is never consulted anymore.
    assert.deepEqual(meaning(document)[START], cases[0].expected.router);
  });
}

for (const name of ["linear", "single", "mixed-unknown"]) {
  test(`document validator rejects unjustified branch: ${name}`, async () => {
    const recipe = cases.find(
      /** @param {any} recipe */ (recipe) => recipe.name === name,
    );
    const document = await describe(compileCase(recipe));
    const extension = /** @type {any} */ (document.graphs[0]?.[key]);
    extension.nodes = [
      {
        nodeId: name === "linear" ? "step" : "router",
        branch: {
          ...cases[0].expected.router,
          evidence: { kind: "unconditional-edges", source: "authored-test" },
        },
      },
    ];
    assert.equal(validateDocument(document).valid, true);
    assert.equal(interpretationStatus(document), "invalid");
  });
}
test("hidden dynamic declarations require producer conformance", async () => {
  const recipe = cases.find(
    /** @param {any} recipe */ (recipe) => recipe.name === "dynamic-empty",
  );
  const document = await describe(compileCase(recipe));
  assert.equal(meaning(document).router.status, "unknown");
  const extension = /** @type {any} */ (document.graphs[0]?.[key]);
  extension.nodes.find(
    /** @param {any} r */ (r) => r.nodeId === "router",
  ).branch = {
    ...cases[0].expected.router,
    evidence: { kind: "unconditional-edges", source: "authored-test" },
  };
  // A document alone cannot refute this lie; the real graph test above does.
  assert.equal(interpretationStatus(document), "valid");
});
