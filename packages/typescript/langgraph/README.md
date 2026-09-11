# `@agent-topology/langgraph`

Describe a supported compiled LangGraph.js `StateGraph` as the canonical document
representation from `@agent-topology/spec`.

```bash
npm install @agent-topology/spec@0.1.0-beta.1 @agent-topology/langgraph@0.1.0-beta.1
```

Supports Node.js 20+ with ESM imports. Install the specification peer explicitly.
For a complete graph you can run without a model or API key, follow the
[quickstart](https://github.com/agent-topology/agent-topology/blob/main/docs/getting-started/typescript.md).

```ts
import { describe } from "@agent-topology/langgraph";

const document = await describe(compiledGraph);
const expanded = await describe(compiledGraph, { depth: 1 });
```

The producer supports LangGraph.js 1.4.14. Other versions are refused before graph
inspection with an installation command for the tested release. The default depth is
zero, so nested graphs stay opaque. Framework-only observations are emitted beneath
`x-langgraph`; producer-wide limitations and graph-specific element-local gaps remain
separate.

This package exposes no command-line executable.
