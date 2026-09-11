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
import {
  RegistryPreflightError,
  fetchPublishedSpecVersion,
  verifyResolvedSpecVersion,
} from "../scripts/verify_npm_registry_peer.mjs";

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
  const releaseInstallSpec = release.indexOf(
    "npm ci --prefix packages/typescript/spec",
  );
  const releaseBuildSpec = release.indexOf(
    "Build the local specification for producer checks",
  );
  const releasePackageChecks = release.indexOf(
    "Run package tests and quality checks",
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
  assert.ok(releaseInstallSpec >= 0, "release spec install step is missing");
  assert.ok(
    releaseBuildSpec > releaseInstallSpec,
    "release qualification must build the local spec after installing it",
  );
  assert.ok(
    releasePackageChecks > releaseBuildSpec,
    "release producer checks must run after the local spec build",
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

function packument(versions) {
  return {
    versions: Object.fromEntries(
      versions.map((version) => [version, { version }]),
    ),
  };
}

test("registry peer resolution accepts only the exact published version", async () => {
  const resolved = await fetchPublishedSpecVersion({
    version: "0.1.0-beta.2",
    fetchImpl: async () => ({
      status: 200,
      ok: true,
      json: async () => packument(["0.1.0-beta.1", "0.1.0-beta.2"]),
    }),
  });
  assert.equal(resolved, "0.1.0-beta.2");
});

test("registry peer resolution fails closed on a missing peer", async () => {
  await assert.rejects(
    fetchPublishedSpecVersion({
      version: "0.1.0-beta.2",
      fetchImpl: async () => ({ status: 404, ok: false }),
    }),
    (error) => {
      assert.ok(error instanceof RegistryPreflightError);
      assert.equal(error.reason, "missing-peer");
      return true;
    },
  );
});

test("registry peer resolution fails closed on a registry failure", async () => {
  await assert.rejects(
    fetchPublishedSpecVersion({
      version: "0.1.0-beta.2",
      fetchImpl: async () => {
        throw new Error("getaddrinfo ENOTFOUND registry.npmjs.org");
      },
    }),
    (error) => {
      assert.ok(error instanceof RegistryPreflightError);
      assert.equal(error.reason, "registry-failure");
      return true;
    },
  );
  await assert.rejects(
    fetchPublishedSpecVersion({
      version: "0.1.0-beta.2",
      fetchImpl: async () => ({ status: 500, ok: false }),
    }),
    (error) => {
      assert.ok(error instanceof RegistryPreflightError);
      assert.equal(error.reason, "registry-failure");
      return true;
    },
  );
});

test("registry peer resolution refuses a moving dist-tag that resolves elsewhere", async () => {
  await assert.rejects(
    fetchPublishedSpecVersion({
      version: "0.1.0-beta.2",
      fetchImpl: async () => ({
        status: 200,
        ok: true,
        json: async () => packument(["0.1.0-beta.1", "0.1.0-beta.3"]),
      }),
    }),
    (error) => {
      assert.ok(error instanceof RegistryPreflightError);
      assert.equal(error.reason, "missing-peer");
      assert.match(error.message, /moving dist-tag/);
      return true;
    },
  );
});

test("clean install must resolve the exact qualified spec peer, not a substitute", () => {
  const root = mkdtempSync(resolve(tmpdir(), "npm-registry-install-test-"));
  try {
    const specDir = resolve(root, "node_modules/@agent-topology/spec");
    execFileSync("mkdir", ["-p", specDir]);
    writeFileSync(
      resolve(specDir, "package.json"),
      JSON.stringify({ name: "@agent-topology/spec", version: "0.1.0-beta.2" }),
    );

    verifyResolvedSpecVersion({
      projectDir: root,
      specVersion: "0.1.0-beta.2",
    });
    assert.throws(
      () =>
        verifyResolvedSpecVersion({
          projectDir: root,
          specVersion: "0.1.0-beta.3",
        }),
      (error) => {
        assert.ok(error instanceof RegistryPreflightError);
        assert.equal(error.reason, "missing-peer");
        return true;
      },
    );
  } finally {
    rmSync(root, { recursive: true });
  }
});

test("release-npm.yml gates producer publication on a registry preflight even for dry runs", () => {
  const release = workflow("release-npm.yml");
  const preflightJob = release.indexOf("\n  registry-preflight:");
  const qualifyJob = release.indexOf("\n  qualify:");
  const publishJob = release.indexOf("\n  publish:");
  const preflightStep = release.indexOf("verify_npm_registry_peer.mjs");
  const publishNeeds = release.indexOf(
    "needs: [selection, qualify, registry-preflight]",
  );

  assert.ok(
    preflightJob > qualifyJob,
    "registry-preflight must follow qualify",
  );
  assert.ok(
    publishJob > preflightJob,
    "publish must follow registry-preflight",
  );
  assert.ok(
    preflightStep > preflightJob && preflightStep < publishJob,
    "the registry preflight script must run inside the registry-preflight job",
  );
  assert.ok(
    publishNeeds > preflightJob,
    "publish must depend on the registry-preflight job so a fail-closed result blocks the upload",
  );
  assert.ok(
    !/registry-preflight:[\s\S]*?if:\s*inputs\.publish/.test(
      release.slice(preflightJob, publishJob),
    ),
    "registry-preflight must run even when publish=false so dry runs still qualify the candidate",
  );
});
