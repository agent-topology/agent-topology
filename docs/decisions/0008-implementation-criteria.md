# ADR 0008 implementation criteria

These requirements are part of [accepted ADR 0008](0008-experimental-consumer-interpretation.md).
They refine T3–T6 without implementing them. Work targets `rc/0.1.0-beta.3`;
the evidence prerequisite is PR #108 at `db3b1873841739d3bb2e7968ecb187251116383f`.

## Shared gate for #97–#100

- Use graph-level `x-topology-interpretation` revision `"1"` with the requested
  `traversalDepth` and sorted, unique, visible `nodeId` records. Preserve fields
  implemented by other Tasks. Do not emit the testbed's trial extension.
- Use exactly the fact states, values, evidence kinds and reasons in ADR 0008
  and the separate extension schema. Unsupported/absent means no assertion.
- Validate the full document independently of the producer: existing core
  validation, extension schema, then the ADR's semantic/reference checks.
  Use the shared authored cases as a validation oracle, not as producer output.
- Construct minimum real graphs in Python and TypeScript. Record the inspected
  structural surface and supported framework version for every known fact.
  Node/router bodies raise if called; extraction must not call them.
- Compare states, values, identities, evidence kinds and deterministic ordering
  across languages. Source locators and package provenance may differ; record
  those differences. For identical documents both spec packages must agree on
  canonical bytes and hash. Reverse declaration order as a separate check.
- At depth 0, 1 and 2 test retained root identities and expanded child identities.
  Unmapped applicable child facts are `unknown/scope-not-inspected`. Never
  infer child identity from a flattened name or promise successful expansion.
- Adding/removing the extension must preserve core structure, entry/exit arrays,
  hash algorithm 1, gaps, strict-mode behavior and existing `x-langgraph` data.
  Keep beta.2 history intact. No package/version/release work belongs here.
- Document the new consumer interpretation as experimental and distinguish
  current implementation from published beta.2. Include legacy, invalid and
  unsupported-revision fallbacks. No core promotion or renderer product.

## T3 / #97: branch

Populate only `branch`:

| Minimum input | Required outcome |
| --- | --- |
| One source with two unconditional direct destinations | Known `all-declared`, evidence `unconditional-edges` after inspecting the complete declaration surface; no concurrency claim. |
| Same declared destination pair, callback returns one versus a list | Both `unknown/selection-not-observable`, including return annotations. |
| Conditional loop, Send routing, unknown destination router | Unknown; preserve existing local routing gap where applicable. |
| Same source has direct plus conditional or unresolved routing | Unknown, never known all-declared. |
| Join with two sources | Join alone never establishes a branch mode; no duplicated core edges. |
| Linear edge or terminal node | No branch fact. |
| Expanded source without matching inspected declarations | Unknown scope; do not promote drawable direct edges to proof. |

Validate at least two outgoing direct edges for all-declared, reject conditional
edges or a local unknown-routing-targets gap at the same source. Producer tests
must additionally detect dynamic declarations that a document cannot reveal.
Do not introduce exclusive or concurrent values in revision 1.

## T4 / #98: child graph

Populate only `subgraph`:

| Minimum input | Required outcome |
| --- | --- |
| One outer node containing a one-node compiled child at depth 0 | Known `opaque-child` with `compiled-child` evidence. |
| Ordinary node with the same ID and display name | Known `not-child` only if structural inspection rules out a child; otherwise unknown identity. |
| Wrapper obscuring compiled identity | `unknown/identity-unavailable`; no false negative. |
| Child remains opaque at positive depth | Opaque-child remains permitted with evidence. |
| Parent disappears during expansion | No dangling record for the removed parent. |
| Child/grandchild flattened without identity mapping | Unknown scope, retain expanded-subgraph-metadata gap. |

No invented `subgraphId` or child graph; reject an opaque-child assertion on a
node already linked by `subgraphId` to a materialized graph. Expansion is an
attempt offered by a consumer, not a guaranteed operation or completeness claim.
TaskGroup analogy and class/display names are not child evidence.

## T5 / #99: sentinels

Populate only `sentinel`. A one-task graph establishes known start/end through
framework-owned sentinel identity and ordinary through positive user-node
membership. Test user nodes named `start`, `end` and `__start__-user`; do not
classify them from strings. Failed identity inspection yields unknown, never
ordinary by default. Expanded child names do not inherit root roles.

Use a minimal document consumer assertion to select known sentinel records
without importing LangGraph or reading `x-langgraph`. Its presentation filter
must leave the source document byte-identical, retain original connection and
join provenance, and keep gaps visible. No new rendering/reconnection API is
required. Absent or invalid roles do not authorize hiding a node.

## T6 / #100: entries

Populate `entry` for every visible node in the inspected snapshot. Compute
`observedRoot` from edge **and join** targets, independent of `entryNodeIds`.
For LangGraph revision 1, confirmed START is known confirmed, confirmed END is
known not-entry, and remaining root-scope nodes are unknown entry-not-established.
Without a mapping to inspected scope, use unknown scope-not-inspected.

Use the minimal F2 graph (router plus undeclared target): preserve entry
candidates START and target, assert confirmed only for START, and leave the
unknown-routing-targets gap on router. Add a second unknown router only for the
no-causality test; do not assign either as the cause of a candidate root.
Test genuine start, disconnected candidates using authored documents if native
compilation rejects them, a join target, and a cycle with an incoming edge to a
confirmed entry in a contract example. Label authored cases separately from real
producer fixtures. Do not treat incoming edges as proof of not-entry.

Consumer migration guidance must say that legacy entry arrays are observed
candidates, absence is not a negative, and hash equality is not metadata equality.
Show local candidate uncertainty even when the core document is complete.
