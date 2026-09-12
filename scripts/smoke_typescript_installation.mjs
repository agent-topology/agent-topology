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
  execFileSync(process.execPath, ["--input-type=module", "--eval", source], {
    cwd,
    stdio: "pipe",
  });
}

// Execute the documentation itself in projects outside the checkout so package
// self-resolution and development dependencies cannot hide installation failures.
function documentedExamples(project, documentPath, basename) {
  const markdown = readFileSync(new URL(documentPath, import.meta.url), "utf8");
  const sources = [...markdown.matchAll(/```javascript\n([\s\S]*?)\n```/g)];
  assert.equal(
    sources.length,
    2,
    `${documentPath}: expected ESM and CommonJS examples`,
  );
  return sources.map((match, index) => {
    const filename = `${basename}.${index === 0 ? "mjs" : "cjs"}`;
    writeFileSync(resolve(project, filename), match[1]);
    const output = execFileSync(process.execPath, [filename], {
      cwd: project,
      encoding: "utf8",
    });
    return JSON.parse(output);
  });
}

function assertEsmBoundary(project, packageName) {
  const manifest = JSON.parse(
    readFileSync(
      resolve(project, "node_modules", packageName, "package.json"),
      "utf8",
    ),
  );
  assert.equal(manifest.type, "module");
  assert.deepEqual(manifest.exports, {
    ".": { types: "./dist/index.d.ts", import: "./dist/index.js" },
  });
  for (const source of [
    `require(${JSON.stringify(packageName)})`,
    `import(${JSON.stringify(`${packageName}/dist/index.js`)})`,
  ]) {
    const result = spawnSync(
      process.execPath,
      ["--input-type=commonjs", "--eval", source],
      {
        cwd: project,
        encoding: "utf8",
      },
    );
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /ERR_PACKAGE_PATH_NOT_EXPORTED/);
  }
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
      `${JSON.stringify({ private: true, type: "commonjs" })}\n`,
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
      writeFileSync(
        resolve(project, "topology.json"),
        readFileSync(
          new URL(
            "../conformance/fixtures/linear-flow/expected.json",
            import.meta.url,
          ),
        ),
      );
      const expected = JSON.parse(
        readFileSync(resolve(project, "topology.json"), "utf8"),
      );
      for (const document of documentedExamples(
        project,
        "../packages/typescript/spec/README.md",
        "inspect",
      )) {
        assert.deepEqual(document, expected);
      }
      writeFileSync(resolve(project, "topology.json"), "{}");
      for (const extension of ["mjs", "cjs"]) {
        const invalid = spawnSync(process.execPath, [`inspect.${extension}`], {
          cwd: project,
          encoding: "utf8",
        });
        assert.equal(invalid.status, 1);
        assert.ok(invalid.stderr.trim());
      }
      // A malformed JSON file rejects the CommonJS async entry point.
      writeFileSync(resolve(project, "topology.json"), "{");
      const rejected = spawnSync(process.execPath, ["inspect.cjs"], {
        cwd: project,
        encoding: "utf8",
      });
      assert.equal(rejected.status, 1);
      assert.match(rejected.stderr, /SyntaxError/);
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
    assertEsmBoundary(project, "@agent-topology/spec");
    if (scenario !== "spec") {
      assertEsmBoundary(project, "@agent-topology/langgraph");
      for (const document of documentedExamples(
        project,
        "../docs/getting-started/typescript.md",
        "graph",
      )) {
        assert.equal(document.completeness.status, "complete");
        assert.deepEqual(
          document.graphs[0].structure.nodes.map((node) => node.id),
          ["__end__", "__start__", "greet"],
        );
        writeFileSync(
          resolve(project, "topology.json"),
          JSON.stringify(document),
        );
        run(
          project,
          `
          import assert from "node:assert/strict";
          import { readFileSync } from "node:fs";
          import { computeStructureHash, validateDocument } from "@agent-topology/spec";
          const document = JSON.parse(readFileSync("topology.json", "utf8"));
          assert.equal(validateDocument(document).valid, true);
          assert.deepEqual(computeStructureHash(document), document.structureHash);
        `,
        );
      }
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
    "spec alone, producer with its peer, and both packages together passed clean ESM/CommonJS documentation and public-import smoke tests",
  );
} finally {
  rmSync(temporaryRoot, { recursive: true });
}
