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
    new URL("../../../../conformance/subgraph-cases.json", import.meta.url),
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
  const names = nodes.map(([name]) => name);
  const sources = [START, ...names];
  const targets = [...names, END];
  const edges = sources.map((source, i) => [source, targets[i]]);
  for (const [source, target] of reverse ? edges.reverse() : edges)
    builder.addEdge(source, target);
  return builder.compile();
}
/** @param {string} mode @param {boolean} reverse @param {number} width */
function compileCase(mode, reverse = false, width = 1) {
  let child = chain(
    ["step", "next"].slice(0, width).map((name) => [name, forbidden]),
    reverse,
  );
  if (mode === "grandchild") child = chain([["inner", child]], reverse);
  const hidden = child;
  function wrapper() {
    throw new Error("wrapper executed");
    return hidden.invoke({});
  }
  return chain(
    [
      [
        "child",
        mode === "ordinary" ? forbidden : mode === "wrapper" ? wrapper : child,
      ],
    ],
    reverse,
  );
}
/** @param {any} document */
function meaning(document) {
  const result = /** @type {Record<string, any>} */ ({});
  for (const record of document.graphs[0][key].nodes) {
    if (!record.subgraph) continue;
    const fact = structuredClone(record.subgraph);
    if (fact.evidence) {
      assert.equal(fact.evidence.source, "compiled.builder.nodes.runnable");
      delete fact.evidence.source;
    }
    result[record.nodeId] = fact;
  }
  return result;
}
for (const recipe of cases) {
  test(`subgraph ${recipe.mode}, depth ${recipe.depth}`, async () => {
    const document = await describe(
      compileCase(recipe.mode, false, recipe.width ?? 1),
      { depth: recipe.depth },
    );
    assert.equal(validateDocument(document).valid, true);
    assert.equal(interpretationStatus(document), "valid");
    assert.equal(document.provenance.framework.version, "1.4.14");
    assert.equal(
      /** @type {any} */ (document.graphs[0][key]).traversalDepth,
      recipe.depth,
    );
    assert.deepEqual(
      meaning(document),
      recipe.typescriptExpected ?? recipe.expected,
    );
    const reversed = await describe(
      compileCase(recipe.mode, true, recipe.width ?? 1),
      { depth: recipe.depth },
    );
    reversed.provenance = document.provenance;
    assert.equal(canonicalStringify(reversed), canonicalStringify(document));
    const stripped = structuredClone(document);
    delete stripped.graphs[0][key];
    assert.deepEqual(computeStructureHash(stripped), document.structureHash);
    assert.equal(document.structureHash.algorithmVersion, "1");
    assert.equal(document.graphs.length, 1);
    assert.ok(
      document.graphs[0].structure.nodes.every(
        (n) => n.subgraphId === undefined,
      ),
    );
  });
}
for (const mode of ["child", "grandchild"])
  for (const depth of [1, 2]) {
    test(`expanded child scope ${mode}, depth ${depth}`, async () => {
      const document = await describe(compileCase(mode, false, 2), { depth });
      assert.equal(validateDocument(document).valid, true);
      assert.equal(interpretationStatus(document), "valid");
      const facts = meaning(document);
      if (mode === "grandchild" && depth === 1) {
        assert.equal(facts.child.value, "opaque-child");
        return;
      }
      assert.equal(facts.child, undefined);
      assert.ok(Object.keys(facts).length);
      for (const fact of Object.values(facts))
        assert.deepEqual(fact, {
          status: "unknown",
          reason: "scope-not-inspected",
        });
      assert.ok(
        document.completeness.gaps.some(
          (g) => g.code === "expanded-subgraph-metadata",
        ),
      );
    });
  }
test("retained identity preserves branch facts", async () => {
  const child = chain([
    ["step", forbidden],
    ["next", forbidden],
  ]);
  const builder = /** @type {any} */ (new StateGraph(State));
  for (const [name, runnable] of /** @type {Array<[string, any]>} */ ([
    ["child", child],
    ["retained", forbidden],
    ["left", forbidden],
    ["right", forbidden],
  ]))
    builder.addNode(name, runnable);
  for (const [source, target] of [
    [START, "child"],
    ["child", "retained"],
    ["retained", "left"],
    ["retained", "right"],
    ["left", END],
    ["right", END],
  ])
    builder.addEdge(source, target);
  for (const depth of [0, 1, 2]) {
    const document = await describe(builder.compile(), { depth });
    const records = /** @type {any} */ (document.graphs[0][key]).nodes;
    const retained = records.find(
      /** @param {any} r */ (r) => r.nodeId === "retained",
    );
    assert.equal(retained.branch.value, "all-declared");
    assert.deepEqual(retained.subgraph, {
      status: "unknown",
      reason: "identity-unavailable",
    });
    assert.equal(interpretationStatus(document), "valid");
  }
});
for (const depth of [1, 2]) {
  test(`positive depth ${depth} can remain opaque`, async () => {
    const compiled = compileCase("child");
    const drawable = await compiled.getGraphAsync({ xray: 0 });
    // Controlled framework traversal fallback over a real compiled child.
    compiled.getGraphAsync = async () => drawable;
    const document = await describe(compiled, { depth });
    assert.equal(meaning(document).child.value, "opaque-child");
    assert.equal(interpretationStatus(document), "valid");
  });
}
test("opaque assertion conflicts with a materialized reference", async () => {
  const document = await describe(compileCase("child"));
  const child = structuredClone(document.graphs[0]);
  child.id = "materialized";
  delete child[key];
  document.graphs.push(child);
  const node = document.graphs[0].structure.nodes.find((n) => n.id === "child");
  assert.ok(node);
  node.subgraphId = "materialized";
  assert.equal(validateDocument(document).valid, true);
  assert.equal(interpretationStatus(document), "invalid");
});

test("display name and core shape do not establish child identity", async () => {
  const child = await describe(compileCase("child"));
  const ordinary = await describe(compileCase("ordinary"));
  assert.deepEqual(child.graphs[0].structure, ordinary.graphs[0].structure);
  assert.deepEqual(child.structureHash, ordinary.structureHash);
  assert.equal(meaning(child).child.value, "opaque-child");
  assert.deepEqual(meaning(ordinary).child, {
    status: "unknown",
    reason: "identity-unavailable",
  });
});

test("real producer documents validate and canonicalize across languages", async () => {
  const documents = await Promise.all(
    cases.map(
      /** @param {any} recipe */ (recipe) =>
        describe(compileCase(recipe.mode, false, recipe.width ?? 1), {
          depth: recipe.depth,
        }),
    ),
  );
  const root = fileURLToPath(new URL("../../../../", import.meta.url));
  const script = [
    "import json, runpy, sys",
    "from agent_topology.spec import canonical_json, compute_structure_hash, validate_document",
    "suite = runpy.run_path('packages/python/langgraph/tests/test_subgraph.py')",
    "incoming = json.load(sys.stdin)",
    "assert all(not validate_document(d) and suite['ORACLE'](d) == 'valid' for d in incoming)",
    "produced = [suite['describe'](suite['compile_case'](c['mode'], width=c.get('width', 1)), depth=c['depth']) for c in suite['CASES']]",
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
    {
      cwd: root,
      encoding: "utf8",
      input: JSON.stringify(documents),
    },
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
    // Evidence source locators and provenance are deliberately language-specific.
    const records = structuredClone(python.graphs[0][key].nodes);
    for (const record of records)
      if (record.subgraph?.evidence) delete record.subgraph.evidence.source;
    const pythonMeaning = Object.fromEntries(
      records
        .filter(/** @param {any} r */ (r) => r.subgraph)
        .map(/** @param {any} r */ (r) => [r.nodeId, r.subgraph]),
    );
    assert.deepEqual(pythonMeaning, cases[index].expected);
    if (!cases[index].typescriptExpected)
      assert.deepEqual(meaning(document), pythonMeaning);
  });
});
