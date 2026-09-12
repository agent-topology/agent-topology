// Framework-free consumer of both producers' wire documents through public APIs.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  canonicalStringify,
  computeStructureHash,
  derivedJoinEdges,
  validateDocument,
} from "../dist/index.js";
import { interpretationStatus } from "./interpretation-helper.mjs";

const documents = JSON.parse(readFileSync(process.argv[2], "utf8"));
const results = documents.map((document) => {
  const before = JSON.stringify(document);
  assert.equal(validateDocument(document).valid, true);
  const result = {
    canonical: canonicalStringify(document),
    hash: computeStructureHash(document),
    status: interpretationStatus(document),
    links: document.graphs.map((graph) => derivedJoinEdges(graph.structure)),
  };
  assert.equal(JSON.stringify(document), before);
  return result;
});
process.stdout.write(JSON.stringify(results));
