import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(packageRoot, "../../..");

function option(name, fallback) {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : resolve(process.argv[index + 1]);
}

const manifestPath = option(
  "--manifest",
  resolve(packageRoot, "src/compatibility.json"),
);
const packagePath = option(
  "--package-json",
  resolve(packageRoot, "package.json"),
);

const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
const packageDocument = JSON.parse(await readFile(packagePath, "utf8"));
const versions = manifest.testedVersions;

if (!Array.isArray(versions) || versions.length === 0) {
  throw new Error("testedVersions must be a non-empty array");
}
if (
  versions.some(
    (version) =>
      typeof version !== "string" || !/^\d+\.\d+\.\d+$/.test(version),
  )
) {
  throw new Error("testedVersions must contain exact stable semantic versions");
}
if (new Set(versions).size !== versions.length) {
  throw new Error("testedVersions must not contain duplicates");
}
const sortedVersions = [...versions].sort((left, right) =>
  left.localeCompare(right, "en", { numeric: true }),
);
if (JSON.stringify(versions) !== JSON.stringify(sortedVersions)) {
  throw new Error("testedVersions must be sorted in ascending version order");
}

for (const version of versions) {
  const evidenceRoot = resolve(
    repositoryRoot,
    "docs/research/frameworks/langgraph/typescript",
    version,
  );
  await Promise.all([
    readFile(resolve(evidenceRoot, "dossier.md")),
    readFile(resolve(evidenceRoot, "probes/introspection.mjs")),
  ]);
}

const supportedRange = versions.join(" || ");
const metadataRange = packageDocument.dependencies?.["@langchain/langgraph"];
if (metadataRange !== supportedRange) {
  throw new Error(
    `package metadata declares ${JSON.stringify(metadataRange)} for @langchain/langgraph; ` +
      `the tested-version manifest derives ${JSON.stringify(supportedRange)}`,
  );
}

if (process.argv.includes("--matrix")) {
  process.stdout.write(`matrix=${JSON.stringify({ langgraph: versions })}\n`);
} else {
  process.stdout.write(
    `LangGraph.js compatibility contract: ${versions.join(", ")}\n`,
  );
}
