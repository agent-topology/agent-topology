import type { AgentTopologyDocument } from "./generated/contract.js";

export type TopologyDocument = AgentTopologyDocument;
export type TopologyProvenance = TopologyDocument["provenance"];
export type ProducerLimitation =
  TopologyDocument["producerLimitations"][number];
export type StructureHash = TopologyDocument["structureHash"];
export type TopologyGraph = TopologyDocument["graphs"][number];
export type GraphStructure = TopologyGraph["structure"];
export type TopologyNode = GraphStructure["nodes"][number];
export type TopologyEdge = GraphStructure["edges"][number];
export type MultiSourceJoin = GraphStructure["joins"][number];
export type Completeness = TopologyDocument["completeness"];
export type TopologyGap = Completeness["gaps"][number];
export type ElementReference = TopologyGap["element"];
