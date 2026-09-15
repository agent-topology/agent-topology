import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { Annotation, StateGraph, START, END } from "@langchain/langgraph";
import {
  canonicalStringify,
  computeStructureHash,
  validateDocument,
} from "@agent-topology/spec";
import { describe } from "../dist/index.js";
const { interpretationStatus } = await import(
  new URL("../../spec/tests/interpretation-helper.mjs", import.meta.url).href
);

const key = "x-topology-interpretation";
const State = Annotation.Root({ value: Annotation });
const cases = JSON.parse(
  readFileSync(
    new URL("../../../../conformance/entry-cases.json", import.meta.url),
    "utf8",
  ),
);
function forbidden() {
  throw new Error("user function executed");
}
/** @param {Array<[string, any]>} nodes @param {boolean} reverse */
function chain(nodes, reverse = false) {
  const builder = /** @type {any} */ (new StateGraph(State));
  for (const [name, runnable] of reverse ? [...nodes].reverse() : nodes)
    builder.addNode(name, runnable);
  const names = nodes.map(([n]) => n);
  const targets = [...names, END];
  const edges = [START, ...names].map((source, i) => [source, targets[i]]);
  for (const [source, target] of reverse ? edges.reverse() : edges)
    builder.addEdge(source, target);
  return builder.compile();
}
/** @param {any} recipe @param {boolean} reverse */
function compileCase(recipe, reverse = false) {
  const builder = /** @type {any} */ (new StateGraph(State));
  /** @param {any[]} values */
  const ordered = (values) => (reverse ? [...values].reverse() : values);
  const child = recipe.child
    ? chain(
        [
          ["start", forbidden],
          ["__start__-user", forbidden],
        ],
        reverse,
      )
    : undefined;
  for (const name of ordered(recipe.nodes))
    builder.addNode(name, name === "child" && child ? child : forbidden);
  for (const [source, target] of ordered(recipe.edges))
    builder.addEdge(source, target);
  for (const [sources, target] of ordered(recipe.joins ?? []))
    builder.addEdge(ordered(sources), target);
  if (recipe.startTargets)
    builder.addConditionalEdges(START, forbidden, recipe.startTargets);
  for (const source of ordered(recipe.routers ?? []))
    builder.addConditionalEdges(source, forbidden);
  return builder.compile();
}
/** @param {any} document */
function meaning(document) {
  return Object.fromEntries(
    document.graphs[0][key].nodes.map(
      /** @param {any} record */ (record) => {
        const fact = structuredClone(record.entry);
        if (fact.evidence) {
          assert.equal(
            fact.evidence.source,
            "compiled.inputChannels+getGraphAsync.reserved-sentinels",
          );
          delete fact.evidence.source;
        }
        return [record.nodeId, fact];
      },
    ),
  );
}
for (const recipe of cases) {
  test(`entry ${recipe.name}`, async () => {
    const depth = recipe.depth ?? 0;
    const document = await describe(compileCase(recipe), { depth });
    assert.equal(validateDocument(document).valid, true);
    assert.equal(interpretationStatus(document), "valid");
    assert.equal(document.provenance.framework.version, "1.4.14");
    assert.equal(
      /** @type {any} */ (document.graphs[0][key]).traversalDepth,
      depth,
    );
    assert.deepEqual(meaning(document), recipe.expected);
    const reversed = await describe(compileCase(recipe, true), { depth });
    reversed.provenance = document.provenance;
    assert.equal(canonicalStringify(reversed), canonicalStringify(document));
    const stripped = structuredClone(document);
    delete stripped.graphs[0][key];
    assert.deepEqual(computeStructureHash(stripped), document.structureHash);
    assert.equal(document.structureHash.algorithmVersion, "1");
  });
}
test("materialized child entries", async () => {
  const child = chain([
    ["start", forbidden],
    ["__start__-user", forbidden],
  ]);
  const document = await describe(chain([["child", child]]), { depth: 1 });
  const childGraph = document.graphs.find((g) => g.id === "main:child");
  assert.ok(childGraph);
  const records = Object.fromEntries(
    /** @type {any} */ (childGraph[key]).nodes.map(
      /** @param {any} r */ (r) => [r.nodeId, r],
    ),
  );
  assert.equal(records[START].entry.value, "confirmed");
  assert.equal(records[END].entry.value, "not-entry");
  assert.equal(records["start"].entry.status, "unknown");
  assert.equal(records["start"].entry.observedRoot, false);
  assert.equal(interpretationStatus(document), "valid");
});
for (const nodeId of [START, END, "task"])
  for (const depth of [0, 1, 2]) {
    test(`failed visible identity ${nodeId} depth ${depth}`, async () => {
      const compiled = chain([["task", forbidden]]);
      const drawable = await compiled.getGraphAsync({ xray: depth });
      drawable.nodes[nodeId].data = {};
      compiled.getGraphAsync = async () => drawable;
      const document = await describe(compiled, { depth });
      assert.deepEqual(meaning(document)[nodeId], {
        status: "unknown",
        reason: depth > 0 ? "scope-not-inspected" : "entry-not-established",
        observedRoot: nodeId === START,
      });
      assert.equal(interpretationStatus(document), "valid");
    });
  }
test("failed framework ownership", async () => {
  const compiled = chain([["task", forbidden]]);
  const drawable = await compiled.getGraphAsync();
  compiled.getGraphAsync = async () => drawable;
  compiled.inputChannels = "unavailable";
  const facts = meaning(await describe(compiled));
  assert.ok(Object.values(facts).every((fact) => fact.status === "unknown"));
});

for (const recipe of cases.filter(/** @param {any} c */ (c) => c.routers)) {
  test(`entry no inferred causality ${recipe.name}`, async () => {
    const document = await describe(compileCase(recipe));
    assert.deepEqual(document.graphs[0].structure.entryNodeIds, [
      START,
      "target",
    ]);
    assert.deepEqual(
      document.completeness.gaps.map((gap) => gap.element.id).sort(),
      [...recipe.routers].sort(),
    );
    assert.ok(
      document.completeness.gaps.every(
        (gap) => gap.code === "unknown-routing-targets",
      ),
    );
    assert.deepEqual(meaning(document).target, {
      status: "unknown",
      reason: "entry-not-established",
      observedRoot: true,
    });
  });
}

test("producer entry documents agree across languages and preserve consumer provenance", async () => {
  const documents = await Promise.all(
    cases.map(
      /** @param {any} recipe */ (recipe) =>
        describe(compileCase(recipe), { depth: recipe.depth ?? 0 }),
    ),
  );
  const root = fileURLToPath(new URL("../../../../", import.meta.url));
  const script = [
    "import json, runpy, sys",
    "from agent_topology.spec import canonical_json, compute_structure_hash, validate_document",
    "suite = runpy.run_path('packages/python/langgraph/tests/test_entry.py')",
    "consumer = runpy.run_path('spec/tests/test_entry_consumer.py')",
    "incoming = json.load(sys.stdin)",
    "assert all(not validate_document(d) and suite['ORACLE'](d) == 'valid' for d in incoming)",
    "produced = [suite['describe'](suite['compile_case'](c), depth=c.get('depth', 0)) for c in suite['CASES']]",
    "[consumer['assert_preserved'](d) for d in incoming + produced]",
    "json.dump({'documents': produced, 'canonical': [canonical_json(d) for d in incoming], 'hashes': [compute_structure_hash(d) for d in incoming]}, sys.stdout)",
  ].join("; ");
  const result = spawnSync(
    "uv",
    [
      "run",
      "--project",
      "packages/python/langgraph",
      "--group",
      "test",
      "python",
      "-c",
      script,
    ],
    { cwd: root, encoding: "utf8", input: JSON.stringify(documents) },
  );
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const evidence = JSON.parse(result.stdout);
  documents.forEach((document, index) => {
    assert.equal(canonicalStringify(document), evidence.canonical[index]);
    assert.deepEqual(computeStructureHash(document), evidence.hashes[index]);
    const python = evidence.documents[index];
    assert.equal(validateDocument(python).valid, true);
    assert.equal(interpretationStatus(python), "valid");
    const facts = Object.fromEntries(
      python.graphs[0][key].nodes.map(
        /** @param {any} r */ (r) => {
          const fact = structuredClone(r.entry);
          if (fact.evidence) delete fact.evidence.source;
          return [r.nodeId, fact];
        },
      ),
    );
    assert.deepEqual(facts, meaning(document));
    assert.deepEqual(facts, cases[index].expected);
  });
});
