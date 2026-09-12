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
    new URL("../../../../conformance/sentinel-cases.json", import.meta.url),
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
  const child = recipe.child
    ? chain(
        [
          ["start", forbidden],
          ["__start__-user", forbidden],
        ],
        reverse,
      )
    : undefined;
  return chain(
    recipe.nodes.map(
      /** @param {string} n */ (n) => [
        n,
        n === "child" && child ? child : forbidden,
      ],
    ),
    reverse,
  );
}
/** @param {any} document */
function meaning(document) {
  return Object.fromEntries(
    document.graphs[0][key].nodes.map(
      /** @param {any} record */ (record) => {
        const fact = structuredClone(record.sentinel);
        if (fact.evidence) {
          assert.equal(
            fact.evidence.source,
            fact.evidence.kind === "ordinary-node"
              ? "compiled.builder.nodes.runnable"
              : "compiled.inputChannels+getGraphAsync.reserved-sentinels",
          );
          delete fact.evidence.source;
        }
        return [record.nodeId, fact];
      },
    ),
  );
}
for (const recipe of cases) {
  test(`sentinel ${recipe.name}`, async () => {
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
for (const nodeId of [START, END, "task"])
  for (const depth of [0, 1, 2]) {
    test(`failed visible identity ${nodeId} depth ${depth}`, async () => {
      const compiled = compileCase({ nodes: ["task"] });
      const drawable = await compiled.getGraphAsync({ xray: depth });
      drawable.nodes[nodeId].data = {};
      compiled.getGraphAsync = async () => drawable;
      const document = await describe(compiled, { depth });
      assert.deepEqual(meaning(document)[nodeId], {
        status: "unknown",
        reason:
          depth > 0 && nodeId === "task"
            ? "scope-not-inspected"
            : "identity-unavailable",
      });
      assert.equal(interpretationStatus(document), "valid");
    });
  }
test("failed framework ownership", async () => {
  const compiled = compileCase({ nodes: ["task"] });
  const drawable = await compiled.getGraphAsync();
  compiled.getGraphAsync = async () => drawable;
  compiled.inputChannels = "unavailable";
  const facts = meaning(await describe(compiled));
  for (const id of [START, END])
    assert.deepEqual(facts[id], {
      status: "unknown",
      reason: "identity-unavailable",
    });
  assert.equal(facts.task.value, "ordinary");
});
test("reserved IDs cannot be user nodes", () => {
  for (const id of [START, END])
    assert.throws(() =>
      /** @type {any} */ (new StateGraph(State)).addNode(id, forbidden),
    );
});

test("producer sentinel documents agree across languages and preserve consumer provenance", async () => {
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
    "suite = runpy.run_path('packages/python/langgraph/tests/test_sentinel.py')",
    "consumer = runpy.run_path('spec/tests/test_sentinel_consumer.py')",
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
          const fact = structuredClone(r.sentinel);
          if (fact.evidence) delete fact.evidence.source;
          return [r.nodeId, fact];
        },
      ),
    );
    assert.deepEqual(facts, meaning(document));
    assert.deepEqual(facts, cases[index].expected);
  });
});
