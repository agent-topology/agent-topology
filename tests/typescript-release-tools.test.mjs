import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import test from "node:test";

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
