# agent-topology

**A derived, descriptive manifest for the internal shape of an agent workflow.**

Status: **0.1 public preview** — provisional and pre-1.0. The four packages are
published independently, so registry availability may be partial until a coordinated
GitHub release is announced. See the [0.1 contract](docs/0.1-contract.md),
[changelog](CHANGELOG.md), and [Roadmap](#roadmap).

---

## What this is

Agent frameworks compile a workflow into a graph of nodes and edges. That structure
exists at runtime, but there is no common way to **publish** it.

`agent-topology` reads a compiled graph and emits a JSON document describing its shape:

```python
from agent_topology.langgraph import describe

doc = describe(compiled_graph)
```

```bash
agt describe src/my_agent/graph.py:graph --out agent-topology.manifest.json
```

That's the whole library.

## Installation

The public preview has four distinct installation paths. Pin the ecosystem-native
`beta.1` version when evaluating the initial release; if a registry does not yet list
it, that package's publication step is still pending.

| Package                             | Install                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------ |
| Python document utilities           | `python -m pip install "agent-topology-spec==0.1.0b1"`                               |
| Python LangGraph producer and `agt` | `python -m pip install "agent-topology-langgraph==0.1.0b1"`                          |
| TypeScript document utilities       | `npm install @agent-topology/spec@0.1.0-beta.1`                                      |
| TypeScript LangGraph.js producer    | `npm install @agent-topology/spec@0.1.0-beta.1 @agent-topology/langgraph@0.1.0-beta.1` |

The Python distributions install into the native namespace and are imported as
`agent_topology.spec` and `agent_topology.langgraph`. The TypeScript packages are
imported as `@agent-topology/spec` and `@agent-topology/langgraph`. Installing the
Python producer also installs its compatible specification dependency. The
TypeScript producer declares the specification as a peer, so install both explicitly.

### Python API

`agent_topology.langgraph.describe` accepts the `CompiledStateGraph` returned by
`langgraph.graph.StateGraph.compile()` and returns the canonical public `dict`
representation defined by `agent_topology.spec`:

```python
from agent_topology.langgraph import describe

document = describe(compiled_graph)
```

The LangGraph producer supports only releases with explicit conformance evidence.
The current tested range is 1.2.10 through 1.2.11; `describe` raises
`UnsupportedLangGraphVersionError` with an installation command before inspecting a
graph on any other release. The compatibility manifest drives the CI boundary matrix,
so widening package metadata also requires adding a tested release.

Pass the keyword-only `depth` option to expand nested graphs through that many
levels. It defaults to `0`, which leaves nested graphs opaque:

```python
document = describe(compiled_graph, depth=1)
```

Pass `strict=True` when the caller requires a graph-specific complete extraction:

```python
from agent_topology.langgraph import IncompleteTopologyError, describe

try:
    document = describe(compiled_graph, strict=True)
except IncompleteTopologyError as error:
    document = error.document
    # Map this producer-owned condition to a stable non-zero CLI exit status.
```

Strict mode raises `IncompleteTopologyError` only when the canonical document contains
one or more graph-specific `completeness.gaps`. Producer-wide
`producerLimitations` do not make a document incomplete and do not raise. The
exception's public `document` attribute contains the canonical incomplete document,
including its structure hash and gaps, so callers can report the same extraction
result without repeating completeness logic.

### Command line

Installing `agent-topology-langgraph` provides the `agt` executable. Its Foundation
command imports a Python file, resolves the named compiled graph object, and writes the
byte-stable canonical document without executing the graph:

```bash
agt describe path/to/graph.py:graph --out topology.json
```

The target syntax is `path.py:object`. Use `--strict` to require graph-specific
completeness. When gaps are present, strict mode still writes the canonical incomplete
document and exits with status 6.

`agt describe` uses stable, distinguishable process results:

| Status | Meaning                                                            |
| ------ | ------------------------------------------------------------------ |
| 0      | The canonical document was written successfully.                   |
| 2      | The command or target syntax is invalid.                           |
| 3      | The Python target file could not be imported.                      |
| 4      | The named object could not be resolved or is not a compiled graph. |
| 5      | The installed LangGraph version is unsupported.                    |
| 6      | Strict extraction found graph-specific completeness gaps.          |
| 7      | The output document could not be written.                          |
| 8      | Extraction failed for another reason.                              |

Importing a target executes its module-level Python statements so the compiled object
can be created. The CLI never invokes or schedules the graph itself.

Source code, uncompiled `StateGraph` builders, and runtime execution are not
accepted by this API. Producer-specific metadata is emitted only beneath the
`x-langgraph` extension key.

The Python distributions build as `agent-topology-spec` and
`agent-topology-langgraph`, imported as `agent_topology.spec` and
`agent_topology.langgraph`. Both `0.1.0b1` distributions are available from PyPI.
TypeScript applications can use `@agent-topology/spec` to
validate, canonicalize, serialize, and hash documents without a framework runtime.
They can use the async `describe` API from `@agent-topology/langgraph` to inspect a
compiled LangGraph.js graph:

```ts
import { describe } from "@agent-topology/langgraph";

const document = await describe(compiledGraph);
const expanded = await describe(compiledGraph, { depth: 1 });
```

The TypeScript producer currently supports LangGraph.js 1.4.14 and refuses other
versions before graph inspection with an actionable installation command. It has no
CLI; `agt` remains owned by the Python Foundation producer.

All four packages are built, qualified, and published as independent operations.
Repository CI inspects their exact public contents and metadata, installs the
artifacts in clean projects, and binds qualification to the source commit and artifact
digests. During the initial rollout, check the relevant registry before installing;
the coordinated announcement waits for all four. Maintainers use the
[release and partial-publication recovery guide](docs/releasing.md).

### Compatibility matrix

| Package                           | Runtime          | Framework compatibility |
| --------------------------------- | ---------------- | ----------------------- |
| `agent-topology-spec` 0.1.0b1            | Python 3.11–3.14 | No framework dependency |
| `agent-topology-langgraph` 0.1.0b1       | Python 3.11–3.14 | LangGraph 1.2.10–1.2.11 |
| `@agent-topology/spec` 0.1.0-beta.1      | Node.js 20+      | No framework dependency |
| `@agent-topology/langgraph` 0.1.0-beta.1 | Node.js 20+      | LangGraph.js 1.4.14     |

Only the versions listed above have conformance evidence. Producers refuse untested
framework releases before inspecting a graph.

### Interface support matrix

| Interface              | Python                                              | TypeScript                                        |
| ---------------------- | --------------------------------------------------- | ------------------------------------------------- |
| Contract utilities     | `agent_topology.spec`                               | `@agent-topology/spec`                            |
| LangGraph producer API | `agent_topology.langgraph.describe`                 | async `describe` from `@agent-topology/langgraph` |
| Command line           | `agt describe`, owned by `agent-topology-langgraph` | Not provided                                      |

There is no TypeScript `agt` command, producer discovery, or `agt diff` command in the
0.1 public preview.

For maintainers, see [Architecture](ARCHITECTURE.md),
[Conventions](CONVENTIONS.md), the
[architecture decision router](docs/decisions/DECISIONS.md), and the
[issue-planning model](docs/ISSUE-PLANNING.md). The
[Foundation retrospective](docs/retrospectives/0001-foundation-usable-python-producer.md)
records what this first implementation demonstrated and what remains provisional.

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

## First proven consumer

The repository's [topology-to-trace correlation example](examples/trace-correlation/README.md)
replays deterministic, sanitized evidence from a real LangGraph execution against a
canonical topology document. It distinguishes matched, unmatched, unobserved,
ambiguous, and insufficient evidence while preserving topology gaps and producer
limitations. Replay is offline and uses only Python's standard library.

This evidence does not expand the project into rendering, policy verdicts, or path
coverage; those remain outside the scope described below.

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

Namespaced keys carry anything the core doesn't. For example, this document
fragment adds producer-specific graph data:

```jsonc
{
  "topologyVersion": "0.1",
  "graphs": [
    {
      "id": "issue-resolver",
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

| Framework          | Status                                   |
| ------------------ | ---------------------------------------- |
| LangGraph (Python) | Foundation implemented (1.2.10–1.2.11)   |
| LangGraph.js       | TypeScript producer implemented (1.4.14) |
| LangChain (LCEL)   | planned                                  |
| others             | contributions welcome                    |

A producer is a function from a framework's compiled object to this document. It should
be small. If it needs configuration, the format is probably wrong.

---

## Conformance

`conformance/fixtures/` holds the ground truth. Each case is a graph description and the
document a correct producer must emit.

The provisional v0.1 contract is defined by the single canonical
[JSON Schema](spec/agent-topology.schema.json); its extension and validation
rules are summarized in the [contract README](spec/README.md).

```
conformance/fixtures/
├── linear-flow/
│   ├── fixture.json
│   └── expected.json
├── conditional-routing/
├── loop/
├── parallel-fanout/
├── nested-subgraph/
├── interrupt-before/
├── unknown-routing-targets/
└── multi-source-join/
```

Every producer runs the same fixtures. **This is how the format stays one format** —
without it, each producer drifts into its own dialect and the spec becomes a suggestion.

Fixtures are data, not test code. Producer-specific runners construct native framework
objects from the shared `fixture.json` recipes and compare core topology meaning with
the shared `expected.json` documents. They outlive any implementation.

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
- **Provisional core boundary.** Python and TypeScript exercise the same LangGraph
  model. That proves cross-language extraction, not vendor neutrality. Core fields may
  move before v1 when a structurally different producer supplies evidence.
- **Branch and fan-out semantics.** The current document can represent the resulting
  conditional shape but does not establish whether several destinations are
  alternatives or all run. It is not a path-coverage or policy-verdict format.
- **Framework-shaped sentinel nodes.** LangGraph entry and exit sentinels remain
  visible in the 0.1 producer output and are marked under `x-langgraph`.

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

**The 0.1 candidate is provisional.** Pre-1.0 changes follow the explicit format,
hash-algorithm, and package-version policy in the
[0.1 contract](docs/0.1-contract.md); do not treat it as a v1 stability promise.

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

[MIT](LICENSE). For public support, contribution guidance, and the private security
channel, see [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
