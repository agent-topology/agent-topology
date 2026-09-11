import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import langGraphPackage from "@langchain/langgraph/package.json" with { type: "json" };

const probeUrl = pathToFileURL(
  resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../../../../docs/research/frameworks/langgraph/typescript",
    langGraphPackage.version,
    "probes/introspection.mjs",
  ),
).href;

test(`LangGraph.js ${langGraphPackage.version} exposes the producer introspection surfaces`, async () => {
  const { runIntrospectionProbes } = await import(probeUrl);
  await runIntrospectionProbes({ Annotation, END, START, StateGraph });
});
