# Experimental sentinel evidence

Current unreleased source implements only the `sentinel` fact added by #99 to
ADR 0008 revision 1. Existing branch and child fields are merged unchanged.
Published beta.2 does not emit these roles; no package version, core schema,
hash algorithm or historical release entry changes here.

| Producer / supported framework | Role and inspected structural evidence | Evidence source locator |
| --- | --- | --- |
| Python / LangGraph 1.2.10 and 1.2.11 | START is the compiled input channel and reserved node, with drawable data identical to its compiled bound object. END is the framework-created null drawable node, absent from compiled nodes. Both are absent from user builder membership. | `compiled.input_channels+nodes+get_graph.reserved-sentinels` |
| Python / LangGraph 1.2.10 and 1.2.11 | Ordinary requires positive builder membership and drawable data identical to the compiled node's bound object. | `compiled.builder.nodes+nodes.bound` |
| TypeScript / LangGraph.js 1.4.14 | START is the compiled input channel; `getGraphAsync` creates START/END as reserved schema nodes, absent from user builder membership. | `compiled.inputChannels+getGraphAsync.reserved-sentinels` |
| TypeScript / LangGraph.js 1.4.14 | Ordinary requires own builder membership and drawable data identical to that member's runnable. | `compiled.builder.nodes.runnable` |

These checks run only after the existing supported-version and compiled-class
gates. Framework `StateGraph.add_node` / `addNode` rejects its exact reserved
START and END constants; tests verify that ownership boundary. The producers
use those constants, not substring or display-name matching. Python's
`StateGraph.compile`, `Pregel.get_graph`, `_draw.draw_graph` and `_draw.add_edge`
provide the recorded surfaces. TypeScript's `CompiledGraph.getGraphAsync`
creates reserved schema nodes separately from the builder-node loop. No schema
validation or user function is invoked to classify a role.

[sentinel-cases.json](sentinel-cases.json) is a shared authored expectation
oracle, not captured producer output. Independent native runners build a one-task
graph, individual user-name counterexamples `start`, `end`, `__start__-user`,
and a two-node Unicode chain for code-point ordering under reversed node and edge
declarations. A two-node child plus one retained root is the minimum expansion
input needed to test child scope and retained identity in both languages at
requested depths 0, 1 and 2. The child deliberately uses sentinel-like names.
At depth 0 the child is an ordinary user node as well as an opaque subgraph;
at positive depths its expanded nodes are unknown scope. Removed parent records
do not survive. This does not promise that every child expands successfully.

Every node body raises if executed. Controlled replacements of drawable data
and the compiled input channel test failed identity/ownership separately from
native extraction. No missing membership defaults to ordinary. Missing identity
at depth 0 is `identity-unavailable`; unmapped non-sentinel nodes at positive
depth are `scope-not-inspected`. Failed reserved ownership remains
`identity-unavailable` at every depth.

Both native suites compare visible identities, states, values, evidence kinds,
requested depth and ordering against the same cases. Source locators listed above
and producer/framework provenance deliberately differ. The TypeScript suite sends
real producer documents to Python's independent core, extension-schema and
semantic validators; it also reads real Python output and checks semantic parity
and validity in TypeScript. Identical documents agree on canonical bytes and
algorithm-1 hashes. Both suites check extension hash exclusion, and Python
compares complete documents with sentinel annotation disabled to verify core,
entry/exit, gaps, strict behavior, `x-langgraph` and existing fact preservation.
Existing branch and child suites additionally test coexistence on retained nodes.

The framework-free [consumer assertion](../spec/tests/test_sentinel_consumer.py)
selects only supported-valid known start/end facts. It runs against real output
from both languages and an explicitly authored minimum document using non-LangGraph
IDs, one edge, one join and a gap attached to a hidden sentinel. Display selection
leaves source bytes unchanged, retains original edge/join objects and their
identities, and keeps completeness and limitations visible. Absent, unknown,
ordinary, missing, invalid and unsupported roles never authorize hiding. The
legacy shared core fixture remains unchanged. This is a test of presentation
policy, not a new public rendering or reconnection API.

Run the [Conventions](../CONVENTIONS.md) checks, the shared `spec/tests`, and both
supported Python framework boundaries. The separate extension schema and authored
validation cases remain the independent oracle; no production validator API is
added.
