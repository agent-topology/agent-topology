# agent-topology

**A derived, descriptive manifest for the internal shape of an agent workflow.**

Status: `draft` — the format is not stable. See [Roadmap](#roadmap).

---

## What this is

Agent frameworks compile a workflow into a graph of nodes and edges. That structure
exists at runtime, but there is no common way to **publish** it.

`agent-topology` reads a compiled graph and emits a JSON document describing its shape:

```python
from agent_topology import describe

doc = describe(compiled_graph)
```

```bash
agent-topology src/my_agent/graph.py:graph -o agent-topology.manifest.json
```

That's the whole library.

---

## What this is not

This distinction is the point of the project. Read it before proposing a feature.

|                               |                                                                                                                                                                                                                         |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Not an authoring format**   | You do not write graphs in this. Your framework's DSL stays your framework's DSL. This describes what you already built.                                                                                                |
| **Not hand-written**          | A human editing this file is a bug. It is derived from compiled code, and it drifts the moment it isn't.                                                                                                                |
| **Not a replacement for A2A** | [A2A Agent Card](https://a2a-protocol.org) answers _"how do I call this from outside?"_ — deliberately opaque about internals. This answers _"what does the inside look like?"_ Both can be served by the same process. |
| **Not a runtime**             | No execution, no scheduling, no state.                                                                                                                                                                                  |
| **Not a registry**            | No hosting, no discovery service, no index.                                                                                                                                                                             |
| **Not a viewer**              | Rendering is downstream. This is data.                                                                                                                                                                                  |

The closest analogy is **SBOM**. Nobody writes an SBOM by hand — the build emits it.
SPDX and CycloneDX succeeded because they described what already existed and left
production to tooling. Same posture here.

---

## Why it might be needed

Three things need the internal shape and none of them can get it today:

- **Observability** — a trace shows what ran. It cannot show what _could have_ run, which
  branch wasn't taken, or which node was skipped. That needs the definition.
- **Audit and review** — "does this workflow have a human approval step before it writes?"
  is a structural question. Answering it currently means reading source.
- **Portability** — comparing or migrating between orchestrators has no common
  intermediate description.

Each one currently reimplements framework-specific introspection.

---

## Scope

### In

Structural facts that exist in every orchestration framework:

```
nodes            identifiers, and type when the framework distinguishes them
edges            source, target, and whether the edge is conditional
entry / exit     start and terminal points
branches         conditional fan-out, with destinations when declarable
parallelism      fan-out groups
loops            cycles, represented honestly rather than flattened
subgraphs        nested graphs, opaque by default
interrupts       nodes that can pause for external input
provenance       what produced this document, from what, when
```

### Out

Anything that is a policy, a business rule, or specific to one product:

```
retry policy · model selection · cost budgets · triggers · approval routing
input schemas · secrets handling · deployment config · anything named after a vendor
```

These belong in **vendor extensions**, not the core.

### Extensions

Namespaced keys carry anything the core doesn't:

```jsonc
{
  "topologyVersion": "0.1",
  "graphs": [
    {
      "name": "issue-resolver",
      "structure": { "nodes": [], "edges": [] },
      "x-yourtool": { "whatever": "you need" },
    },
  ],
}
```

The core never interprets `x-*`. If a field is useful across three producers, propose
promoting it.

### The test for a core field

> Would Temporal, Airflow, CrewAI, and LangGraph all be able to emit this?

If no, it's an extension.

---

## Producers

| Framework        | Status                |
| ---------------- | --------------------- |
| LangGraph        | in progress           |
| LangChain (LCEL) | planned               |
| others           | contributions welcome |

A producer is a function from a framework's compiled object to this document. It should
be small. If it needs configuration, the format is probably wrong.

---

## Conformance

`conformance/fixtures/` holds the ground truth. Each case is a graph description and the
document a correct producer must emit.

```
conformance/fixtures/
├── linear-three-node/
│   ├── source.py
│   └── expected.json
├── conditional-branch/
├── retry-loop/
├── parallel-fanout/
├── nested-subgraph/
└── interrupt-before-write/
```

Every producer runs the same fixtures. **This is how the format stays one format** —
without it, each producer drifts into its own dialect and the spec becomes a suggestion.

Fixtures are data, not test code. They outlive any implementation.

---

## Known limits

Honesty about what derivation cannot see, because a partially accurate description is
more dangerous than an obviously absent one.

- **Dynamically routed destinations.** Some frameworks only know a conditional edge's
  targets if the author declares them. LangGraph, for instance, needs a `Command[Literal[...]]`
  return annotation for destinations to appear. Undeclared targets are absent from the
  output, and the document says so.
- **Deep nesting.** Subgraphs are opaque by default. Expanding them is opt-in and,
  in at least one framework, currently unreliable past two levels.
- **Runtime-constructed graphs.** A graph assembled from configuration at startup is
  described as it exists at that moment, not as all the graphs it might have been.

Every document carries a `completeness` field listing what the producer could not
determine. **Consumers must surface it.**

---

## Roadmap

```
0.1   format shaped by two real producers on real graphs
0.9   a second orchestrator emits it without changes to the core
1.0   the format has been stable across two consumers for six months
```

Beyond that, if adoption exists: write the specification document, register a
provisional well-known URI under RFC 8615, and only then discuss a generic name.
Names are earned, not claimed.

**The format will change before 0.1.** Do not build on it yet.

---

## Design principles

1. **Descriptive, never prescriptive.** Describe what exists. Define nothing.
2. **Derived, never authored.** If a human can edit it, it will drift.
3. **Complement, never compete.** A2A owns the outside. This owns the inside.
4. **Small enough to reimplement in an afternoon.** A format that needs a framework
   to read has already failed.
5. **Honest about gaps.** Say what could not be determined.

---

## License

MIT
