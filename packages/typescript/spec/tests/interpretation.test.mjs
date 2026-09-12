import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { Ajv2020 } from "ajv/dist/2020.js";
import {
  canonicalStringify,
  computeStructureHash,
  validateDocument,
} from "../dist/index.js";

import { interpretationStatus } from "./interpretation-helper.mjs";

// Authored ADR examples: these are not producer output or a public validator.
const root = new URL("../../../../spec/experimental/", import.meta.url);
const cases = JSON.parse(
  readFileSync(new URL("interpretation-cases.json", root), "utf8"),
);
const schema = JSON.parse(
  readFileSync(new URL("interpretation-v1.schema.json", root), "utf8"),
);
const validateExtension = new Ajv2020({ strict: false }).compile(schema);
const key = "x-topology-interpretation";

for (const example of cases) {
  test(`ADR 0008 core/hash/shape: ${example.name}`, () => {
    const document = example.document;
    assert.equal(interpretationStatus(document), example.extensionStatus);
    assert.equal(validateDocument(document).valid, true);
    assert.deepEqual(computeStructureHash(document), document.structureHash);
    assert.equal(
      createHash("sha256").update(canonicalStringify(document)).digest("hex"),
      example.canonicalSha256,
    );
    for (const graph of document.graphs) {
      if (key in graph) {
        assert.equal(validateExtension(graph[key]), example.shapeValid);
      }
    }
    const stripped = structuredClone(document);
    delete stripped[key];
    for (const graph of stripped.graphs) delete graph[key];
    assert.deepEqual(
      computeStructureHash(document),
      computeStructureHash(stripped),
    );
    assert.equal(
      canonicalStringify(JSON.parse(canonicalStringify(document))),
      canonicalStringify(document),
    );
  });
}
