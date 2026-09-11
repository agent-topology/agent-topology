#!/usr/bin/env node
// Publication-only preflight: before the npm producer publishes, confirm its
// exact prepared @agent-topology/spec peer is already public at that exact
// version (never a moving dist-tag), then clean-install that registry copy
// with the already-qualified producer tarball and run a minimal API smoke.
// This never replaces the local/offline candidate qualification in `qualify`.

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const SPEC_PACKAGE_NAME = "@agent-topology/spec";
export const PUBLIC_NPM_REGISTRY = "https://registry.npmjs.org";

export class RegistryPreflightError extends Error {
  constructor(reason, message) {
    super(message);
    this.name = "RegistryPreflightError";
    this.reason = reason;
  }
}

export async function fetchPublishedSpecVersion({
  version,
  name = SPEC_PACKAGE_NAME,
  registry = PUBLIC_NPM_REGISTRY,
  fetchImpl = fetch,
}) {
  assert.ok(version, "a specification peer version is required");
  const url = `${registry.replace(/\/+$/, "")}/${encodeURIComponent(name)}`;
  let response;
  try {
    response = await fetchImpl(url, {
      headers: { accept: "application/vnd.npm.install-v1+json" },
    });
  } catch (error) {
    throw new RegistryPreflightError(
      "registry-failure",
      `could not reach ${registry} for ${name}: ${error.message}`,
    );
  }
  if (response.status === 404) {
    throw new RegistryPreflightError(
      "missing-peer",
      `${name} is not published on ${registry}`,
    );
  }
  if (!response.ok) {
    throw new RegistryPreflightError(
      "registry-failure",
      `${registry} returned HTTP ${response.status} for ${name}`,
    );
  }
  let packument;
  try {
    packument = await response.json();
  } catch (error) {
    throw new RegistryPreflightError(
      "registry-failure",
      `${registry} returned an invalid response for ${name}: ${error.message}`,
    );
  }
  const resolved = packument?.versions?.[version]?.version;
  if (resolved !== version) {
    throw new RegistryPreflightError(
      "missing-peer",
      `${name}@${version} is not published on ${registry}; refusing a moving dist-tag`,
    );
  }
  return resolved;
}

export function verifyResolvedSpecVersion({
  projectDir,
  specVersion,
  specName = SPEC_PACKAGE_NAME,
  readFile = readFileSync,
}) {
  const manifestPath = resolve(
    projectDir,
    "node_modules",
    ...specName.split("/"),
    "package.json",
  );
  let manifest;
  try {
    manifest = JSON.parse(readFile(manifestPath, "utf8"));
  } catch (error) {
    throw new RegistryPreflightError(
      "registry-failure",
      `could not read the installed ${specName} manifest: ${error.message}`,
    );
  }
  if (manifest.version !== specVersion) {
    throw new RegistryPreflightError(
      "missing-peer",
      `installed ${specName}@${manifest.version} does not match the qualified peer ${specVersion}`,
    );
  }
}

export function runPublicApiSmoke(projectDir, { exec = execFileSync } = {}) {
  try {
    exec(
      "node",
      [
        "--input-type=module",
        "--eval",
        'const spec = await import("@agent-topology/spec"); const producer = await import("@agent-topology/langgraph"); if (typeof spec.validateDocument !== "function" || typeof producer.describe !== "function") throw new Error("missing public API");',
      ],
      { cwd: projectDir, stdio: "pipe" },
    );
  } catch (error) {
    throw new RegistryPreflightError(
      "smoke-failure",
      `public API smoke failed for the registry spec and the qualified producer tarball: ${error.message}`,
    );
  }
}

export async function verifyRegistryPeer({
  specVersion,
  producerTarball,
  registry = PUBLIC_NPM_REGISTRY,
  exec = execFileSync,
  fetchImpl = fetch,
}) {
  await fetchPublishedSpecVersion({
    version: specVersion,
    registry,
    fetchImpl,
  });

  const projectDir = mkdtempSync(
    resolve(tmpdir(), "agent-topology-registry-preflight-"),
  );
  writeFileSync(
    resolve(projectDir, "package.json"),
    `${JSON.stringify({ private: true, type: "module" })}\n`,
  );
  try {
    try {
      exec(
        "npm",
        [
          "install",
          "--ignore-scripts",
          "--registry",
          registry,
          `${SPEC_PACKAGE_NAME}@${specVersion}`,
          resolve(producerTarball),
        ],
        { cwd: projectDir, stdio: "pipe" },
      );
    } catch (error) {
      throw new RegistryPreflightError(
        "registry-failure",
        `clean install of ${SPEC_PACKAGE_NAME}@${specVersion} and the qualified producer tarball failed: ${error.message}`,
      );
    }
    verifyResolvedSpecVersion({ projectDir, specVersion });
    runPublicApiSmoke(projectDir, { exec });
  } finally {
    rmSync(projectDir, { recursive: true, force: true });
  }
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

async function main(argv) {
  const args = options(argv);
  assert.ok(args["spec-version"], "--spec-version is required");
  assert.ok(args["producer-tarball"], "--producer-tarball is required");
  try {
    await verifyRegistryPeer({
      specVersion: args["spec-version"],
      producerTarball: args["producer-tarball"],
      registry: args.registry,
    });
  } catch (error) {
    const label =
      error instanceof RegistryPreflightError ? `[${error.reason}] ` : "";
    process.stderr.write(`${label}${error.message}\n`);
    process.exitCode = 1;
    return;
  }
  process.stdout.write(
    `verified ${SPEC_PACKAGE_NAME}@${args["spec-version"]} on the public registry and the coexistence smoke with the qualified producer tarball\n`,
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2));
}
