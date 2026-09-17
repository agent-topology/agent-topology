# Upgrade from beta.4 to beta.5

[Documentation home](../README.md) · [Release notes](../releases/v0.1.0-beta.5.md)

Status: **Prepared in source; not published.** The installation commands in
this repository's README, package READMEs, and quickstarts still select the
published beta.4 versions. This guide describes what changes for a beta.4
consumer once beta.5 passes registry verification; do not install these
candidate versions from a public registry before then.

## Select the packages

| Package | beta.4 → beta.5 candidate | Runtime | Framework |
| --- | --- | --- | --- |
| `agent-topology-spec` | `0.1.0b4` (unchanged) | Python 3.11–3.14 | None |
| `agent-topology-langgraph` | `0.1.0b4` → `0.1.0b5` | Python 3.11–3.14 | LangGraph 1.2.10–1.2.11 |
| `@agent-topology/spec` | `0.1.0-beta.4` (unchanged) | Node.js 20+ | None |
| `@agent-topology/langgraph` | `0.1.0-beta.4` → `0.1.0-beta.5` | Node.js 20+ | LangGraph.js 1.4.14 |

Only the two LangGraph producer packages move. Neither specification
package's schema, canonical model, or public API changed, so
`agent-topology-spec` and `@agent-topology/spec` stay on their already
published beta.4 versions — there is nothing to reinstall for them. The
Python producer's specification dependency
(`agent-topology-spec>=0.1.0b4,<0.2.0`) and the npm producer's specification
peer (`@agent-topology/spec@0.1.0-beta.4`) are both unchanged from beta.4.
LangGraph and LangGraph.js compatibility ranges are unchanged.

## No format or hash-algorithm change

`topologyVersion` stays `0.1` and `structureHash.algorithm` stays `1`. Every
change below is either a producer bug fix (the join-identity correction) or
a strictly additive extraction capability (`declare_children`); neither
redefines what the hash covers, how it orders collections, or the document
format.

## Join identities: a document you could not previously validate may now be valid

If your graph never declares more than one `add_edge(sources, target)` for
the same set of source node ids and target, and no node id contains a `+` or
`\` character, **nothing observable changes**: your producer output,
`structureHash`, and every join id are byte-identical to beta.4.

If your graph *does* declare an equivalent join more than once (the same
source set and target, in any order), beta.4's producer emitted a document
the independent validator rejected as containing a duplicate join id. beta.5
collapses those declarations into a single join record instead, matching
LangGraph's own runtime behavior (the target fires once regardless of how
many equivalently-grouped declarations produced the barrier). This is a
correction to previously invalid output, not a change to a previously valid
hash — there is nothing to migrate. If a source node id itself contains `+`
or `\`, its join-id segment is now escaped; this only affects graphs using
such node ids, and only in the join-source encoding.

One Python-specific case keeps its existing behavior: if your graph's join
sources collide under LangGraph's own internal `+`-delimited channel naming,
`agt describe` (and the underlying `describe()` call) continues to report
extraction failure — this is LangGraph's own construction failing before this
producer's logic runs, not something beta.5 changes.

See the
[join identity release note](../releases/v0.1.0-beta.5.md#join-identity-deduplication-and-unambiguous-encoding)
and [ADR 0015](../decisions/0015-join-identity-deduplication-and-unambiguous-encoding.md).

## `declare_children`: an opt-in way to expose a wrapped child call (Python only)

If your graph binds a child `CompiledStateGraph` directly to a node
(`builder.add_node(node_id, child)`), **nothing changes**: that identity
evidence is unaffected.

If instead your graph wraps a child call in a plain function — the shape
`describe()` could not previously identify, reporting
`subgraph: unknown/identity-unavailable` at every depth — you can now call
the new `agent_topology.langgraph.declare_children(compiled_graph, children)`
once in your factory, right before returning the compiled graph, to state the
node-id-to-child mapping explicitly:

```python
from agent_topology.langgraph import declare_children

return declare_children(
    builder.compile(name=graph_id),
    {"prepare_brief": brief_child, "draft_copy": draft_child},
)
```

This is opt-in and purely additive metadata read only by `describe()`; it
does not run during a real graph invocation and does not change any node
function, state schema, or call site. A node you do not declare keeps
rendering exactly as it does today. Declaring a node id that is not actually
present in the graph raises `ValueError` at construction time. This addition
is Python-only in beta.5; no TypeScript consumer currently exhibits the
wrapped-call shape it addresses, so `@agent-topology/langgraph`'s beta.5
build contains only the join-identity fix above.

See the
[declare_children release note](../releases/v0.1.0-beta.5.md#declare-children-an-explicit-construction-time-child-relationship-contract-python-only)
and [ADR 0014](../decisions/0014-explicit-construction-time-child-declaration.md).

## What is not verified

`declare_children`'s mapping is not checked against actual runtime
invocation — a declaration that does not match what a node function really
calls is a caller-owned correctness bug, the same way a wrong `graph_id`
already is. Dynamic `interrupt()`/resume behavior remains entirely outside
`describe()`'s static output in beta.5, as it always has. See
[known limitations and unverified claims](../releases/v0.1.0-beta.5.md#known-limitations-and-unverified-claims).
