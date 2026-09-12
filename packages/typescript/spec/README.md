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

## Join connections (unreleased)

Current source exports `derivedJoinEdges(structure)`; published beta.2 does not.

```typescript
import { derivedJoinEdges, type DerivedJoinEdge } from "@agent-topology/spec";

// After validateDocument(value) succeeds:
const links: DerivedJoinEdge[] = derivedJoinEdges(document.graphs[0].structure);
```

The helper returns one fresh `{joinId, source, target}` record per join source,
sorted first by `joinId`, then by `source`, using lexicographic Unicode code point
order (shorter prefixes first, without normalization or locale collation). Empty
joins produce an empty list. Input objects and arrays are not mutated.

Consumers must read both `structure.edges` and `structure.joins`. Derived links
retain their join identity even when endpoints coincide with another join or a
direct edge. They describe the original join's AND convergence: all its sources
are required. They do not imply independent edge execution. Keep them separate
from ordinary edges; no ordinary edge `id` or `kind` is assigned. Validate the
containing document at the input boundary; the helper does not validate again.
