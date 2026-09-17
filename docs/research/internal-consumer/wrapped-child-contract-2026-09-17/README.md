# Wrapped child call contract — decision evidence, 2026-09-17

Evidence for [ADR 0014](../../../decisions/0014-explicit-construction-time-child-declaration.md)
(issue [#179](https://github.com/agent-topology/agent-topology/issues/179)).
This directory does not implement anything in `packages/`; it is the "minimum
executable proof" #179 requires before the decision, and the fixture oracle
[#180](https://github.com/agent-topology/agent-topology/issues/180) copies
into its own implementation.

## Decision

Adopt an explicit, construction-time, runtime-identity declaration
(`declare_children`) as a second evidence source for
[ADR 0012](../../../decisions/0012-nested-graph-identity-traversal-and-compatibility.md)'s
materialized-child identity, additive to its existing direct-bound check.
Framework-native direct composition and LangGraph's own closure-based
subgraph detection were both measured and rejected. Full rationale, the
comparison table, and the exact package/repository changes required are in
[ADR 0014](../../../decisions/0014-explicit-construction-time-child-declaration.md).

## Bounded scope

Per [#179](https://github.com/agent-topology/agent-topology/issues/179), this
probe is one parent, one child, fake ports — not the full campaign graph, no
model/network/notification call, and no execution of any real campaign-agent
code. The pinned real shape it mirrors is
[`channel_concept._prepare_brief`](https://github.com/milocosmopolitan/campaign-agent/blob/62089cc4a0adcd3703b22583246bf05ff69efc37/src/campaign_agent/channel_concept/graph.py#L621-L648)
and its factory,
[`create_graph`](https://github.com/milocosmopolitan/campaign-agent/blob/62089cc4a0adcd3703b22583246bf05ff69efc37/src/campaign_agent/channel_concept/graph.py#L1485-L1714),
at campaign-agent commit `62089cc4a0adcd3703b22583246bf05ff69efc37` — the same
commit the [2026-09-17 pre-beta review](../pre-beta-review-2026-09-17/README.md)
pinned. All six wrapped call sites across `channel_concept` and
`channel_production` were read at that commit and confirmed to share this one
shape (see ADR 0014's Context section for each file:line).

## Probes

Each script is self-contained and asserts its own claims (`assert`, not just
printed output). All three pass at the pinned `langgraph==1.2.11` (matching
both this producer's supported range and the campaign baseline).

- [`probe_detection.py`](probe_detection.py) — does LangGraph's own
  closure-based subgraph detection (`PregelNode.subgraphs`,
  `get_subgraphs()`) see the wrapped-invoke pattern? Yes, for the exact
  campaign shape (a lambda closing directly over the child by keyword) — and
  no, for two behaviorally identical refactors of the same idiom (a child
  reached through a dict lookup; a child closed over by a helper function one
  level removed from the outer `add_node` callable). This is the evidence
  behind rejecting candidate 1b in ADR 0014.
- [`probe_behavior.py`](probe_behavior.py) — does each candidate preserve
  input projection, per-call-site context narrowing, `InvalidInputError`
  handling, result folding, and pause/resume? Runs a real
  `langgraph.types.interrupt()` inside the child with an `InMemorySaver`
  checkpointer and resumes with `Command(resume=...)`, with no explicit
  `config` forwarded to `child.invoke(...)` — matching campaign's actual call
  — for both the wrapped pattern and framework-native direct composition
  (candidate 1a). Direct composition passes pause/resume but fails input
  projection (no hook), context narrowing (the child receives the *parent's*
  context object verbatim — proven by handing it a context type missing a
  field the child reads, which then crashes with `AttributeError`), and error
  translation (an app exception raised inside the child propagates uncaught,
  with no fold point into a `last_error`-shaped field).
- [`probe_materialization.py`](probe_materialization.py) — with
  `_describe._mapped_compiled_child` given one additional branch that checks
  a `declare_children`-populated mapping, does `describe()` materialize
  correctly? Verifies, in one document, at depth 0/1/2: unchanged depth-0
  opaque output; correct materialization at depth 1 and depth 2 (a real
  grandchild case); the same compiled child reused at two sibling node ids
  producing two independent materialized graphs (`main:left`/`main:right`,
  neither asserting a shared-definition fact); a node with no declaration
  staying `unknown/identity-unavailable` at every depth, byte-identical to
  today; `agent_topology.spec.validate_document` and `strict=True` both
  passing with zero gaps at every depth; and `declare_children` rejecting a
  declared node id that is not actually a node in the graph.

## Reproduction

From the topology repository root:

```sh
rtk uv run --project packages/python/langgraph --group test python -B \
    docs/research/internal-consumer/wrapped-child-contract-2026-09-17/probe_detection.py
rtk uv run --project packages/python/langgraph --group test python -B \
    docs/research/internal-consumer/wrapped-child-contract-2026-09-17/probe_behavior.py
rtk uv run --project packages/python/langgraph --group test python -B \
    docs/research/internal-consumer/wrapped-child-contract-2026-09-17/probe_materialization.py
```

Each prints its findings and raises `AssertionError` if a claim above stops
holding (all three currently exit 0). `probe_materialization.py` monkeypatches
`agent_topology.langgraph._describe._mapped_compiled_child` in-process; it does
not modify any file under `packages/`.

## What this does not establish

- That campaign-agent's real six call sites, run end to end, behave exactly
  like this minimal probe — that is
  [#180](https://github.com/agent-topology/agent-topology/issues/180)'s
  acceptance, against the real, re-pinned factories.
- That a `declare_children` call is checked against what a node body actually
  invokes at runtime. It is not — see ADR 0014's "What we are explicitly not
  doing".
- Anything about git-agent, which has no wrapped-child call in the reviewed
  evidence.
