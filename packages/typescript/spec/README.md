# `@agent-topology/spec`

Idiomatic TypeScript types and runtime utilities for the provisional agent-topology
v0.1 document contract. This package has no framework runtime dependency.

```bash
npm install @agent-topology/spec@0.1.0-beta.3
```

Supports Node.js 20+ and is ESM-only; synchronous `require()` is unsupported.
Ajv and ajv-formats are runtime dependencies; hashing uses `node:crypto`. Start with the
[consumer guide](https://github.com/agent-topology/agent-topology/blob/main/docs/guides/consuming-documents.md)
for a runnable JSON-file example.

Save this as `inspect.mjs` next to a `topology.json` document and run
`node inspect.mjs` (or use `.js` with `"type": "module"`):

```javascript
import { readFileSync } from "node:fs";
import { canonicalStringify, validateDocument } from "@agent-topology/spec";

const value = JSON.parse(readFileSync("topology.json", "utf8"));
const result = validateDocument(value);
if (!result.valid) {
  console.error(result.errors);
  process.exitCode = 1;
} else {
  console.log(canonicalStringify(result.document));
}
```

For CommonJS, save this as `inspect.cjs` and run `node inspect.cjs`:

```javascript
const { readFileSync } = require("node:fs");

async function main() {
  const { canonicalStringify, validateDocument } =
    await import("@agent-topology/spec");
  const value = JSON.parse(readFileSync("topology.json", "utf8"));
  const result = validateDocument(value);
  if (!result.valid) {
    console.error(result.errors);
    process.exitCode = 1;
  } else {
    console.log(canonicalStringify(result.document));
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
```

Await the module namespace inside an async function; CommonJS has no top-level
`await`. Use named APIs from the public package root. For
`ERR_PACKAGE_PATH_NOT_EXPORTED`, see
[ESM installation errors](https://github.com/agent-topology/agent-topology/blob/main/docs/guides/troubleshooting.md#esm-installation-errors).
TypeScript consumers can also import the `TopologyDocument` type.

The repository root `spec/agent-topology.schema.json` remains the single checked-in
schema authority. The build generates TypeScript declarations from it and embeds a
copy for runtime validation. `topologyVersion`, the structure-hash algorithm version,
and this npm package's version are independent.

## Join connections (beta.3 candidate)

The registry-available beta.3 candidate exports `derivedJoinEdges(structure)`;
coordinated beta.2 does not. The repository's live installation guides move to beta.3
only after coordinated closeout.

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
