import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { compile } from "json-schema-to-typescript";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const schemaPath = resolve(
  packageRoot,
  "../../../spec/agent-topology.schema.json",
);
const generatedDirectory = resolve(packageRoot, "src/generated");
const schema = JSON.parse(await readFile(schemaPath, "utf8"));

await mkdir(generatedDirectory, { recursive: true });
await writeFile(
  resolve(generatedDirectory, "contract.ts"),
  await compile(schema, "AgentTopologyDocument", {
    bannerComment:
      "/* Generated from the repository's canonical JSON Schema. Do not edit. */",
    style: { singleQuote: false },
  }),
);
await copyFile(
  schemaPath,
  resolve(generatedDirectory, "agent-topology.schema.json"),
);
