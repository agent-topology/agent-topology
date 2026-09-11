#!/usr/bin/env node

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const PACKAGES = {
  spec: {
    name: "@agent-topology/spec",
    root: "packages/typescript/spec",
    repositoryDirectory: "packages/typescript/spec",
    files: [
      "package/README.md",
      "package/dist/canonical.d.ts",
      "package/dist/canonical.js",
      "package/dist/generated/agent-topology.schema.json",
      "package/dist/generated/contract.d.ts",
      "package/dist/generated/contract.js",
      "package/dist/index.d.ts",
      "package/dist/index.js",
      "package/dist/types.d.ts",
      "package/dist/types.js",
      "package/dist/validation.d.ts",
      "package/dist/validation.js",
      "package/package.json",
    ],
    checks: [
      "artifact-inspection",
      "clean-installation",
      "package-tests",
      "typescript-quality",
    ],
  },
  langgraph: {
    name: "@agent-topology/langgraph",
    root: "packages/typescript/langgraph",
    files: [
      "package/README.md",
      "package/dist/compatibility.json",
      "package/dist/errors.d.ts",
      "package/dist/errors.js",
      "package/dist/index.d.ts",
      "package/dist/index.js",
      "package/dist/internal.d.ts",
      "package/dist/internal.js",
      "package/package.json",
    ],
    checks: [
      "artifact-inspection",
      "clean-installation",
      "package-tests",
      "supported-langgraph-conformance",
      "typescript-quality",
    ],
  },
};

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function tarOutput(tarball, member) {
  return execFileSync("tar", ["-xOf", tarball, member], { encoding: "utf8" });
}

export function inspectTarball({ packageId, version, tarball, specVersion }) {
  const config = PACKAGES[packageId];
  assert.ok(config, `unsupported package: ${packageId}`);
  const absoluteTarball = resolve(tarball);
  const files = execFileSync("tar", ["-tzf", absoluteTarball], {
    encoding: "utf8",
  })
    .trim()
    .split("\n")
    .sort();
  assert.deepEqual(
    files,
    [...config.files].sort(),
    "tarball file list differs",
  );

  const manifest = JSON.parse(
    tarOutput(absoluteTarball, "package/package.json"),
  );
  assert.equal(manifest.name, config.name);
  assert.equal(manifest.version, version);
  assert.equal(manifest.type, "module");
  assert.equal(manifest.engines?.node, ">=20");
  if (config.repositoryDirectory) {
    assert.deepEqual(manifest.repository, {
      type: "git",
      url: "git+https://github.com/agent-topology/agent-topology.git",
      directory: config.repositoryDirectory,
    });
  }
  assert.deepEqual(manifest.files, ["dist", "README.md"]);
  assert.deepEqual(manifest.exports, {
    ".": { types: "./dist/index.d.ts", import: "./dist/index.js" },
  });
  assert.equal(
    manifest.bin,
    undefined,
    "TypeScript packages must not publish an executable",
  );

  if (packageId === "spec") {
    assert.deepEqual(manifest.dependencies, {
      ajv: "8.20.0",
      "ajv-formats": "3.0.1",
    });
    assert.equal(manifest.peerDependencies, undefined);
  } else {
    assert.deepEqual(manifest.dependencies, {
      "@langchain/langgraph": "1.4.14",
    });
    assert.equal(
      manifest.peerDependencies?.["@agent-topology/spec"],
      specVersion,
    );
    assert.equal(
      manifest.devDependencies?.["@agent-topology/spec"],
      "file:../spec",
    );
  }

  return {
    filename: basename(absoluteTarball),
    name: config.name,
    package: packageId,
    sha256: sha256(absoluteTarball),
    version,
  };
}

export function makeReceipt({ packageId, version, commit, artifact, checks }) {
  const config = PACKAGES[packageId];
  assert.ok(config, `unsupported package: ${packageId}`);
  assert.deepEqual([...checks].sort(), [...config.checks].sort());
  return {
    schemaVersion: 1,
    ecosystem: "npm",
    package: packageId,
    name: config.name,
    version,
    commit,
    checks: [...checks].sort(),
    artifact,
  };
}

export function verifyWorktree(commit, cwd = repositoryRoot) {
  const head = execFileSync("git", ["rev-parse", "HEAD"], {
    cwd,
    encoding: "utf8",
  }).trim();
  assert.equal(head, commit, "release commit does not match checkout HEAD");
  const status = execFileSync(
    "git",
    ["status", "--porcelain", "--untracked-files=all"],
    { cwd, encoding: "utf8" },
  ).trim();
  assert.equal(status, "", "release checkout is dirty");
}

export function checkReceipt({ receipt, packageId, version, commit, tarball }) {
  const config = PACKAGES[packageId];
  assert.ok(config, `unsupported package: ${packageId}`);
  assert.equal(receipt.schemaVersion, 1);
  assert.equal(receipt.ecosystem, "npm");
  assert.equal(receipt.package, packageId);
  assert.equal(receipt.name, config.name);
  assert.equal(receipt.version, version);
  assert.equal(receipt.commit, commit);
  assert.deepEqual(receipt.checks, [...config.checks].sort());
  assert.equal(receipt.artifact.filename, basename(tarball));
  assert.equal(receipt.artifact.sha256, sha256(tarball));
}

function options(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    assert.ok(key?.startsWith("--"), `invalid option: ${key}`);
    const value = argv[index + 1];
    assert.ok(value, `missing value for ${key}`);
    parsed[key.slice(2)] = value;
  }
  return parsed;
}

function pack(packageId, version, specVersion) {
  const config = PACKAGES[packageId];
  assert.ok(config, `unsupported package: ${packageId}`);
  const temporaryRoot = mkdtempSync(resolve(tmpdir(), "agent-topology-pack-"));
  try {
    const output = JSON.parse(
      execFileSync(
        "npm",
        [
          "pack",
          resolve(repositoryRoot, config.root),
          "--json",
          "--pack-destination",
          temporaryRoot,
        ],
        { cwd: repositoryRoot, encoding: "utf8" },
      ),
    );
    const tarball = resolve(temporaryRoot, output[0].filename);
    const artifact = inspectTarball({
      packageId,
      version,
      tarball,
      specVersion,
    });
    process.stdout.write(`${JSON.stringify(artifact)}\n`);
  } finally {
    rmSync(temporaryRoot, { recursive: true });
  }
}

function main(argv) {
  const [command, ...rest] = argv;
  const args = options(rest);
  if (command === "pack") {
    pack(args.package, args.version, args["spec-version"]);
    return;
  }
  if (command === "inspect") {
    process.stdout.write(
      `${JSON.stringify(
        inspectTarball({
          packageId: args.package,
          version: args.version,
          tarball: args.tarball,
          specVersion: args["spec-version"],
        }),
      )}\n`,
    );
    return;
  }
  if (command === "create") {
    verifyWorktree(args.commit);
    const artifact = inspectTarball({
      packageId: args.package,
      version: args.version,
      tarball: args.tarball,
      specVersion: args["spec-version"],
    });
    const receipt = makeReceipt({
      packageId: args.package,
      version: args.version,
      commit: args.commit,
      artifact,
      checks: args.checks.split(","),
    });
    writeFileSync(args.receipt, `${JSON.stringify(receipt, null, 2)}\n`);
    return;
  }
  if (command === "check") {
    verifyWorktree(args.commit);
    const receipt = JSON.parse(readFileSync(args.receipt, "utf8"));
    checkReceipt({
      receipt,
      packageId: args.package,
      version: args.version,
      commit: args.commit,
      tarball: args.tarball,
    });
    return;
  }
  throw new Error(`unsupported command: ${command}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2));
}
