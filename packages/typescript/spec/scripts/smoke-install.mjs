import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const temporaryRoot = await mkdtemp(
  resolve(tmpdir(), "agent-topology-spec-smoke-"),
);

try {
  const packedName = execFileSync(
    "npm",
    ["pack", "--pack-destination", temporaryRoot],
    { cwd: packageRoot, encoding: "utf8" },
  )
    .trim()
    .split("\n")
    .at(-1);
  assert.ok(packedName);
  const tarball = resolve(temporaryRoot, packedName);
  const contents = execFileSync("tar", ["-tzf", tarball], {
    encoding: "utf8",
  })
    .trim()
    .split("\n")
    .sort();
  assert.deepEqual(
    contents,
    [
      "package/LICENSE",
      "package/README.md",
      "package/dist/canonical.d.ts",
      "package/dist/canonical.js",
      "package/dist/generated/agent-topology.schema.json",
      "package/dist/generated/contract.d.ts",
      "package/dist/generated/contract.js",
      "package/dist/index.d.ts",
      "package/dist/index.js",
      "package/dist/joins.d.ts",
      "package/dist/joins.js",
      "package/dist/types.d.ts",
      "package/dist/types.js",
      "package/dist/validation.d.ts",
      "package/dist/validation.js",
      "package/package.json",
    ].sort(),
  );

  const consumer = resolve(temporaryRoot, "consumer");
  await mkdir(consumer);
  await writeFile(
    resolve(consumer, "package.json"),
    JSON.stringify({ private: true, type: "module" }),
  );
  await writeFile(
    resolve(consumer, "tsconfig.json"),
    JSON.stringify({
      compilerOptions: {
        module: "NodeNext",
        moduleResolution: "NodeNext",
        outDir: "dist",
        strict: true,
        target: "ES2022",
      },
      include: ["index.ts"],
    }),
  );
  const expected = JSON.parse(
    await readFile(
      resolve(
        packageRoot,
        "../../../conformance/fixtures/multi-source-join/expected.json",
      ),
      "utf8",
    ),
  );
  await writeFile(
    resolve(consumer, "index.ts"),
    [
      'import { canonicalStringify, computeStructureHash, derivedJoinEdges, validateDocument, type DerivedJoinEdge, type TopologyDocument } from "@agent-topology/spec";',
      `const value: unknown = ${JSON.stringify(expected)};`,
      "const result = validateDocument(value);",
      'if (!result.valid) throw new Error("fixture did not validate");',
      "const document: TopologyDocument = result.document;",
      "const links: DerivedJoinEdge[] = derivedJoinEdges(document.graphs[0]!.structure);",
      'if (links.length !== 2 || links.some(link => link.joinId !== document.graphs[0]!.structure.joins[0]!.id)) throw new Error("join provenance differs");',
      `if (canonicalStringify(document) !== ${JSON.stringify(JSON.stringify(expected))}) throw new Error("canonical bytes differ");`,
      `if (computeStructureHash(document).value !== ${JSON.stringify(expected.structureHash.value)}) throw new Error("hash differs");`,
    ].join("\n"),
  );

  execFileSync(
    "npm",
    [
      "install",
      "--ignore-scripts",
      tarball,
      "typescript@7.0.2",
      "@types/node@22.20.2",
    ],
    { cwd: consumer, stdio: "pipe" },
  );
  execFileSync(
    resolve(consumer, "node_modules/.bin/tsc"),
    ["-p", "tsconfig.json"],
    {
      cwd: consumer,
      stdio: "pipe",
    },
  );
  execFileSync("node", ["dist/index.js"], { cwd: consumer, stdio: "pipe" });
  const deepImport = spawnSync(
    "node",
    [
      "--input-type=module",
      "--eval",
      'await import("@agent-topology/spec/dist/validation.js")',
    ],
    { cwd: consumer, encoding: "utf8" },
  );
  assert.notEqual(deepImport.status, 0);
  assert.match(deepImport.stderr, /ERR_PACKAGE_PATH_NOT_EXPORTED/);
  console.log(
    "packed artifact installed, type-checked, ran, and kept internals private in a clean project",
  );
} finally {
  await rm(temporaryRoot, { recursive: true });
}
