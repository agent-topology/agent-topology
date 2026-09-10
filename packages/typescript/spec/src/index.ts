export {
  STRUCTURE_HASH_ALGORITHM,
  STRUCTURE_HASH_ALGORITHM_VERSION,
  canonicalStringify,
  canonicalizeDocument,
  computeStructureHash,
  finalizeDocument,
} from "./canonical.js";
export {
  TopologyValidationError,
  assertTopologyDocument,
  isTopologyDocument,
  loadSchema,
  validateDocument,
} from "./validation.js";
export type {
  Completeness,
  ElementReference,
  GraphStructure,
  MultiSourceJoin,
  ProducerLimitation,
  StructureHash,
  TopologyDocument,
  TopologyEdge,
  TopologyGap,
  TopologyGraph,
  TopologyNode,
  TopologyProvenance,
} from "./types.js";
export type { ValidationIssue, ValidationResult } from "./validation.js";
