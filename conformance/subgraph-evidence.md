# Experimental child identity evidence

Current source implements ADR 0008 revision 1 child facts; published beta.2 does
not emit them. No package, core schema, hash algorithm, or release history changes
are part of this work.

| Producer / supported framework | Inspected positive surface | Mapping to visible identity |
| --- | --- | --- |
| Python / LangGraph 1.2.10 and 1.2.11 | `compiled.nodes.bound`, an actual `CompiledStateGraph` instance | Drawable node data is the identical compiled bound object. |
| TypeScript / LangGraph.js 1.4.14 | `compiled.builder.nodes.runnable`, an actual `CompiledStateGraph` instance | Drawable node data is the identical builder runnable object. |

Those sources establish `known/opaque-child` only for a visible root child with
no materialized `subgraphId`. A class/display name is never evidence. Ordinary
functions and wrappers are counterexamples: both can hide child invocation, so
neither producer currently claims `not-child`. They report identity-unavailable.
Root framework sentinels have no applicable child fact.

[ADR 0012](../docs/decisions/0012-nested-graph-identity-traversal-and-compatibility.md)
retired framework drawable/`xray` traversal from both producers' positive-depth
extraction: neither producer flattens a child's descendants into the containing
graph any more. A confirmed compiled child instead keeps its own id in its
containing graph at every depth and, within the requested `depth` budget, gains a
core `subgraphId` addressing the child as its own materialized `graphs[]` entry,
extracted the same way a root graph is. `subgraph-cases.json`'s `expected` field
is therefore identical across both producers at every depth: no
`typescriptExpected` divergence remains, and both languages compare their real
producer output against each other for byte-identical canonical JSON and hashes.

[subgraph-cases.json](subgraph-cases.json) supplies shared expected meanings for
minimum real graphs built independently in the Python and TypeScript tests.
The one-node child, ordinary function with the same node ID/display name, hidden
wrapper, and grandchild cover depths 0, 1 and 2. Every user body raises if called.
Both languages compare identities, states, values and evidence kinds to that
same oracle, and test reverse declaration order. The TypeScript suite also
constructs real Python producer documents, checks them independently, and sends
its real documents to the Python specification for canonical byte and hash
comparison. Source locators above and
package/framework provenance intentionally differ across languages. Shared
specification authored cases independently assert the same canonical byte digest
and hash in both specification packages; they are not producer output.

Additional tests use a two-node child for expanded scope (asserting materialized
`graphs[]` entries and the retirement of `expanded-subgraph-metadata`), a reused
compiled child bound at two sibling node ids (independent, equal-structure
materialized graphs with no shared-definition assertion), and retained root
branching for coexistence with branch facts. A derived id collision is exercised
directly against the internal extraction primitive in both languages, seeding an
already-assigned id, because LangGraph's own node-name validation makes a
delimiter-caused collision impossible to construct through the public API in
either language; that impossibility is itself asserted. Full core validation
precedes separate schema and semantic validation; a materialized child reference
plus an opaque assertion is rejected. Python compares the entire core extraction
with child interpretation disabled, including gaps, entry/exit arrays,
`x-langgraph`, hash and strict-mode behavior. Both languages check hash
exclusion, visible records, reference validity and extension ordering.

Run the producer suites from [Conventions](../CONVENTIONS.md), including both
supported Python framework boundaries. The shared authored extension validation
oracle remains under `spec/experimental`; no public validator API is introduced.
