import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { derivedJoinEdges, validateDocument } from "../dist/index.js";

const cases = JSON.parse(
  readFileSync(
    new URL("../../../../spec/derived-join-edges-cases.json", import.meta.url),
    "utf8",
  ),
);
const base = JSON.parse(
  readFileSync(
    new URL(
      "../../../../conformance/fixtures/linear-flow/expected.json",
      import.meta.url,
    ),
    "utf8",
  ),
);

for (const fixture of cases) {
  test(`shared join connections: ${fixture.name}`, () => {
    /** @type {import("../dist/index.js").GraphStructure} */
    const structure = structuredClone(fixture.structure);
    const document = structuredClone(base);
    document.graphs[0].structure = structure;
    assert.equal(validateDocument(document).valid, true);
    const original = structuredClone(structure);
    const links = derivedJoinEdges(structure);
    assert.deepEqual(links, fixture.expected);
    assert.deepEqual(structure, original);
    const again = derivedJoinEdges(structure);
    assert.notEqual(again, links);
    links.forEach((link, index) => assert.notEqual(link, again[index]));
    if (links[0]) {
      links[0].source = "changed";
      assert.deepEqual(again, fixture.expected);
      assert.deepEqual(structure, original);
    }
    structure.joins.reverse();
    structure.nodes.reverse();
    structure.edges.reverse();
    structure.joins.forEach((join) => join.sources.reverse());
    const reordered = structuredClone(structure);
    assert.deepEqual(derivedJoinEdges(structure), fixture.expected);
    assert.deepEqual(structure, reordered);
  });
}
