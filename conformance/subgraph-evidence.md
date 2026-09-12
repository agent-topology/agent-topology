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
Root framework sentinels have no applicable child fact. Flattened names never
establish mapping, including child/grandchild nodes at requested depths 1 and 2.

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

Additional tests use a two-node child for expanded scope, retained root branching
for coexistence with branch facts, and a controlled drawable fallback over a real
compiled child for positive-depth opacity. The fallback is explicitly simulated;
it is not evidence that native expansion always fails or always succeeds. Full
core validation precedes separate schema and semantic validation; a materialized
child reference plus an opaque assertion is rejected. Python compares the entire
core extraction with child interpretation disabled, including gaps, entry/exit
arrays, `x-langgraph`, hash and strict-mode behavior. Both languages check hash
exclusion, visible records, reference validity and extension ordering.

Run the producer suites from [Conventions](../CONVENTIONS.md), including both
supported Python framework boundaries. The shared authored extension validation
oracle remains under `spec/experimental`; no public validator API is introduced.

## Measured traversal differences

Python expands a one-node child at positive depth. LangGraph.js 1.4.14 retains
that child opaque at both depths 1 and 2; it also retains a one-node outer child
at depth 1 when its grandchild has two nodes. The shared cases record those exact
TypeScript expectations rather than changing core extraction to force identity
parity. Two-node children expand in both producers, and a two-node grandchild
expands in both at depth 2. Their identities and unknown scope facts agree.
Thus requested depth is not evidence of expansion success. These native cases
also prove positive-depth opaque-child emission without the simulated fallback.
