import { compareText } from "./canonical.js";
import type { GraphStructure } from "./types.js";

/** A connection belonging to an AND join, not an independently executing edge. */
export interface DerivedJoinEdge {
  joinId: string;
  source: string;
  target: string;
}

/**
 * Return fresh records from an already validated structure, sorted by joinId and
 * source in Unicode code point order without normalization. Validate the document
 * at the input boundary. Read both edges and joins; these links preserve AND
 * convergence and do not carry ordinary edge IDs/kinds or execution semantics.
 */
export function derivedJoinEdges(structure: GraphStructure): DerivedJoinEdge[] {
  return structure.joins
    .flatMap((join) =>
      join.sources.map((source) => ({
        joinId: join.id,
        source,
        target: join.target,
      })),
    )
    .sort(
      (left, right) =>
        compareText(left.joinId, right.joinId) ||
        compareText(left.source, right.source),
    );
}
