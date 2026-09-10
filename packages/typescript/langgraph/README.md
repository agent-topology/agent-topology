# `@agent-topology/langgraph`

Describe a supported compiled LangGraph.js `StateGraph` as the canonical document
representation from `@agent-topology/spec`.

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
