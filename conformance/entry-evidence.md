# Experimental entry evidence

Current unreleased source adds `entry` to ADR 0008 revision 1 (#100), preserving
branch, child and sentinel facts. Published beta.2 has no such assertion. Core
schema, entry/exit arrays, algorithm 1, gaps, strict mode, `x-langgraph`, package
versions and beta.2 release history remain unchanged.

| Producer / supported framework | Inspected source locator | Affirmative entry evidence |
| --- | --- | --- |
| Python / LangGraph 1.2.10 and 1.2.11 | `compiled.input_channels+nodes+get_graph.reserved-sentinels` | START is the compiled input channel, absent from user builder membership, with drawable identity equal to its compiled bound object. END is the reserved null drawable node absent from compiled and builder nodes. |
| TypeScript / LangGraph.js 1.4.14 | `compiled.inputChannels+getGraphAsync.reserved-sentinels` | START is the compiled input channel; the supported framework creates reserved START/END schema nodes outside user builder membership. |

The existing compiled-class and supported-version gates precede inspection.
The shared internal identity classifier also powers sentinel facts; entry uses
its structural proof independently, without depending on sentinel metadata being
emitted. The framework-owned START is `known/confirmed` and END is
`known/not-entry`, both with `framework-entry` evidence. Positive root membership
maps retained ordinary nodes to inspected scope but never proves not-entry.
Every other inspected root node is `unknown/entry-not-established`. Unmapped
nodes at positive depth are `unknown/scope-not-inspected`, including flattened
child names. Failed reserved ownership never produces a known entry fact.
See the [sentinel evidence](sentinel-evidence.md) for the framework surfaces and
reserved-name counterexamples establishing this ownership boundary.

`observedRoot` is calculated independently from emitted edge **and join** targets,
never from the entry array, node name, routing gaps or a guessed cause. Incoming
connections cannot establish not-entry. Unknown facts add no gaps and do not
make a complete core incomplete.

[entry-cases.json](entry-cases.json) contains authored expectations and minimum
native graph recipes, not captured output. The Python and TypeScript entry
suites independently construct them with node/router bodies that raise if run:

- A one-task graph establishes genuine START, END and unknown ordinary entries.
  A conditional START with one successor named `start` separately proves that
  neither successor routing nor a sentinel-like user name confirms that entry.
- F2 uses only a router and undeclared target: both START and target remain core
  entry candidates, but only START is confirmed. The routing gap stays on router.
- A second unknown router is added only for the no-causality counterexample.
  Neither is linked to the candidate root by invented metadata or connections.
- Two upstream nodes and one join target prove incoming join connectivity does
  not imply a negative entry assertion or duplicated edges.
- A two-node child plus a retained root at depths 0, 1 and 2 measures expanded
  identities and retained scope. Two child nodes are the minimum both frameworks
  expand. Sentinel-like child names do not inherit root meaning; removed parents
  leave no records. Requested depth is not an expansion guarantee.
- A two-node Unicode chain proves code-point ordering, with reversed node and
  edge declarations checked separately for every recipe.

Controlled drawable-identity and compiled-input replacements are failure probes,
not native producer fixtures. They prevent false certainty when evidence fails.
Python additionally changes the legacy entry array before annotation to prove
that the observed-root calculation is independent of it. Disabling only entry
annotation and comparing complete documents proves preservation of all existing
facts, structure, gaps and framework extensions. Strict mode is exercised with
and without gaps; TypeScript retains its existing completeness-based consumer
policy and has no producer strict option.

Both suites validate the entire core, separate extension schema and semantic
references. They compare every visible identity, state, value, reason, evidence
kind, depth and deterministic order against the same oracle. The TypeScript
suite exchanges real documents with Python, validates in both languages and
compares canonical bytes and hashes for identical documents. Producer/framework
provenance and the source locators above intentionally differ across languages.

The [shared authored contract cases](../spec/experimental/interpretation-cases.json)
separately cover a disconnected root candidate in a complete graph, a confirmed
entry with an incoming cycle and no entry-array member, join connectivity, legacy
absence, invalid metadata and unsupported revisions. These are document examples,
not claimed native compiled graphs. Both specification suites validate them.
The [framework-free consumer assertions](../spec/tests/test_entry_consumer.py)
keep candidate uncertainty local even when the core is complete, never turn
absence into a negative, and preserve source bytes and hash semantics. They also
run on real documents from both producers.

Run the Conventions checks, `spec/tests`, and both supported Python framework
boundaries. Consumer migration is described in the
[entry guide](../docs/guides/consuming-documents.md#experimental-entry-interpretation).
