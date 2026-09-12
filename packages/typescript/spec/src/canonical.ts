import { createHash } from "node:crypto";

import type { StructureHash, TopologyDocument } from "./types.js";

export const STRUCTURE_HASH_ALGORITHM = "sha256" as const;
export const STRUCTURE_HASH_ALGORITHM_VERSION = "1" as const;

type JsonObject = { [key: string]: JsonValue };
type JsonValue = JsonObject | JsonValue[] | boolean | null | number | string;

function ordered(value: JsonValue): JsonValue {
  if (Array.isArray(value)) {
    return value.map(ordered);
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort(compareText)
        .map((key) => [key, ordered(value[key] as JsonValue)]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new TypeError("canonical JSON does not support non-finite numbers");
  }
  return value;
}

export function compareText(left: string, right: string): number {
  const leftPoints = [...left].map((character) => character.codePointAt(0)!);
  const rightPoints = [...right].map((character) => character.codePointAt(0)!);
  for (
    let index = 0;
    index < Math.min(leftPoints.length, rightPoints.length);
    index += 1
  ) {
    const difference = leftPoints[index]! - rightPoints[index]!;
    if (difference !== 0) return difference;
  }
  return leftPoints.length - rightPoints.length;
}

function serializeCanonical(value: JsonValue): string {
  if (Array.isArray(value)) {
    return `[${value.map(serializeCanonical).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value)
      .sort(compareText)
      .map(
        (key) =>
          `${JSON.stringify(key)}:${serializeCanonical(value[key] as JsonValue)}`,
      )
      .join(",")}}`;
  }
  const serialized = JSON.stringify(value);
  if (serialized === undefined) {
    throw new TypeError("canonical JSON supports JSON values only");
  }
  return serialized;
}

function cloneDocument(document: TopologyDocument): TopologyDocument {
  return ordered(document as JsonValue) as TopologyDocument;
}

function sortKey(value: unknown): string {
  return serializeCanonical(ordered(value as JsonValue));
}

function compareCanonical(left: unknown, right: unknown): number {
  return compareText(sortKey(left), sortKey(right));
}

export function canonicalizeDocument(
  document: TopologyDocument,
): TopologyDocument {
  const canonical = cloneDocument(document);

  for (const graph of canonical.graphs) {
    for (const node of graph.structure.nodes) {
      node.interrupts?.sort();
    }
    for (const join of graph.structure.joins) {
      join.sources.sort(compareText);
    }
    graph.structure.nodes.sort(compareCanonical);
    graph.structure.edges.sort(compareCanonical);
    graph.structure.joins.sort(compareCanonical);
    graph.structure.entryNodeIds.sort(compareText);
    graph.structure.exitNodeIds.sort(compareText);
  }
  canonical.graphs.sort(compareCanonical);
  return ordered(canonical as JsonValue) as TopologyDocument;
}

export function canonicalStringify(document: TopologyDocument): string {
  return serializeCanonical(canonicalizeDocument(document) as JsonValue);
}

function selectFields(
  value: Record<string, unknown>,
  fields: readonly string[],
): Record<string, unknown> {
  return Object.fromEntries(
    fields
      .filter((field) => field in value)
      .map((field) => [field, value[field]]),
  );
}

function projectStructureV1(document: TopologyDocument): JsonObject {
  const graphs = canonicalizeDocument(document).graphs.map((graph) => {
    const structure = graph.structure;
    return {
      id: graph.id,
      structure: {
        nodes: structure.nodes.map((node) =>
          selectFields(node, ["id", "type", "subgraphId", "interrupts"]),
        ),
        edges: structure.edges.map((edge) =>
          selectFields(edge, ["id", "source", "target", "kind"]),
        ),
        joins: structure.joins.map((join) =>
          selectFields(join, ["id", "sources", "target"]),
        ),
        entryNodeIds: structure.entryNodeIds,
        exitNodeIds: structure.exitNodeIds,
      },
    };
  });
  return { graphs } as JsonObject;
}

export function computeStructureHash(
  document: TopologyDocument,
  algorithmVersion: string = STRUCTURE_HASH_ALGORITHM_VERSION,
): StructureHash {
  if (algorithmVersion !== STRUCTURE_HASH_ALGORITHM_VERSION) {
    throw new RangeError(
      `unsupported structure hash algorithm version ${JSON.stringify(algorithmVersion)}; supported versions: ${STRUCTURE_HASH_ALGORITHM_VERSION}`,
    );
  }
  const payload = serializeCanonical(ordered(projectStructureV1(document)));
  return {
    algorithm: STRUCTURE_HASH_ALGORITHM,
    algorithmVersion: STRUCTURE_HASH_ALGORITHM_VERSION,
    value: createHash("sha256").update(payload, "utf8").digest("hex"),
  };
}

export function finalizeDocument(
  document: TopologyDocument,
  algorithmVersion: string = STRUCTURE_HASH_ALGORITHM_VERSION,
): TopologyDocument {
  const finalized = cloneDocument(document);
  finalized.structureHash = computeStructureHash(finalized, algorithmVersion);
  return canonicalizeDocument(finalized);
}
