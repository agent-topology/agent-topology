#!/usr/bin/env node

import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
        `
        import assert from "node:assert/strict";
        import { derivedJoinEdges, validateDocument } from "@agent-topology/spec";
        const document = ${readFileSync(new URL("../conformance/fixtures/multi-source-join/expected.json", import.meta.url), "utf8")};
        assert.equal(validateDocument(document).valid, true);
        const structure = document.graphs[0].structure;
        const before = JSON.stringify(structure);
        const links = derivedJoinEdges(structure);
        assert.deepEqual(links, structure.joins.flatMap(join => join.sources.map(source => ({joinId: join.id, source, target: join.target}))));
        assert.equal(links.length, 2);
        assert.equal(JSON.stringify(structure), before);
        `,
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
    if (scenario !== "spec") {
      run(
        project,
        `
        import assert from "node:assert/strict";
        import { readFileSync } from "node:fs";
        import { Annotation, StateGraph, START, END } from "@langchain/langgraph";
        import { describe } from "@agent-topology/langgraph";
        const manifest = JSON.parse(readFileSync("node_modules/@agent-topology/langgraph/package.json", "utf8"));
        const graph = new StateGraph(Annotation.Root({ value: Annotation }))
          .addNode("step", state => state).addEdge(START, "step").addEdge("step", END).compile();
        const document = await describe(graph);
        assert.equal(document.provenance.producer.version, manifest.version);
        assert.equal(document.topologyVersion, "0.1");
        assert.equal(document.structureHash.algorithmVersion, "1");
      `,
      );
    }
  }
  console.log(
    "spec alone, producer with its peer, and both packages together passed clean public-import smoke tests",
  );
} finally {
  rmSync(temporaryRoot, { recursive: true });
}
