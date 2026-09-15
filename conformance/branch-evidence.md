# Branch interpretation evidence (ADR 0008 / #97)

This is current-source conformance evidence, not a beta.2 publication claim.
`branch-cases.json` contains shared recipes and expected semantic facts. Native
Python and TypeScript runners construct real compiled graphs independently;
these recipes are not the authored document examples in `spec/experimental`.

| Producer | Supported version | Complete declaration surface for known facts | Retained identity |
| --- | --- | --- | --- |
| Python LangGraph | 1.2.10, 1.2.11 | `compiled.builder.edges`, `branches`, and every node's `ends` | Drawable `data` is the compiled node's `bound` runnable. |
| LangGraph.js | 1.4.14 | `compiled.builder.edges`, `branches`, and every node's `ends` | Drawable `data` is the builder node's `runnable`. |

Both emit the stable locator `compiled.builder.edges+branches+nodes.ends` with
`unconditional-edges`. The locator names the combined inspection, not merely
an edge list. Nonempty branch declarations or dynamic node destinations
(including an explicitly empty destination mapping/list) disqualify a known
fact even when no corresponding conditional edge appears in the document.
Python's absent node destinations are an empty tuple; JavaScript uses undefined.
The framework-owned START node is mapped through its reserved root sentinel
mechanism. Ordinary retained sources and their direct destinations require object identity,
not display names.
[ADR 0012](../docs/decisions/0012-nested-graph-identity-traversal-and-compatibility.md)
retired framework drawable/`xray` traversal from both producers' positive-depth
extraction: a compiled child's own structure is now extracted the same way a
root graph's is, whatever its node count, so a one-node child materializes
identically in both languages. Rewritten-root tests still use a two-node child
for coverage of the retained root's own branch fact alongside a materialized
child, not to route around a language-specific limitation.

Known requires two outgoing ordinary direct declarations, no conditional or
dynamic declarations, and matching visible connections. Joins are inspected by
the existing core path and do not count toward direct fan-out. Since neither
producer flattens descendants into the root any more, the root's own branch
facts are unaffected by requested depth; a materialized child's own branch
facts are separate follow-up work, not populated by this contract. No callback,
router, or node body is invoked; all fixture bodies raise if called. Return
shapes/annotations describe the paired test inputs and never prove a mode.

The shared cases compare identities, states, values, reasons, evidence kinds,
and Unicode ordering at depths 0, 1, and 2, also reversing declaration order.
Additional nested tests verify materialized child/grandchild addressing and
retained root facts. Provenance differs by package name, package version
spelling, framework version, and extraction timestamp. These fields are not
used for semantic parity. Source locators currently agree; the contract permits
language-specific locators. Both producers now extract identical core drawable
structure at every requested depth; real producer documents are compared for
byte-identical canonical JSON and hashes across languages.

Python compares the complete document with the unmodified core extraction path,
removing only this extension and normalizing timestamps, including strict behavior.
Both languages independently validate core, extension shape and semantics and
verify hash exclusion. Existing shared core fixtures continue to assert core
shape, join identity and gaps. Both spec suites validate the same authored ADR
cases and canonical UTF-8 SHA-256 digests, proving equal bytes and hashes for
identical complete documents without substituting them for producer evidence.

Run:

```bash
rtk uv run --project packages/python/langgraph --group test pytest packages/python/langgraph/tests
rtk npm --prefix packages/typescript/langgraph run check
rtk uv run --project packages/python/spec --group test pytest spec/tests
rtk npm --prefix packages/typescript/spec run check
```

The compatibility CI matrix supplies each supported Python framework version.
No package, schema, release-history or hash-algorithm revision is introduced here.
