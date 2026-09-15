# Import-safe compiled-object export recipe

Evidence for [issue #153](https://github.com/agent-topology/agent-topology/issues/153),
advancing [#142](https://github.com/agent-topology/agent-topology/issues/142)
acceptance criterion 5. Recorded 2026-09-15. This is a research recipe, not a
new agent-topology contract; [the cross-consumer findings](../README.md#findings-across-consumers)
(IC-04, IC-05) remain the parent research context.

## What this recipe shows

[recipe.py](recipe.py) is a standalone, import-safe module: merely importing
it constructs nothing -- no graph, no LangGraph object, no I/O. It defines two
inert dataclasses, `FakePolicy` and `FakePorts`, standing in for a consumer
policy object and runtime ports (e.g. a model gateway), and one factory
function, `build_compiled_graph(*, graph_id, policy, ports)`, which is called
explicitly -- never at import time -- to compile a tiny two-node fixture graph
(`plan -> act`, no conditional routing, no checkpointer) and hand it to
`agent_topology.langgraph.describe`.

This mirrors, without invoking, the compile-time shape already inspected in
both consumers:

- campaign-agent's `campaign_contract.create_graph(*, graph_id: str, policy: CampaignContractPolicy)`
  ([source](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/src/campaign_agent/campaign_contract/graph.py#L662-L754)),
  which requires policy and uses graph ID as compile name and returns
  `builder.compile(name=graph_id)` without a checkpointer
  ([../campaign-agent/README.md](../campaign-agent/README.md)).
- git-agent's `issue_resolution.create_graph(*, graph_id: str, policy: IssueResolutionPolicy)`
  ([source](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/src/git_agent/graphs/issue_resolution/graph.py#L114-L256)),
  which validates the graph ID and policy and compiles without runtime
  resource access ([../git-agent/README.md](../git-agent/README.md)).

Neither factory is imported, invoked, or executed by this recipe: no
campaign-agent or git-agent source is read at runtime, no model gateway,
credential, checkpoint, or GitHub/notification effect is touched, and no
campaign-agent or git-agent workflow -- full or partial -- runs. `FakePolicy`
and `FakePorts` are this recipe's own inert stand-ins, not the real
`CampaignContractPolicy`, `IssueResolutionPolicy`, or
`agent_workflow_core.ports` types.

## Why "ports" alongside "policy"

Both real factories compile with only a `policy` argument; runtime ports
(git-agent's model gateway, GitHub, and notification adapters; campaign's
`agent_workflow_core.ports.ModelGateway`) are supplied later, per invocation,
through LangGraph's `context` parameter, never at compile time. `git-agent`'s
factory docstring makes this explicit ("without touching invocation-time
resources"), as does campaign's ("without a checkpointer and without touching
a model gateway, workspace, credential or runtime"). `build_compiled_graph`
accepts a `ports` argument anyway and rejects anything but `FakePorts`, so
that compile-time absence is an explicit, checked contract in this recipe
rather than something a consumer's own export module would have to remember
unaided.

## Why this is import-safe, and why that means no CLI target

`agt describe PATH.py:OBJECT` resolves `OBJECT` by executing the whole module
and then reading a module-level attribute
([`_load_target`/`_import_module`](https://github.com/agent-topology/agent-topology/blob/d9aee90a6259b5a4eaa874fdfa9da0d56c1ab082/packages/python/langgraph/src/agent_topology/langgraph/_cli.py#L111-L143)),
so a CLI-targetable module must construct its compiled object as an
import-time side effect -- exactly like git-agent's own LangGraph Studio
adapter, which assigns `graph = create_dev_graph()` at module scope
([dev/issue_resolution.py](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/dev/issue_resolution.py#L73-L76)).

This recipe deliberately does not do that. It stays import-safe by not using
the CLI target syntax at all: `main()` calls `build_compiled_graph` and
`describe` directly, through the same Python API a consumer's own export
module would use. This is the "consumer-owned import-safe export recipe
first" resolution IC-05 already recorded: it answers the factory-vs-CLI gap
without asking agent-topology's CLI to invoke a factory or accept
policy/port arguments.

It also demonstrates IC-04's distinction in miniature: `--graph-id` is passed
both as the LangGraph `compile(name=...)` display name and, separately and
explicitly, as `describe`'s document-local `graph_id`. Nothing makes those two
parameters agree by default; the recipe must (and does) set both.

## Running it

Needs `agent-topology-langgraph` (`packages/python/langgraph`) and its
`langgraph` dependency; no campaign-agent or git-agent checkout, package, or
network access.

```bash
uv run --project packages/python/langgraph \
  python docs/research/internal-consumer/import-safe-export/recipe.py --check
```

Prints a one-line `ok: ...` result and exits `0` once the recipe has compiled
the fixture graph from fake policy/ports, described it, and confirmed the
document validates against the canonical schema and reports
`provenance.source.kind == "compiled-object"`. Drop `--check` to print the
full canonical document instead:

```bash
uv run --project packages/python/langgraph \
  python docs/research/internal-consumer/import-safe-export/recipe.py
```

## Disposition

Advances IC-05 ("Consumer-owned import-safe export recipe first; new factory
CLI behavior is not automatically necessary") from `pending` to a documented,
runnable pattern: a compile-time factory shape identical to both inspected
consumers can be described without CLI factory invocation and without any
import-time side effect. It does not execute campaign-agent's or git-agent's
real graph, policy, or ports, does not prove their production entity wiring,
and does not change IC-03's runtime-interrupt finding or IC-04's
graph-ID-versus-compile-name finding for their actual graphs -- only this
recipe's own compiled object.
