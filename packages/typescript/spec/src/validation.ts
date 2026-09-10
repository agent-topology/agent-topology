import type { ErrorObject } from "ajv";
import { Ajv2020 } from "ajv/dist/2020.js";
import addFormats = require("ajv-formats");

import canonicalSchema from "./generated/agent-topology.schema.json" with { type: "json" };
import type { ElementReference, TopologyDocument } from "./types.js";

export interface ValidationIssue {
  readonly path: string;
  readonly message: string;
}

export type ValidationResult =
  | { readonly valid: true; readonly document: TopologyDocument }
  | { readonly valid: false; readonly errors: readonly ValidationIssue[] };

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats.default(ajv);
const validateSchema = ajv.compile<TopologyDocument>(canonicalSchema);

function cloneSchema(): object {
  return JSON.parse(JSON.stringify(canonicalSchema)) as object;
}

export function loadSchema(): object {
  return cloneSchema();
}

function schemaIssues(
  errors: ErrorObject[] | null | undefined,
): ValidationIssue[] {
  return (errors ?? [])
    .map((error) => ({
      path: error.instancePath === "" ? "$" : `$${error.instancePath}`,
      message: error.message ?? "is invalid",
    }))
    .sort(
      (left, right) =>
        left.path.localeCompare(right.path, "en") ||
        left.message.localeCompare(right.message, "en"),
    );
}

function duplicates(values: readonly string[]): string[] {
  const seen = new Set<string>();
  const duplicateValues = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) duplicateValues.add(value);
    else seen.add(value);
  }
  return [...duplicateValues].sort();
}

function issue(path: string, message: string): ValidationIssue {
  return { path, message };
}

function referenceIssues(document: TopologyDocument): ValidationIssue[] {
  const errors: ValidationIssue[] = [];
  const graphIds = document.graphs.map((graph) => graph.id);
  for (const duplicate of duplicates(graphIds)) {
    errors.push(
      issue("$.graphs", `duplicate graph id ${JSON.stringify(duplicate)}`),
    );
  }

  const graphById = new Map(document.graphs.map((graph) => [graph.id, graph]));
  const elementIds = new Map<
    string,
    Record<ElementReference["kind"], Set<string>>
  >();

  document.graphs.forEach((graph, graphIndex) => {
    const structure = graph.structure;
    const structurePath = `$.graphs[${graphIndex}].structure`;
    const nodeIds = structure.nodes.map((node) => node.id);
    const edgeIds = structure.edges.map((edge) => edge.id);
    const joinIds = structure.joins.map((join) => join.id);
    const knownNodes = new Set(nodeIds);
    elementIds.set(graph.id, {
      graph: new Set([graph.id]),
      node: knownNodes,
      edge: new Set(edgeIds),
      join: new Set(joinIds),
    });

    for (const [kind, ids] of [
      ["node", nodeIds],
      ["edge", edgeIds],
      ["join", joinIds],
    ] as const) {
      for (const duplicate of duplicates(ids)) {
        errors.push(
          issue(
            `${structurePath}.${kind}s`,
            `duplicate ${kind} id ${JSON.stringify(duplicate)}`,
          ),
        );
      }
    }

    const requireNode = (reference: string, path: string): void => {
      if (!knownNodes.has(reference)) {
        errors.push(
          issue(path, `unknown node id ${JSON.stringify(reference)}`),
        );
      }
    };
    structure.nodes.forEach((node, nodeIndex) => {
      if (node.subgraphId !== undefined && !graphById.has(node.subgraphId)) {
        errors.push(
          issue(
            `${structurePath}.nodes[${nodeIndex}].subgraphId`,
            `unknown graph id ${JSON.stringify(node.subgraphId)}`,
          ),
        );
      }
    });
    structure.edges.forEach((edge, edgeIndex) => {
      requireNode(edge.source, `${structurePath}.edges[${edgeIndex}].source`);
      requireNode(edge.target, `${structurePath}.edges[${edgeIndex}].target`);
    });
    structure.joins.forEach((join, joinIndex) => {
      join.sources.forEach((source, sourceIndex) =>
        requireNode(
          source,
          `${structurePath}.joins[${joinIndex}].sources[${sourceIndex}]`,
        ),
      );
      requireNode(join.target, `${structurePath}.joins[${joinIndex}].target`);
    });
    for (const field of ["entryNodeIds", "exitNodeIds"] as const) {
      structure[field].forEach((reference, referenceIndex) =>
        requireNode(reference, `${structurePath}.${field}[${referenceIndex}]`),
      );
    }
  });

  const expectedStatus =
    document.completeness.gaps.length === 0 ? "complete" : "incomplete";
  if (document.completeness.status !== expectedStatus) {
    errors.push(
      issue(
        "$.completeness.status",
        `must be ${JSON.stringify(expectedStatus)} when gaps contains ${document.completeness.gaps.length} item(s)`,
      ),
    );
  }
  document.completeness.gaps.forEach((gap, gapIndex) => {
    const element = gap.element;
    const path = `$.completeness.gaps[${gapIndex}].element`;
    const ids = elementIds.get(element.graphId);
    if (ids === undefined) {
      errors.push(
        issue(
          `${path}.graphId`,
          `unknown graph id ${JSON.stringify(element.graphId)}`,
        ),
      );
    } else if (!ids[element.kind].has(element.id)) {
      errors.push(
        issue(
          `${path}.id`,
          `unknown ${element.kind} id ${JSON.stringify(element.id)} in graph ${JSON.stringify(element.graphId)}`,
        ),
      );
    }
  });
  return errors;
}

export function validateDocument(value: unknown): ValidationResult {
  if (!validateSchema(value)) {
    return { valid: false, errors: schemaIssues(validateSchema.errors) };
  }
  const document = value as TopologyDocument;
  const errors = referenceIssues(document);
  return errors.length === 0
    ? { valid: true, document }
    : { valid: false, errors };
}

export function isTopologyDocument(value: unknown): value is TopologyDocument {
  return validateDocument(value).valid;
}

export class TopologyValidationError extends Error {
  readonly errors: readonly ValidationIssue[];

  constructor(errors: readonly ValidationIssue[]) {
    super(`invalid agent-topology document (${errors.length} issue(s))`);
    this.name = "TopologyValidationError";
    this.errors = errors;
  }
}

export function assertTopologyDocument(
  value: unknown,
): asserts value is TopologyDocument {
  const result = validateDocument(value);
  if (!result.valid) throw new TopologyValidationError(result.errors);
}
