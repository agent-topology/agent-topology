import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const checker = resolve(packageRoot, "scripts/check-compatibility.mjs");

test("the package range is derived from the tested-version manifest", async () => {
  const { stdout } = await execFileAsync(process.execPath, [
    checker,
    "--matrix",
  ]);
  assert.equal(stdout, 'matrix={"langgraph":["1.4.14"]}\n');
});

test("widening package metadata without conformance evidence is refused", async () => {
  const temporaryDirectory = await mkdtemp(
    resolve(tmpdir(), "agent-topology-compatibility-"),
  );
  const packageDocument = JSON.parse(
    await readFile(resolve(packageRoot, "package.json"), "utf8"),
  );
  packageDocument.dependencies["@langchain/langgraph"] = ">=1.4.14";
  const widenedPackage = resolve(temporaryDirectory, "package.json");
  await writeFile(widenedPackage, JSON.stringify(packageDocument));

  await assert.rejects(
    execFileAsync(process.execPath, [
      checker,
      "--package-json",
      widenedPackage,
    ]),
    /the tested-version manifest derives "1\.4\.14"/,
  );
});
