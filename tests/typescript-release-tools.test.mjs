import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  checkReceipt,
  makeReceipt,
  verifyWorktree,
} from "../scripts/verify_typescript_release.mjs";

const checks = [
  "artifact-inspection",
  "clean-installation",
  "package-tests",
  "typescript-quality",
];

function workflow(name) {
  return readFileSync(
    resolve(
      fileURLToPath(new URL("..", import.meta.url)),
      `.github/workflows/${name}`,
    ),
    "utf8",
  );
}

test("TypeScript evidence jobs provision their cross-language inputs", () => {
  const compatibility = workflow("langgraph-compatibility.yml");
  const packages = workflow("typescript-packages.yml");
  const release = workflow("release-npm.yml");
  const installSpec = compatibility.indexOf(
    "npm ci --prefix packages/typescript/spec",
  );
  const buildSpec = compatibility.indexOf(
    "npm --prefix packages/typescript/spec run build",
  );
  const installProducer = compatibility.indexOf(
    "npm ci --prefix packages/typescript/langgraph",
  );

  assert.ok(installSpec >= 0, "compatibility spec install step is missing");
  assert.ok(
    buildSpec > installSpec,
    "compatibility spec must build after its dependencies install",
  );
  assert.ok(
    installProducer > buildSpec,
    "compatibility producer must install after the local spec has build output",
  );

  const packageInstallSpec = packages.indexOf(
    "npm ci --prefix packages/typescript/spec",
  );
  const packageBuildSpec = packages.indexOf(
    "npm --prefix packages/typescript/spec run build",
  );
  const packageInstallTarget = packages.indexOf(
    "npm ci --prefix packages/typescript/${{ matrix.package }}",
  );

  assert.ok(
    packages.includes("uses: astral-sh/setup-uv@v10.0.1"),
    "package tests must install uv for the Python parity oracle",
  );
  assert.ok(
    release.includes("uses: astral-sh/setup-uv@v10.0.1"),
    "npm release qualification must install uv for the Python parity oracle",
  );
  assert.ok(
    release.includes("npm-tag: ${{ steps.select.outputs.npm-tag }}"),
    "npm release selection must expose the version-derived distribution tag",
  );
  assert.ok(
    release.includes('--tag "${{ needs.selection.outputs.npm-tag }}"'),
    "npm publication must provide the selected distribution tag",
  );
  assert.ok(
    release.includes("NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}"),
    "npm publication must receive the protected environment token",
  );
  assert.ok(packageInstallSpec >= 0, "package spec install step is missing");
  assert.ok(packageBuildSpec > packageInstallSpec);
  assert.ok(
    packageInstallTarget > packageBuildSpec,
    "package producer must install after the local spec has build output",
  );
});

test("receipt binds package, version, commit, checks, and artifact digest", () => {
  const root = mkdtempSync(resolve(tmpdir(), "npm-receipt-test-"));
  try {
    const tarball = resolve(root, "agent-topology-spec-1.2.3.tgz");
    writeFileSync(tarball, "artifact bytes");
    const artifact = {
      filename: "agent-topology-spec-1.2.3.tgz",
      name: "@agent-topology/spec",
      package: "spec",
      sha256:
        "4659fc0570122b0e0aa14f4ff7c261b1fe51795a01ba79963f462ebf40d7520d",
      version: "1.2.3",
    };
    const receipt = makeReceipt({
      packageId: "spec",
      version: "1.2.3",
      commit: "abc123",
      artifact,
      checks,
    });
    checkReceipt({
      receipt,
      packageId: "spec",
      version: "1.2.3",
      commit: "abc123",
      tarball,
    });

    receipt.artifact.sha256 = "tampered";
    assert.throws(
      () =>
        checkReceipt({
          receipt,
          packageId: "spec",
          version: "1.2.3",
          commit: "abc123",
          tarball,
        }),
      /Expected values to be strictly equal/,
    );
  } finally {
    rmSync(root, { recursive: true });
  }
});

test("receipt refuses a missing qualification check", () => {
  assert.throws(
    () =>
      makeReceipt({
        packageId: "spec",
        version: "1.2.3",
        commit: "abc123",
        artifact: {},
        checks: checks.slice(1),
      }),
    /Expected values to be strictly deep-equal/,
  );
});

test("release input must be the exact commit and a clean checkout", () => {
  const root = mkdtempSync(resolve(tmpdir(), "npm-worktree-test-"));
  try {
    execFileSync("git", ["init", "--quiet"], { cwd: root });
    execFileSync("git", ["config", "user.email", "test@example.com"], {
      cwd: root,
    });
    execFileSync("git", ["config", "user.name", "Test"], { cwd: root });
    writeFileSync(resolve(root, "tracked.txt"), "clean\n");
    execFileSync("git", ["add", "tracked.txt"], { cwd: root });
    execFileSync("git", ["commit", "--quiet", "-m", "fixture"], { cwd: root });
    const commit = execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: root,
      encoding: "utf8",
    }).trim();

    verifyWorktree(commit, root);
    assert.throws(() => verifyWorktree("wrong-commit", root), /does not match/);
    writeFileSync(resolve(root, "tracked.txt"), "dirty\n");
    assert.throws(() => verifyWorktree(commit, root), /dirty/);
  } finally {
    rmSync(root, { recursive: true });
  }
});
