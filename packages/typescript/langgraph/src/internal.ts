import { readFileSync } from "node:fs";

import { CompiledStateGraph, END, START } from "@langchain/langgraph";
import {
  finalizeDocument,
  type MultiSourceJoin,
  type TopologyDocument,
  type TopologyEdge,
  type TopologyGraph,
  type TopologyNode,
} from "@agent-topology/spec";

import compatibility from "./compatibility.json" with { type: "json" };
import { UnsupportedLangGraphVersionError } from "./errors.js";

const PRODUCER_VERSION: string = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url), "utf8"),
).version;

const PRODUCER_LIMITATIONS = [
  {
    code: "dynamic-interrupts",
    message:
      "Interrupts raised inside node bodies cannot be observed statically.",
  },
] as const;

type EdgeKind = "conditional" | "direct";
type EdgeValue = readonly [source: string, target: string, kind: EdgeKind];

interface BuilderBranch {
  ends?: Record<string, string>;
}

interface BuilderNode {
  runnable: unknown;
  ends?: string[];
}

interface RuntimeBuilder {
  branches: Record<string, Record<string, BuilderBranch>>;
  edges: Set<readonly [string, string]>;
  nodes: Record<string, BuilderNode>;
  waitingEdges: Set<readonly [readonly string[], string]>;
}

interface DrawableNode {
  data: unknown;
  id: string;
  name?: string;
}

interface DrawableEdge {
  conditional: boolean;
  source: string;
  target: string;
}

interface DrawableGraph {
  edges: DrawableEdge[];
  nodes: Record<string, DrawableNode>;
}

interface RuntimeCompiledGraph {
  builder: RuntimeBuilder;
  getGraphAsync(options?: { xray?: boolean | number }): Promise<DrawableGraph>;
  getName(): string;
  interruptAfter?: readonly string[] | "*";
  interruptBefore?: readonly string[] | "*";
}

export interface DescribeOptions {
  depth?: number;
}

export function supportedRangeFromTestedVersions(
  testedVersions: readonly string[],
): string {
  if (testedVersions.length === 0) {
    throw new Error("the LangGraph.js compatibility manifest is empty");
  }
  return testedVersions.join(" || ");
}

export function ensureSupportedLangGraphVersion(
  installedVersion: string,
): string {
  if (!compatibility.testedVersions.includes(installedVersion)) {
    throw new UnsupportedLangGraphVersionError({
      installedVersion,
      supportedRange: supportedRangeFromTestedVersions(
        compatibility.testedVersions,
      ),
      testedVersions: compatibility.testedVersions,
    });
  }
  return installedVersion;
}

function compareText(left: string, right: string): number {
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

function edgeDocuments(values: readonly EdgeValue[]): TopologyEdge[] {
  const occurrences = new Map<string, number>();
  return [...values]
    .sort((left, right) => {
      for (const index of [0, 1, 2] as const) {
        const difference = compareText(left[index], right[index]);
        if (difference !== 0) return difference;
      }
      return 0;
    })
    .map(([source, target, kind]) => {
      const key = `${source}\0${target}\0${kind}`;
      const occurrence = (occurrences.get(key) ?? 0) + 1;
      occurrences.set(key, occurrence);
      return {
        id: `edge:${source}:${target}:${kind}:${occurrence}`,
        source,
        target,
        kind,
      };
    });
}

function builderStructure(compiledGraph: RuntimeCompiledGraph): {
  edges: TopologyEdge[];
  joins: MultiSourceJoin[];
  unknownRouters: Set<string>;
} {
  const values: EdgeValue[] = [...compiledGraph.builder.edges].map(
    ([source, target]) => [String(source), String(target), "direct"],
  );
  const unknownRouters = new Set<string>();

  for (const [source, branches] of Object.entries(
    compiledGraph.builder.branches,
  )) {
    for (const branch of Object.values(branches)) {
      if (branch.ends === undefined) {
        unknownRouters.add(String(source));
        continue;
      }
      for (const target of Object.values(branch.ends)) {
        values.push([String(source), String(target), "conditional"]);
      }
    }
  }

  for (const [source, node] of Object.entries(compiledGraph.builder.nodes)) {
    for (const target of node.ends ?? []) {
      values.push([String(source), String(target), "conditional"]);
    }
  }

  const joins = [...compiledGraph.builder.waitingEdges].map(
    ([rawSources, rawTarget]) => {
      const sortedSources = rawSources.map(String).sort(compareText);
      const [first, second, ...rest] = sortedSources;
      if (first === undefined || second === undefined) {
        throw new TypeError(
          "a multi-source join must contain at least two sources",
        );
      }
      const sources: [string, string, ...string[]] = [first, second, ...rest];
      const target = String(rawTarget);
      return {
        id: `join:${sources.join("+")}:${target}`,
        sources,
        target,
      };
    },
  );
  return { edges: edgeDocuments(values), joins, unknownRouters };
}

function drawableStructure(
  compiledGraph: RuntimeCompiledGraph,
  drawable: DrawableGraph,
): {
  edges: TopologyEdge[];
  joins: MultiSourceJoin[];
  unknownRouters: Set<string>;
} {
  const root = builderStructure(compiledGraph);
  const nodeIds = new Set(Object.keys(drawable.nodes));
  const joins = root.joins.filter(
    (join) =>
      nodeIds.has(join.target) &&
      join.sources.every((source) => nodeIds.has(source)),
  );
  const joinedPairs = new Set(
    joins.flatMap((join) =>
      join.sources.map((source) => `${source}\0${join.target}`),
    ),
  );
  const directDeclarations = new Set(
    root.edges
      .filter((edge) => edge.kind === "direct")
      .map((edge) => `${edge.source}\0${edge.target}`),
  );
  const values: EdgeValue[] = drawable.edges
    .filter((edge) => !joinedPairs.has(`${edge.source}\0${edge.target}`))
    .filter(
      (edge) =>
        !root.unknownRouters.has(edge.source) ||
        directDeclarations.has(`${edge.source}\0${edge.target}`),
    )
    .map((edge) => [
      String(edge.source),
      String(edge.target),
      edge.conditional ? "conditional" : "direct",
    ]);
  return {
    edges: edgeDocuments(values),
    joins,
    unknownRouters: root.unknownRouters,
  };
}

function includesInterrupt(
  configured: readonly string[] | "*" | undefined,
  nodeId: string,
): boolean {
  return configured === "*"
    ? ![START, END].includes(nodeId)
    : configured?.includes(nodeId) === true;
}

function nodeDocument(
  nodeId: string,
  node: DrawableNode,
  compiledGraph: RuntimeCompiledGraph,
): TopologyNode {
  const interrupts = [
    ...(includesInterrupt(compiledGraph.interruptBefore, nodeId)
      ? ["before" as const]
      : []),
    ...(includesInterrupt(compiledGraph.interruptAfter, nodeId)
      ? ["after" as const]
      : []),
  ];
  return {
    id: nodeId,
    ...(interrupts.length > 0 ? { interrupts } : {}),
    "x-langgraph": {
      sentinel: [START, END].includes(nodeId),
      ...(typeof node.name === "string" && node.name.length > 0
        ? { name: node.name }
        : {}),
    },
  };
}

function checkedDepth(options: DescribeOptions): number {
  const depth = options.depth ?? 0;
  if (!Number.isInteger(depth) || depth < 0) {
    throw new TypeError("depth must be a non-negative integer");
  }
  return depth;
}

function branchInterpretation(
  compiled: RuntimeCompiledGraph,
  drawable: DrawableGraph,
  graph: TopologyGraph,
  depth: number,
): void {
  const root = builderStructure(compiled);
  const dynamic = new Set(
    Object.entries(compiled.builder.branches)
      .filter(([, branches]) => Object.keys(branches).length > 0)
      .map(([source]) => source),
  );
  for (const [source, node] of Object.entries(compiled.builder.nodes)) {
    if (node.ends !== undefined) dynamic.add(source);
  }
  const extension = (graph["x-topology-interpretation"] ??= {
    version: "1",
    traversalDepth: depth,
    nodes: [],
  }) as { nodes: Array<{ nodeId: string; branch?: unknown }> };
  const records = new Map(
    extension.nodes.map((record) => [record.nodeId, record]),
  );
  const mappedIdentity = (nodeId: string) =>
    nodeId === START ||
    nodeId === END ||
    (Object.hasOwn(compiled.builder.nodes, nodeId) &&
      Object.hasOwn(drawable.nodes, nodeId) &&
      drawable.nodes[nodeId]?.data ===
        compiled.builder.nodes[nodeId]?.runnable);
  for (const nodeId of Object.keys(drawable.nodes)) {
    const outgoing = graph.structure.edges.filter(
      (edge) => edge.source === nodeId,
    );
    // Retained runnable identity, not a flattened display name, maps root scope.
    const mapped = mappedIdentity(nodeId);
    const declared = root.edges.filter((edge) => edge.source === nodeId);
    const signature = (edges: TopologyEdge[]) =>
      JSON.stringify(
        edges
          .map((edge) => JSON.stringify([edge.target, edge.kind]))
          .sort(compareText),
      );
    if (!(
      outgoing.length >= 2 ||
      outgoing.some((edge) => edge.kind === "conditional") ||
      (mapped && dynamic.has(nodeId))
    ))
      continue;
    let fact: unknown;
    if (!mapped) {
      fact = { status: "unknown", reason: "scope-not-inspected" };
    } else if (
      dynamic.has(nodeId) ||
      outgoing.some((edge) => edge.kind !== "direct")
    ) {
      fact = { status: "unknown", reason: "selection-not-observable" };
    } else if (
      depth > 0 &&
      (signature(outgoing) !== signature(declared) ||
        outgoing.some((edge) => !mappedIdentity(edge.target)))
    ) {
      fact = { status: "unknown", reason: "scope-not-inspected" };
    } else {
      fact = {
        status: "known",
        value: "all-declared",
        evidence: {
          kind: "unconditional-edges",
          source: "compiled.builder.edges+branches+nodes.ends",
        },
      };
    }
    const record = records.get(nodeId) ?? { nodeId };
    record.branch = fact;
    records.set(nodeId, record);
  }
  extension.nodes = [...records.values()].sort((a, b) =>
    compareText(a.nodeId, b.nodeId),
  );
}

function subgraphInterpretation(
  compiled: RuntimeCompiledGraph,
  drawable: DrawableGraph,
  graph: TopologyGraph,
  depth: number,
): void {
  const extension = (graph["x-topology-interpretation"] ??= {
    version: "1",
    traversalDepth: depth,
    nodes: [],
  }) as { nodes: Array<{ nodeId: string; subgraph?: unknown }> };
  const records = new Map(
    extension.nodes.map((record) => [record.nodeId, record]),
  );
  for (const node of graph.structure.nodes) {
    const nodeId = node.id;
    if (nodeId === START || nodeId === END || node.subgraphId !== undefined)
      continue;
    const runnable = Object.hasOwn(compiled.builder.nodes, nodeId)
      ? compiled.builder.nodes[nodeId]?.runnable
      : undefined;
    const mapped =
      runnable !== undefined && drawable.nodes[nodeId]?.data === runnable;
    let fact: unknown;
    if (!mapped) {
      fact = { status: "unknown", reason: "scope-not-inspected" };
    } else if (runnable instanceof CompiledStateGraph) {
      fact = {
        status: "known",
        value: "opaque-child",
        evidence: {
          kind: "compiled-child",
          source: "compiled.builder.nodes.runnable",
        },
      };
    } else {
      // Functions and wrappers may hide child invocation; absence is not proved.
      fact = { status: "unknown", reason: "identity-unavailable" };
    }
    const record = records.get(nodeId) ?? { nodeId };
    record.subgraph = fact;
    records.set(nodeId, record);
  }
  extension.nodes = [...records.values()].sort((a, b) =>
    compareText(a.nodeId, b.nodeId),
  );
}

export async function describeWithVersion(
  compiledGraph: unknown,
  installedVersion: string,
  options: DescribeOptions = {},
): Promise<TopologyDocument> {
  const frameworkVersion = ensureSupportedLangGraphVersion(installedVersion);
  if (!(compiledGraph instanceof CompiledStateGraph)) {
    throw new TypeError(
      "compiledGraph must be a CompiledStateGraph returned by StateGraph.compile()",
    );
  }
  const depth = checkedDepth(options);
  const runtimeGraph = compiledGraph as unknown as RuntimeCompiledGraph;
  const drawable = await runtimeGraph.getGraphAsync({ xray: depth });
  const nodeIds = Object.keys(drawable.nodes).map(String);
  const nodes = Object.entries(drawable.nodes).map(([nodeId, node]) =>
    nodeDocument(String(nodeId), node, runtimeGraph),
  );
  const { edges, joins, unknownRouters } =
    depth === 0
      ? builderStructure(runtimeGraph)
      : drawableStructure(runtimeGraph, drawable);
  const targets = new Set([
    ...edges.map((edge) => edge.target),
    ...joins.map((join) => join.target),
  ]);
  const sources = new Set([
    ...edges.map((edge) => edge.source),
    ...joins.flatMap((join) => join.sources),
    ...unknownRouters,
  ]);
  const name = runtimeGraph.getName();
  const graph: TopologyGraph = {
    id: "main",
    ...(typeof name === "string" && name.length > 0 ? { name } : {}),
    structure: {
      nodes,
      edges,
      joins,
      entryNodeIds: nodeIds.filter((nodeId) => !targets.has(nodeId)),
      exitNodeIds: nodeIds.filter((nodeId) => !sources.has(nodeId)),
    },
    "x-langgraph": { traversalDepth: depth },
  };
  branchInterpretation(runtimeGraph, drawable, graph, depth);
  subgraphInterpretation(runtimeGraph, drawable, graph, depth);
  const gaps: TopologyDocument["completeness"]["gaps"] = [...unknownRouters]
    .sort(compareText)
    .map((source) => ({
      code: "unknown-routing-targets",
      message: "Not every destination of this router could be determined.",
      element: { graphId: "main", kind: "node" as const, id: source },
    }));
  const rootNodeIds = new Set([
    START,
    END,
    ...Object.keys(runtimeGraph.builder.nodes),
  ]);
  if (depth > 0 && nodeIds.some((nodeId) => !rootNodeIds.has(nodeId))) {
    gaps.push({
      code: "expanded-subgraph-metadata",
      message:
        "Expanded child graphs expose drawable shape, but their join, routing, and interrupt declarations are not fully inspected.",
      element: { graphId: "main", kind: "graph", id: "main" },
    });
  }
  return finalizeDocument({
    topologyVersion: "0.1",
    provenance: {
      generatedAt: new Date().toISOString(),
      producer: {
        name: "@agent-topology/langgraph",
        version: PRODUCER_VERSION,
      },
      framework: { name: "langgraph", version: frameworkVersion },
      source: { kind: "compiled-object" },
    },
    producerLimitations: [...PRODUCER_LIMITATIONS],
    structureHash: {
      algorithm: "sha256",
      algorithmVersion: "1",
      value: "0".repeat(64),
    },
    graphs: [graph],
    completeness: {
      status: gaps.length > 0 ? "incomplete" : "complete",
      gaps,
    },
  });
}
