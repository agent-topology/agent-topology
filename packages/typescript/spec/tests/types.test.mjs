// @ts-check
import { strict as assert } from "node:assert";

/** @type {import("../dist/index.js").TopologyDocument} */
const document = {
  topologyVersion: "0.1",
  provenance: {
    generatedAt: "2026-09-10T19:00:00Z",
    producer: { name: "typed", version: "1" },
    framework: { name: "typed", version: "1" },
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
        nodes: [{ id: "node" }],
        edges: [],
        joins: [],
        entryNodeIds: ["node"],
        exitNodeIds: ["node"],
      },
    },
  ],
  completeness: { status: "complete", gaps: [] },
  "x-example": { typed: true },
};

assert.equal(document.topologyVersion, "0.1");
