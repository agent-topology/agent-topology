import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import * as spec from "../dist/index.js";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const fixturesRoot = resolve(packageRoot, "../../../conformance/fixtures");

// ADR 0009 byte oracle: docs/decisions/0009-numeric-canonical-form.md and
// its implementation criteria at 0009-implementation-criteria.md.
/** @type {[string, number, string][]} */
const NUMERIC_BYTE_ORACLE = [
  ["signed-zero-positive", 0, "0"],
  ["signed-zero-negative", -0, "0"],
  ["integral-float", 1.0, "1"],
  ["small-integer-boundary-positive", 100, "100"],
  ["small-integer-boundary-negative", -100, "-100"],
  ["ordinary-fraction", 0.5, "0.5"],
  ["exponent-lower-threshold-fixed", 1e-6, "0.000001"],
  ["exponent-lower-threshold-exponential", 1e-7, "1e-7"],
  ["exponent-upper-threshold-fixed", 1e20, "100000000000000000000"],
  ["exponent-upper-threshold-exponential", 1e21, "1e+21"],
  ["in-domain-integer-boundary", 9007199254740992, "9007199254740992"],
];

async function expectedDocuments() {
  const cases = await readdir(fixturesRoot, { withFileTypes: true });
  return Promise.all(
    cases
      .filter((entry) => entry.isDirectory())
      .map(async (entry) => ({
        name: entry.name,
        document: JSON.parse(
          await readFile(
            resolve(fixturesRoot, entry.name, "expected.json"),
            "utf8",
          ),
        ),
      })),
  );
}

test("the deliberate runtime API is the only public root surface", () => {
  assert.deepEqual(Object.keys(spec).sort(), [
    "STRUCTURE_HASH_ALGORITHM",
    "STRUCTURE_HASH_ALGORITHM_VERSION",
    "TopologyValidationError",
    "assertTopologyDocument",
    "canonicalStringify",
    "canonicalizeDocument",
    "computeStructureHash",
    "derivedJoinEdges",
    "finalizeDocument",
    "isTopologyDocument",
    "loadSchema",
    "validateDocument",
  ]);
});

test("every shared expected document validates and has byte-stable hash parity", async () => {
  for (const { name, document } of await expectedDocuments()) {
    const result = spec.validateDocument(document);
    assert.equal(result.valid, true, `${name}: ${JSON.stringify(result)}`);
    assert.equal(
      spec.canonicalStringify(document),
      JSON.stringify(document),
      `${name}: expected documents are stored in canonical key and collection order`,
    );
    assert.deepEqual(
      spec.computeStructureHash(document),
      document.structureHash,
      `${name}: structure hash`,
    );
  }
});

test("canonical bytes and hashes agree with the Python contract implementation", async () => {
  const cases = await expectedDocuments();
  // UTF-16 order puts the astral character before the BMP private-use character;
  // Python and the canonical contract order their Unicode code points instead.
  const firstCase = cases[0];
  assert.ok(firstCase);
  const unicode = structuredClone(firstCase.document);
  unicode.graphs = [
    {
      id: "main",
      structure: {
        nodes: [{ id: "\u{10000}" }, { id: "\ue000" }],
        edges: [],
        joins: [
          { id: "join", sources: ["\u{10000}", "\ue000"], target: "\ue000" },
        ],
        entryNodeIds: ["\u{10000}", "\ue000"],
        exitNodeIds: ["\u{10000}", "\ue000"],
      },
    },
  ];
  unicode.completeness = { status: "complete", gaps: [] };
  cases.push({ name: "unicode structural identifiers", document: unicode });

  // ADR 0009 byte oracle (docs/decisions/0009-numeric-canonical-form.md and
  // its implementation criteria): every case both as a document-level
  // extension value and nested inside an extension object/array. This
  // harness transports documents to Python as JSON text (`JSON.stringify`
  // below), which re-spells each JS number per ECMAScript's own fixed/
  // exponential threshold — not the literal shape it started with. That
  // reshaping turns "exponent-upper-threshold-fixed" (1e20) into a bare
  // digit-string integer literal (JS writes magnitudes up to 1e21 in fixed
  // form), which Python then correctly rejects as an out-of-domain integer
  // literal per ADR 0009 — not a cross-language divergence, but an artifact
  // of this test's JSON-text transport. Skip it here; the standalone
  // "numeric extension canonical bytes match the ADR 0009 oracle directly"
  // test below already covers it without a JSON-text round trip.
  for (const [name, value] of NUMERIC_BYTE_ORACLE.filter(
    ([caseName]) => caseName !== "exponent-upper-threshold-fixed",
  )) {
    const documentLevel = structuredClone(firstCase.document);
    documentLevel["x-value"] = value;
    cases.push({
      name: `numeric oracle: ${name} (document-level)`,
      document: documentLevel,
    });

    const nested = structuredClone(firstCase.document);
    nested.graphs[0]["x-nested"] = { list: [value] };
    cases.push({ name: `numeric oracle: ${name} (nested)`, document: nested });
  }

  // Not numerically sorted: proves extension array order is preserved, not
  // collection-sorted like structural fields, across both languages.
  const unsortedNested = structuredClone(firstCase.document);
  unsortedNested.graphs[0]["x-nested"] = {
    list: [-0, 1e21, 9007199254740992],
  };
  cases.push({
    name: "numeric oracle: extension array order preservation",
    document: unsortedNested,
  });

  // The retained F8/E1 minimized candidate (sha256 ee86a4ed...af9d22, see
  // the "retained F8/E1 minimized candidate" test below): full canonical
  // bytes and computed hash tuple must agree across languages, not just
  // this package's own algorithm/version fields.
  const f8e1 = JSON.parse(
    '{"topologyVersion":"0.1","provenance":{"generatedAt":"2000-01-01T00:00:00Z",' +
      '"producer":{"name":"a","version":"1"},"framework":{"name":"a","version":"1"}},' +
      '"producerLimitations":[],"structureHash":{"algorithm":"sha256",' +
      '"algorithmVersion":"1","value":' +
      '"0000000000000000000000000000000000000000000000000000000000000000"},' +
      '"graphs":[{"id":"a","structure":{"nodes":[],"edges":[],"joins":[],' +
      '"entryNodeIds":[],"exitNodeIds":[]}}],' +
      '"completeness":{"status":"complete","gaps":[]},"x-e1":0.0}',
  );
  cases.push({ name: "F8/E1 retained minimized candidate", document: f8e1 });

  const pythonProject = resolve(packageRoot, "../../python/spec");
  const script = [
    "import json, sys",
    "from agent_topology.spec import canonical_json, compute_structure_hash",
    "documents = json.load(sys.stdin)",
    "json.dump([{'canonical': canonical_json(document), 'hash': compute_structure_hash(document)} for document in documents], sys.stdout, separators=(',', ':'))",
  ].join("; ");
  const result = spawnSync(
    "uv",
    ["run", "--project", pythonProject, "python", "-c", script],
    {
      encoding: "utf8",
      input: JSON.stringify(cases.map(({ document }) => document)),
    },
  );
  assert.equal(result.status, 0, result.stderr);
  const evidence = JSON.parse(result.stdout);

  cases.forEach(({ name, document }, index) => {
    assert.equal(
      spec.canonicalStringify(document),
      evidence[index].canonical,
      name,
    );
    assert.deepEqual(
      spec.computeStructureHash(document),
      evidence[index].hash,
      name,
    );
  });
});

test("numeric extension canonical bytes match the ADR 0009 oracle directly", () => {
  /** @type {import("../dist/index.js").TopologyDocument} */
  const base = {
    topologyVersion: "0.1",
    provenance: {
      generatedAt: "2026-09-10T19:00:00Z",
      producer: { name: "test", version: "1" },
      framework: { name: "test", version: "1" },
    },
    producerLimitations: [],
    structureHash: {
      algorithm: "sha256",
      algorithmVersion: "1",
      value: "0".repeat(64),
    },
    graphs: [
      {
        id: "main",
        structure: {
          nodes: [],
          edges: [],
          joins: [],
          entryNodeIds: [],
          exitNodeIds: [],
        },
      },
    ],
    completeness: { status: "complete", gaps: [] },
  };

  for (const [name, value, expectedBytes] of NUMERIC_BYTE_ORACLE) {
    const documentLevel = structuredClone(base);
    documentLevel["x-value"] = value;
    assert.ok(
      spec
        .canonicalStringify(documentLevel)
        .includes(`"x-value":${expectedBytes}`),
      name,
    );

    const nested = structuredClone(base);
    const graph = nested.graphs[0];
    assert.ok(graph);
    graph["x-nested"] = { list: [value] };
    assert.ok(
      spec
        .canonicalStringify(nested)
        .includes(`"x-nested":{"list":[${expectedBytes}]}`),
      name,
    );
  }
});

test('the retained F8/E1 minimized candidate canonicalizes to "x-e1":0', () => {
  // Verbatim 479-byte minimized input from agent-topology-testbed
  // observations/E1/run-a/minimized (sha256 ee86a4ed...af9d22): a single
  // empty graph with "x-e1": 0.0, the retained F8 regression candidate.
  const raw =
    '{"topologyVersion":"0.1","provenance":{"generatedAt":"2000-01-01T00:00:00Z",' +
    '"producer":{"name":"a","version":"1"},"framework":{"name":"a","version":"1"}},' +
    '"producerLimitations":[],"structureHash":{"algorithm":"sha256",' +
    '"algorithmVersion":"1","value":' +
    '"0000000000000000000000000000000000000000000000000000000000000000"},' +
    '"graphs":[{"id":"a","structure":{"nodes":[],"edges":[],"joins":[],' +
    '"entryNodeIds":[],"exitNodeIds":[]}}],' +
    '"completeness":{"status":"complete","gaps":[]},"x-e1":0.0}\n';
  assert.equal(Buffer.byteLength(raw, "utf8"), 479);
  const document = JSON.parse(raw);

  // Acceptance and canonical bytes are recorded separately from the
  // (placeholder) stored hash: schema acceptance is not exercised here.
  const canonical = spec.canonicalStringify(document);
  assert.ok(canonical.endsWith('"x-e1":0}'));

  const hash = spec.computeStructureHash(document);
  assert.equal(hash.algorithm, "sha256");
  assert.equal(hash.algorithmVersion, "1");
});

test("non-finite numeric extensions are rejected, not silently reformatted", () => {
  for (const badValue of [NaN, Infinity, -Infinity]) {
    /** @type {import("../dist/index.js").TopologyDocument} */
    const document = {
      topologyVersion: "0.1",
      provenance: {
        generatedAt: "2026-09-10T19:00:00Z",
        producer: { name: "test", version: "1" },
        framework: { name: "test", version: "1" },
      },
      producerLimitations: [],
      structureHash: {
        algorithm: "sha256",
        algorithmVersion: "1",
        value: "0".repeat(64),
      },
      graphs: [
        {
          id: "main",
          structure: {
            nodes: [],
            edges: [],
            joins: [],
            entryNodeIds: [],
            exitNodeIds: [],
          },
        },
      ],
      completeness: { status: "complete", gaps: [] },
      "x-value": badValue,
    };
    assert.throws(() => spec.canonicalStringify(document), TypeError);
  }
});

test("canonicalization is immutable and ignores descriptive data when hashing", () => {
  /** @type {import("../dist/index.js").TopologyDocument} */
  const document = {
    topologyVersion: "0.1",
    provenance: {
      generatedAt: "2026-09-10T19:00:00Z",
      producer: { name: "test", version: "1" },
      framework: { name: "test", version: "1" },
    },
    producerLimitations: [],
    structureHash: {
      algorithm: "sha256",
      algorithmVersion: "1",
      value: "0".repeat(64),
    },
    graphs: [
      {
        id: "main",
        name: "before",
        structure: {
          nodes: [{ id: "b", interrupts: ["before", "after"] }, { id: "a" }],
          edges: [],
          joins: [{ id: "join", sources: ["b", "a"], target: "b" }],
          entryNodeIds: ["b", "a"],
          exitNodeIds: ["b"],
        },
      },
    ],
    completeness: { status: "complete", gaps: [] },
  };
  const original = structuredClone(document);
  const canonical = spec.canonicalizeDocument(document);
  assert.deepEqual(document, original);
  const canonicalGraph = canonical.graphs[0];
  assert.ok(canonicalGraph);
  assert.deepEqual(
    canonicalGraph.structure.nodes.map((node) => node.id),
    ["a", "b"],
  );
  assert.deepEqual(canonicalGraph.structure.nodes[1]?.interrupts, [
    "after",
    "before",
  ]);
  assert.deepEqual(canonicalGraph.structure.joins[0]?.sources, ["a", "b"]);

  const changed = structuredClone(document);
  const changedGraph = changed.graphs[0];
  assert.ok(changedGraph);
  changedGraph.name = "after";
  changed["x-example"] = { presentation: ["right", "left"] };
  assert.deepEqual(
    spec.computeStructureHash(document),
    spec.computeStructureHash(changed),
  );
});

test("validation enforces extensions, references, and completeness", () => {
  /** @type {import("../dist/index.js").TopologyDocument} */
  const valid = {
    topologyVersion: "0.1",
    provenance: {
      generatedAt: "2026-09-10T19:00:00Z",
      producer: { name: "test", version: "1" },
      framework: { name: "test", version: "1" },
    },
    producerLimitations: [],
    structureHash: {
      algorithm: "sha256",
      algorithmVersion: "1",
      value: "0".repeat(64),
    },
    graphs: [
      {
        id: "main",
        structure: {
          nodes: [{ id: "known" }],
          edges: [
            { id: "edge", source: "known", target: "known", kind: "direct" },
          ],
          joins: [],
          entryNodeIds: ["known"],
          exitNodeIds: ["known"],
        },
      },
    ],
    completeness: { status: "complete", gaps: [] },
    "x-example": { accepted: true },
  };
  assert.equal(spec.validateDocument(valid).valid, true);

  const invalidCore = structuredClone(valid);
  invalidCore.unexpected = true;
  assert.equal(spec.validateDocument(invalidCore).valid, false);

  const invalidExtension = structuredClone(valid);
  invalidExtension["x-Uppercase"] = true;
  assert.equal(spec.validateDocument(invalidExtension).valid, false);

  const document = structuredClone(valid);
  const graph = document.graphs[0];
  assert.ok(graph);
  const edge = graph.structure.edges[0];
  assert.ok(edge);
  edge.target = "missing";
  document.completeness.status = "incomplete";
  const result = spec.validateDocument(document);
  assert.equal(result.valid, false);
  assert.deepEqual(result.errors, [
    {
      path: "$.graphs[0].structure.edges[0].target",
      message: 'unknown node id "missing"',
    },
    {
      path: "$.completeness.status",
      message: 'must be "complete" when gaps contains 0 item(s)',
    },
  ]);
});

test("format, hash algorithm, and package versions are independent", () => {
  const schema = /** @type {any} */ (spec.loadSchema());
  assert.equal(schema.properties.topologyVersion.const, "0.1");
  assert.equal(spec.STRUCTURE_HASH_ALGORITHM_VERSION, "1");
  assert.throws(
    () => spec.computeStructureHash(/** @type {any} */ ({}), "2"),
    /unsupported structure hash algorithm version/,
  );
});
