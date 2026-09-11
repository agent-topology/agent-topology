# `@agent-topology/spec`

Idiomatic TypeScript types and runtime utilities for the provisional agent-topology
v0.1 document contract. This package has no framework runtime dependency.

```bash
npm install @agent-topology/spec@0.1.0-beta.2
```

Supports Node.js 20+ with ESM imports. Start with the
[consumer guide](https://github.com/agent-topology/agent-topology/blob/main/docs/guides/consuming-documents.md)
for a runnable JSON-file example.

```ts
import {
  canonicalStringify,
  computeStructureHash,
  validateDocument,
  type TopologyDocument,
} from "@agent-topology/spec";

const result = validateDocument(value);
if (!result.valid) {
  console.error(result.errors);
} else {
  const document: TopologyDocument = result.document;
  console.log(canonicalStringify(document));
  console.log(computeStructureHash(document));
}
```

The repository root `spec/agent-topology.schema.json` remains the single checked-in
schema authority. The build generates TypeScript declarations from it and embeds a
copy for runtime validation. `topologyVersion`, the structure-hash algorithm version,
and this npm package's version are independent.
