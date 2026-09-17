// Ad-hoc verification of beta.5 producer behavior against the clean-installed
// @agent-topology/langgraph-0.1.0-beta.5 tarball (not the source tree).
// Exercises join-identity dedup/escaping (issue #182 / ADR 0015) and the
// exact-version refusal against @langchain/langgraph. Not part of the
// committed test suite.

import assert from "node:assert/strict";

import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { canonicalStringify, validateDocument } from "@agent-topology/spec";
import { describe, UnsupportedLangGraphVersionError } from "@agent-topology/langgraph";
import langGraphPackage from "@langchain/langgraph/package.json" with { type: "json" };

const concat = (a, b) => a.concat(b);
const State = Annotation.Root({
  values: Annotation({ reducer: concat, default: () => [] }),
});
const step = () => ({ values: [] });

async function checkRepeatedJoinDedup() {
  const builder = new StateGraph(State);
  for (const name of ["a", "b", "sink"]) builder.addNode(name, step);
  builder.addEdge(START, "a");
  builder.addEdge(START, "b");
  builder.addEdge(["a", "b"], "sink");
  builder.addEdge(["a", "b"], "sink");
  builder.addEdge("sink", END);
  const document = await describe(builder.compile());
  const validation = validateDocument(document);
  assert.ok(validation.valid, JSON.stringify(validation));
  const joins = document.graphs[0].structure.joins;
  assert.equal(joins.length, 1, JSON.stringify(joins));
  assert.equal(joins[0].id, "join:a+b:sink", JSON.stringify(joins));
  console.log("OK repeated-join-declaration dedup ->", joins[0].id);
}

async function checkPermutedJoinDedup() {
  const builder = new StateGraph(State);
  for (const name of ["a", "b", "sink"]) builder.addNode(name, step);
  builder.addEdge(START, "a");
  builder.addEdge(START, "b");
  builder.addEdge(["a", "b"], "sink");
  builder.addEdge(["b", "a"], "sink");
  builder.addEdge("sink", END);
  const document = await describe(builder.compile());
  const validation = validateDocument(document);
  assert.ok(validation.valid, JSON.stringify(validation));
  const joins = document.graphs[0].structure.joins;
  assert.equal(joins.length, 1, JSON.stringify(joins));
  assert.equal(joins[0].id, "join:a+b:sink", JSON.stringify(joins));
  console.log("OK permuted-join-declaration dedup ->", joins[0].id);
}

async function checkDelimiterEscaping() {
  const names = [...new Set(["a", "a+b", "b+c", "c"])].sort().concat("sink");
  const builder = new StateGraph(State);
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
  const ids = document.graphs[0].structure.joins.map((j) => j.id).sort();
  assert.deepEqual(ids, ["join:a+b\\+c:sink", "join:a\\+b+c:sink"]);
  console.log("OK delimiter-bearing distinct source sets stay distinct ->", ids);
  const canonical = canonicalStringify(document);
  assert.equal(typeof canonical, "string");
  console.log("OK canonicalStringify succeeds on installed artifact output");
}

async function checkVersionRefusal() {
  assert.equal(langGraphPackage.version, "1.4.15-rc.0", langGraphPackage.version);
  const builder = new StateGraph(State);
  builder.addNode("step", step);
  builder.addEdge(START, "step");
  builder.addEdge("step", END);
  await assert.rejects(
    async () => describe(builder.compile()),
    (error) => {
      assert.ok(error instanceof UnsupportedLangGraphVersionError, error);
      console.log("OK refused on @langchain/langgraph@1.4.15-rc.0:", error.message);
      return true;
    },
  );
}

const mode = process.argv[2];
if (mode === "behavior") {
  await checkRepeatedJoinDedup();
  await checkPermutedJoinDedup();
  await checkDelimiterEscaping();
  console.log("ALL INSTALLED-ARTIFACT BEHAVIOR CHECKS PASSED");
} else if (mode === "refusal") {
  await checkVersionRefusal();
  console.log("VERSION REFUSAL CHECK PASSED");
} else {
  throw new Error("usage: node verify_ts_installed_behavior.mjs <behavior|refusal>");
}
