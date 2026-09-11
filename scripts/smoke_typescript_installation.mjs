#!/usr/bin/env node

import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

function options(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 2) {
    parsed[argv[index].slice(2)] = resolve(argv[index + 1]);
  }
  return parsed;
}

function install(cwd, ...artifacts) {
  execFileSync("npm", ["install", "--ignore-scripts", ...artifacts], {
    cwd,
    stdio: "pipe",
  });
}

function run(cwd, source) {
  execFileSync("node", ["--input-type=module", "--eval", source], {
    cwd,
    stdio: "pipe",
  });
}

const args = options(process.argv.slice(2));
assert.ok(args["spec-tarball"], "--spec-tarball is required");
assert.ok(args["langgraph-tarball"], "--langgraph-tarball is required");

const temporaryRoot = mkdtempSync(
  resolve(tmpdir(), "agent-topology-typescript-smoke-"),
);
try {
  for (const scenario of ["spec", "langgraph", "coexistence"]) {
    const project = resolve(temporaryRoot, scenario);
    execFileSync("mkdir", [project]);
    writeFileSync(
      resolve(project, "package.json"),
      `${JSON.stringify({ private: true, type: "module" })}\n`,
    );
    if (scenario === "spec") {
      install(project, args["spec-tarball"]);
      run(
        project,
        'const api = await import("@agent-topology/spec"); if (typeof api.validateDocument !== "function") throw new Error("missing spec API");',
      );
      const deepImport = spawnSync(
        "node",
        [
          "--input-type=module",
          "--eval",
          'await import("@agent-topology/spec/dist/validation.js")',
        ],
        { cwd: project, encoding: "utf8" },
      );
      assert.notEqual(deepImport.status, 0);
      assert.match(deepImport.stderr, /ERR_PACKAGE_PATH_NOT_EXPORTED/);
    } else if (scenario === "langgraph") {
      install(project, args["spec-tarball"]);
      install(project, args["langgraph-tarball"]);
      run(
        project,
        'const api = await import("@agent-topology/langgraph"); if (typeof api.describe !== "function") throw new Error("missing producer API");',
      );
    } else {
      install(project, args["spec-tarball"], args["langgraph-tarball"]);
      run(
        project,
        'const spec = await import("@agent-topology/spec"); const producer = await import("@agent-topology/langgraph"); if (typeof spec.computeStructureHash !== "function" || typeof producer.describe !== "function") throw new Error("packages do not coexist");',
      );
    }
  }
  console.log(
    "spec alone, producer with its peer, and both packages together passed clean public-import smoke tests",
  );
} finally {
  rmSync(temporaryRoot, { recursive: true });
}
