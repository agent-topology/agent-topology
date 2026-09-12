// Copy beside a standalone spec installation; pass a probe result JSON path.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { assertTopologyDocument } from "@agent-topology/spec";

const require = createRequire(import.meta.url);
const result = JSON.parse(readFileSync(process.argv[2], "utf8"));
assertTopologyDocument(result.documents["F5-sentinels"]);
assert.throws(() => require.resolve("@langchain/langgraph"), {
  code: "MODULE_NOT_FOUND",
});
assert.throws(() => require("@agent-topology/spec"), {
  code: "ERR_PACKAGE_PATH_NOT_EXPORTED",
});
console.log(
  JSON.stringify(
    {
      node: process.version,
      esmValidation: "passed",
      frameworkAbsent: true,
      requireCode: "ERR_PACKAGE_PATH_NOT_EXPORTED",
    },
    null,
    2,
  ),
);
