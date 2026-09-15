# `@agent-topology/langgraph`

Describe a supported compiled LangGraph.js `StateGraph` as the canonical document
representation from `@agent-topology/spec`.

```bash
npm install @agent-topology/spec@0.1.0-beta.4 @agent-topology/langgraph@0.1.0-beta.4
```

Supports Node.js 20+ and is ESM-only; synchronous `require()` is unsupported.
Install the specification peer explicitly. LangGraph.js 1.4.14 is installed as a
runtime dependency. Save JavaScript examples as `.mjs`, or use `.js` with
`"type": "module"`.
For a complete graph you can run without a model or API key, follow the
[quickstart](https://github.com/agent-topology/agent-topology/blob/main/docs/getting-started/typescript.md).

For an existing compiled graph in an ESM module:

```ts
import { describe } from "@agent-topology/langgraph";

const document = await describe(compiledGraph);
const expanded = await describe(compiledGraph, { depth: 1 });
const identified = await describe(compiledGraph, { graphId: "invoice-intake" });
```

The producer supports LangGraph.js 1.4.14. Other versions are refused before graph
inspection with an installation command for the tested release. The default depth is
zero, so nested graphs stay opaque. `graphId` is a non-empty document-local address
that defaults to `main`; choose a distinct stable value before composing several
outputs. Framework-only observations are emitted beneath
`x-langgraph`; producer-wide limitations and graph-specific element-local gaps remain
separate.

This package exposes no command-line executable.

CommonJS callers can use `await import("@agent-topology/langgraph")` inside an
async function, then await `describe(compiledGraph)`. Follow the
[complete CommonJS example with error handling](https://github.com/agent-topology/agent-topology/blob/main/docs/getting-started/typescript.md#use-it-from-commonjs).
For `ERR_PACKAGE_PATH_NOT_EXPORTED`, see
[ESM installation errors](https://github.com/agent-topology/agent-topology/blob/main/docs/guides/troubleshooting.md#esm-installation-errors).
