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
  inputChannels?: unknown;
  builder: RuntimeBuilder;
  getGraphAsync(options?: { xray?: boolean | number }): Promise<DrawableGraph>;
  getName(): string;
  interruptAfter?: readonly string[] | "*";
  interruptBefore?: readonly string[] | "*";
}

export interface DescribeOptions {
  depth?: number;
  graphId?: string;
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

function mappedCompiledChild(
  compiled: RuntimeCompiledGraph,
  drawable: DrawableGraph,
  nodeId: string,
): RuntimeCompiledGraph | null {
  // Mapped by runtime identity, never by display name or wrapper inspection.
  const runnable = Object.hasOwn(compiled.builder.nodes, nodeId)
    ? compiled.builder.nodes[nodeId]?.runnable
    : undefined;
  const mapped =
    runnable !== undefined && drawable.nodes[nodeId]?.data === runnable;
  if (!mapped || !(runnable instanceof CompiledStateGraph)) return null;
  return runnable as unknown as RuntimeCompiledGraph;
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

function checkedGraphId(options: DescribeOptions): string {
  const graphId = options.graphId === undefined ? "main" : options.graphId;
  if (typeof graphId !== "string" || graphId.length === 0) {
    throw new TypeError("graphId must be a non-empty string");
  }
  return graphId;
}

function interpretationVersion(graph: TopologyGraph): "1" | "2" {
  const hasMaterializedChild = graph.structure.nodes.some(
    (node) => node.subgraphId !== undefined,
  );
  return hasMaterializedChild ? "2" : "1";
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
    version: interpretationVersion(graph),
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
    version: interpretationVersion(graph),
    traversalDepth: depth,
    nodes: [],
  }) as { nodes: Array<{ nodeId: string; subgraph?: unknown }> };
  const records = new Map(
    extension.nodes.map((record) => [record.nodeId, record]),
  );
  for (const node of graph.structure.nodes) {
    const nodeId = node.id;
    if (nodeId === START || nodeId === END) continue;
    let fact: unknown;
    if (node.subgraphId !== undefined) {
      fact = {
        status: "known",
        value: "materialized-child",
        evidence: {
          kind: "materialized-subgraph-reference",
          source: "graphs[].id+node.subgraphId",
        },
      };
      const record = records.get(nodeId) ?? { nodeId };
      record.subgraph = fact;
      records.set(nodeId, record);
      continue;
    }
    const runnable = Object.hasOwn(compiled.builder.nodes, nodeId)
      ? compiled.builder.nodes[nodeId]?.runnable
      : undefined;
    const mapped =
      runnable !== undefined && drawable.nodes[nodeId]?.data === runnable;
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

function nodeIdentity(
  compiled: RuntimeCompiledGraph,
  drawable: DrawableGraph,
  nodeId: string,
  depth: number,
) {
  const data = drawable.nodes[nodeId]?.data;
  const member = Object.hasOwn(compiled.builder.nodes, nodeId);
  let fact: {
    status: string;
    reason?: string;
    value?: string;
    evidence?: { kind: string; source: string };
  } = {
    status: "unknown",
    reason: depth > 0 ? "scope-not-inspected" : "identity-unavailable",
  };
  if (nodeId === START || nodeId === END) {
    fact = { status: "unknown", reason: "identity-unavailable" };
    // The supported compiled graph creates schema nodes for reserved sentinels.
    if (
      compiled.inputChannels === START &&
      !member &&
      data !== null &&
      typeof data === "object" &&
      Object.hasOwn(data, "schema")
    ) {
      fact = {
        status: "known",
        value: nodeId === START ? "start" : "end",
        evidence: {
          kind: "framework-sentinel",
          source: "compiled.inputChannels+getGraphAsync.reserved-sentinels",
        },
      };
    }
  } else if (
    member &&
    data !== undefined &&
    data === compiled.builder.nodes[nodeId]?.runnable
  ) {
    fact = {
      status: "known",
      value: "ordinary",
      evidence: {
        kind: "ordinary-node",
        source: "compiled.builder.nodes.runnable",
      },
    };
  }
  return fact;
}

function sentinelInterpretation(
  compiled: RuntimeCompiledGraph,
  drawable: DrawableGraph,
  graph: TopologyGraph,
  depth: number,
): void {
  const extension = (graph["x-topology-interpretation"] ??= {
    version: interpretationVersion(graph),
    traversalDepth: depth,
    nodes: [],
  }) as { nodes: Array<{ nodeId: string; sentinel?: unknown }> };
  const records = new Map(
    extension.nodes.map((record) => [record.nodeId, record]),
  );
  for (const node of graph.structure.nodes) {
    const nodeId = node.id;
    const fact = nodeIdentity(compiled, drawable, nodeId, depth);
    const record = records.get(nodeId) ?? { nodeId };
    record.sentinel = fact;
    records.set(nodeId, record);
  }
  extension.nodes = [...records.values()].sort((a, b) =>
    compareText(a.nodeId, b.nodeId),
  );
}

function entryInterpretation(
  compiled: RuntimeCompiledGraph,
  drawable: DrawableGraph,
  graph: TopologyGraph,
  depth: number,
): void {
  const extension = (graph["x-topology-interpretation"] ??= {
    version: interpretationVersion(graph),
    traversalDepth: depth,
    nodes: [],
  }) as { nodes: Array<{ nodeId: string; entry?: unknown }> };
  const records = new Map(
    extension.nodes.map((record) => [record.nodeId, record]),
  );
  const targets = new Set([
    ...graph.structure.edges.map((edge) => edge.target),
    ...graph.structure.joins.map((join) => join.target),
  ]);
  for (const node of graph.structure.nodes) {
    const nodeId = node.id;
    const identity = nodeIdentity(compiled, drawable, nodeId, depth);
    let fact: unknown = {
      observedRoot: !targets.has(nodeId),
      status: "unknown",
      reason:
        identity.status === "known" || depth === 0
          ? "entry-not-established"
          : "scope-not-inspected",
    };
    if (identity.value === "start" || identity.value === "end") {
      fact = {
        observedRoot: !targets.has(nodeId),
        status: "known",
        value: identity.value === "start" ? "confirmed" : "not-entry",
        evidence: {
          kind: "framework-entry",
          source: identity.evidence!.source,
        },
      };
    }
    const record = records.get(nodeId) ?? { nodeId };
    record.entry = fact;
    records.set(nodeId, record);
  }
  extension.nodes = [...records.values()].sort((a, b) =>
    compareText(a.nodeId, b.nodeId),
  );
}

export async function extractGraph(
  compiledGraph: RuntimeCompiledGraph,
  graphId: string,
  remainingDepth: number,
  assignedIds: Set<string>,
): Promise<{
  graphs: [TopologyGraph, ...TopologyGraph[]];
  gaps: TopologyDocument["completeness"]["gaps"];
}> {
  const drawable = await compiledGraph.getGraphAsync({ xray: 0 });
  const nodeIds = Object.keys(drawable.nodes).map(String);
  const nodes = Object.entries(drawable.nodes).map(([nodeId, node]) =>
    nodeDocument(String(nodeId), node, compiledGraph),
  );
  const { edges, joins, unknownRouters } = builderStructure(compiledGraph);
  const targets = new Set([
    ...edges.map((edge) => edge.target),
    ...joins.map((join) => join.target),
  ]);
  const sources = new Set([
    ...edges.map((edge) => edge.source),
    ...joins.flatMap((join) => join.sources),
    ...unknownRouters,
  ]);
  const name = compiledGraph.getName();
  const graph: TopologyGraph = {
    id: graphId,
    ...(typeof name === "string" && name.length > 0 ? { name } : {}),
    structure: {
      nodes,
      edges,
      joins,
      entryNodeIds: nodeIds.filter((nodeId) => !targets.has(nodeId)),
      exitNodeIds: nodeIds.filter((nodeId) => !sources.has(nodeId)),
    },
    "x-langgraph": { traversalDepth: remainingDepth },
  };

  const gaps: TopologyDocument["completeness"]["gaps"] = [...unknownRouters]
    .sort(compareText)
    .map((source) => ({
      code: "unknown-routing-targets",
      message: "Not every destination of this router could be determined.",
      element: { graphId, kind: "node" as const, id: source },
    }));

  const descendants: TopologyGraph[] = [];
  if (remainingDepth > 0) {
    const nodeLookup = new Map(graph.structure.nodes.map((n) => [n.id, n]));
    const candidateIds = Object.keys(compiledGraph.builder.nodes).sort(
      compareText,
    );
    for (const nodeId of candidateIds) {
      const child = mappedCompiledChild(compiledGraph, drawable, nodeId);
      if (child === null) continue;
      const derivedId = `${graphId}:${nodeId}`;
      if (assignedIds.has(derivedId)) {
        gaps.push({
          code: "child-graph-id-collision",
          message:
            "A materialized child graph id would collide with an existing graph id; the child was left opaque.",
          element: { graphId, kind: "node" as const, id: nodeId },
        });
        continue;
      }
      assignedIds.add(derivedId);
      const node = nodeLookup.get(nodeId);
      if (node !== undefined) node.subgraphId = derivedId;
      const { graphs: childGraphs, gaps: childGaps } = await extractGraph(
        child,
        derivedId,
        remainingDepth - 1,
        assignedIds,
      );
      descendants.push(...childGraphs);
      gaps.push(...childGaps);
    }
  }

  branchInterpretation(compiledGraph, drawable, graph, remainingDepth);
  subgraphInterpretation(compiledGraph, drawable, graph, remainingDepth);
  sentinelInterpretation(compiledGraph, drawable, graph, remainingDepth);
  entryInterpretation(compiledGraph, drawable, graph, remainingDepth);

  return { graphs: [graph, ...descendants], gaps };
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
  const graphId = checkedGraphId(options);
  const runtimeGraph = compiledGraph as unknown as RuntimeCompiledGraph;

  const { graphs, gaps } = await extractGraph(
    runtimeGraph,
    graphId,
    depth,
    new Set([graphId]),
  );

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
    graphs,
    completeness: {
      status: gaps.length > 0 ? "incomplete" : "complete",
      gaps,
    },
  });
}
