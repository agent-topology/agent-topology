// Repository-only independent ADR 0008/0012 validator, never a public package API.
import { readFileSync } from "node:fs";
import { Ajv2020 } from "ajv/dist/2020.js";
const schemaV1 = JSON.parse(
  readFileSync(
    new URL(
      "../../../../spec/experimental/interpretation-v1.schema.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
const schemaV2 = JSON.parse(
  readFileSync(
    new URL(
      "../../../../spec/experimental/interpretation-v2.schema.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
const ajv = new Ajv2020({ strict: false });
/** @type {(value: unknown) => boolean} */
const validateV1 = ajv.compile(schemaV1);
/** @type {(value: unknown) => boolean} */
const validateV2 = ajv.compile(schemaV2);
const validators = { 1: validateV1, 2: validateV2 };
const key = "x-topology-interpretation";
/** @param {string} a @param {string} b */
const compare = (a, b) => {
  const left = Array.from(a, (c) => c.codePointAt(0) ?? 0);
  const right = Array.from(b, (c) => c.codePointAt(0) ?? 0);
  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    if (left[i] !== right[i]) return (left[i] ?? 0) - (right[i] ?? 0);
  }
  return left.length - right.length;
};
/** @param {any} document */
export function interpretationStatus(document) {
  const allowed = new Set(document.graphs);
  /** @param {any} value @returns {boolean} */
  function placement(value) {
    if (Array.isArray(value)) return value.some(placement);
    if (!value || typeof value !== "object") return false;
    return (
      (key in value && !allowed.has(value)) ||
      Object.entries(value).some(
        ([name, child]) => name !== key && placement(child),
      )
    );
  }
  if (placement(document)) return "invalid";
  let found = false;
  for (const graph of document.graphs) {
    if (!(key in graph)) continue;
    found = true;
    const extension = graph[key];
    const version =
      typeof extension?.version === "string" ? extension.version : undefined;
    if (version !== undefined && !(version in validators)) return "unsupported";
    const validate = validators[/** @type {"1" | "2"} */ (version ?? "1")];
    if (!validate(extension)) return "invalid";
    const nodes = new Map(
      graph.structure.nodes.map(
        /** @param {any} node */ (node) => [node.id, node],
      ),
    );
    const ids = extension.nodes.map(
      /** @param {any} record */ (record) => record.nodeId,
    );
    if (
      JSON.stringify(ids) !== JSON.stringify([...new Set(ids)].sort(compare)) ||
      ids.some(/** @param {any} id */ (id) => !nodes.has(id))
    )
      return "invalid";
    const targets = new Set(
      [...graph.structure.edges, ...graph.structure.joins].map(
        /** @param {any} edge */ (edge) => edge.target,
      ),
    );
    for (const record of extension.nodes) {
      const id = record.nodeId;
      if (record.entry && record.entry.observedRoot !== !targets.has(id))
        return "invalid";
      if (record.branch?.value === "all-declared") {
        const outgoing = graph.structure.edges.filter(
          /** @param {any} edge */ (edge) => edge.source === id,
        );
        const gap = document.completeness.gaps.some(
          /** @param {any} gap */ (gap) =>
            gap.code === "unknown-routing-targets" &&
            gap.element.graphId === graph.id &&
            gap.element.kind === "node" &&
            gap.element.id === id,
        );
        if (
          outgoing.length < 2 ||
          outgoing.some(
            /** @param {any} edge */ (edge) => edge.kind !== "direct",
          ) ||
          gap
        )
          return "invalid";
      }
      const child = record.subgraph?.value;
      const sentinel = record.sentinel?.value;
      if (
        child === "opaque-child" &&
        (nodes.get(id).subgraphId !== undefined ||
          ["start", "end"].includes(sentinel))
      )
        return "invalid";
      if (
        child === "materialized-child" &&
        nodes.get(id).subgraphId === undefined
      )
        return "invalid";
      if (
        (sentinel === "start" && record.entry?.value === "not-entry") ||
        (sentinel === "end" && record.entry?.value === "confirmed")
      )
        return "invalid";
    }
  }
  return found ? "valid" : "absent";
}
