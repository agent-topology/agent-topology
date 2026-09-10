import langGraphPackage from "@langchain/langgraph/package.json" with { type: "json" };
import type { CompiledStateGraph } from "@langchain/langgraph";
import type { TopologyDocument } from "@agent-topology/spec";

import { describeWithVersion, type DescribeOptions } from "./internal.js";

export { UnsupportedLangGraphVersionError } from "./errors.js";
export type { DescribeOptions } from "./internal.js";

export async function describe(
  compiledGraph: CompiledStateGraph<
    any,
    any,
    any,
    any,
    any,
    any,
    any,
    any,
    any,
    any
  >,
  options: DescribeOptions = {},
): Promise<TopologyDocument> {
  return describeWithVersion(compiledGraph, langGraphPackage.version, options);
}
