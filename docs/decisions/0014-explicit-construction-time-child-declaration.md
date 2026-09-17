# 0014. Wrapped child calls get an explicit, construction-time declaration

- Status: Accepted
- Date: 2026-09-17
- Scope: workspace
- Issue: [#179](https://github.com/agent-topology/agent-topology/issues/179)

## Context

[ADR 0012](0012-nested-graph-identity-traversal-and-compatibility.md) defines
how a materialized child is identified: `_mapped_compiled_child` requires the
node's bound runnable to *be* a `CompiledStateGraph`, mapped by runtime
identity ("never by display name or wrapper inspection"). The
[2026-09-17 pre-beta review](../research/internal-consumer/pre-beta-review-2026-09-17/README.md)
(finding R2) found that campaign-agent's six real nested calls do not fit that
shape: `channel_concept` and `channel_production` each bind three node ids to a
plain function that calls `child.invoke(...)`, not to the compiled child
itself. `_mapped_compiled_child` returns `None` for all six, so every one stays
`subgraph: unknown/identity-unavailable` at every depth — full hierarchy
support is blocked, matching [Epic #178](https://github.com/agent-topology/agent-topology/issues/178)'s
first outcome ("Independent child inventory alone does not satisfy this").

This decision is bounded to the pinned first experiment named in
[#179](https://github.com/agent-topology/agent-topology/issues/179):
[`channel_concept._prepare_brief`](https://github.com/milocosmopolitan/campaign-agent/blob/62089cc4a0adcd3703b22583246bf05ff69efc37/src/campaign_agent/channel_concept/graph.py#L621-L648)
and its factory,
[`create_graph`](https://github.com/milocosmopolitan/campaign-agent/blob/62089cc4a0adcd3703b22583246bf05ff69efc37/src/campaign_agent/channel_concept/graph.py#L1485-L1714).
Reading all six call sites at the pinned commit
(`62089cc4a0adcd3703b22583246bf05ff69efc37`, matching the pre-beta review's
campaign baseline) confirms one uniform shape:

```python
def _prepare_brief(state, runtime: Runtime[RuntimeContext], *, child) -> dict[str, Any]:
    raw_input = {...}                          # input projection: derived, not passed through
    child_ctx = BriefPrepareRuntimeContext(...) # a narrower context type per call site
    try:
        final = child.invoke({"raw_input": raw_input}, context=child_ctx)
    except (InvalidInputError, ResumeDriftError) as exc:
        return {"last_error": ...}              # error translation into parent state
    return _fold_child_result(state, ..., final["result"], on_complete=_commit_brief)
```

with the identical pattern at
[`_draft_copy`](https://github.com/milocosmopolitan/campaign-agent/blob/62089cc4a0adcd3703b22583246bf05ff69efc37/src/campaign_agent/channel_concept/graph.py#L656-L680)/`_review_copy`,
and at channel_production's
[`_revise_copy`](https://github.com/milocosmopolitan/campaign-agent/blob/62089cc4a0adcd3703b22583246bf05ff69efc37/src/campaign_agent/channel_production/graph.py#L1046-L1070)/`_review_copy`/`_prepare_copy_feedback`.
Each factory registers its node as a lambda closing over the already-compiled
child object (e.g.
[`channel_concept/graph.py:1545-1556`](https://github.com/milocosmopolitan/campaign-agent/blob/62089cc4a0adcd3703b22583246bf05ff69efc37/src/campaign_agent/channel_concept/graph.py#L1545-L1556),
[`channel_production/graph.py:2487-2526`](https://github.com/milocosmopolitan/campaign-agent/blob/62089cc4a0adcd3703b22583246bf05ff69efc37/src/campaign_agent/channel_production/graph.py#L2487-L2526)).

## Method

Per [#178](https://github.com/agent-topology/agent-topology/issues/178)'s
non-goals, no model/notification/repository call is exercised and no full
campaign graph is run. A topology-owned probe (fake ports, one parent, one
child, mirroring the exact shape above) measures two candidates directly
against LangGraph 1.2.11 — the version pinned by both the campaign baseline and
this producer's supported range — instead of asserting behavior from source
reading alone. The probe is committed at
[`docs/research/internal-consumer/wrapped-child-contract-2026-09-17/`](../research/internal-consumer/wrapped-child-contract-2026-09-17/README.md)
and passes.

## Candidate 1: framework-visible composition

Two sub-forms were measured.

**1a. Direct node binding** (`builder.add_node(node_id, child)`, the shape
[ADR 0012](0012-nested-graph-identity-traversal-and-compatibility.md) already
recognizes). This requires the parent's own state schema to already contain
the child's exact input/output keys — there is no hook at which to run
`_prepare_brief`'s projection, so the probe pre-populates `raw_input` in the
*parent* state directly, which does not preserve derivation logic (e.g. the
`task_id` construction from `direction_id`/`run_id`/revision), it only
relocates it to a step the composition can no longer represent as one node.
Measured directly:

- **Context is not narrowed per call site.** A child compiled with
  `context_schema=ChildRuntimeContext` and composed directly into a parent
  compiled with `context_schema=ParentRuntimeContext` receives the *parent's*
  context object verbatim (`runtime.context` inside the child node was the
  literal `ParentRuntimeContext` instance, not a `ChildRuntimeContext`).
  Campaign's six call sites each construct a distinct, narrower context type
  per child (e.g. `BriefPrepareRuntimeContext`, `CopyRevisionRuntimeContext`);
  direct composition has no substitution point for that.
- **No interception point for error translation.** With no wrapping function,
  an `InvalidInputError` raised inside the child propagates uncaught out of
  the parent's `.invoke()` call; the probe's direct-binding bad-input case
  raises rather than folding into `last_error`, unlike the wrapped case.
- **Result folding is whatever the shared-key pass-through produces**, not an
  arbitrary reshape (`entry["brief"] = ...` alongside other roster fields).
- **Pause/resume works identically to the wrapped form** (see Candidate 2):
  this is the one property direct binding does not break.

**1b. LangGraph's own closure-based subgraph detection.** LangGraph populates
`PregelNode.subgraphs` (and thus `compiled.get_subgraphs()`) by walking a
node's bound callable for a `PregelProtocol` reachable through
`RunnableLambda`/`RunnableSequence` steps or, for a plain function, through
[`find_subgraph_pregel`/`get_function_nonlocals`](https://github.com/langchain-ai/langgraph)
— `inspect.getsource` plus an AST walk of the function body matched against
its closure and global variables. The probe confirms this **does** detect
campaign's exact shape: for a lambda closing over a keyword-bound child
(`lambda state, runtime: _prepare_brief(state, runtime, child=brief_child)`),
`node.subgraphs == [brief_child]`. It is nonetheless rejected as an evidence
source:

- It is source/AST inspection, not runtime identity — exactly the category
  [ADR 0012](0012-nested-graph-identity-traversal-and-compatibility.md)
  excludes ("never by ... wrapper inspection"), just performed by the
  framework instead of by this producer. Using it would mean topology's
  documented identity contract rides on an internal implementation detail of
  LangGraph's tracing/streaming support, not a stated contract of `describe()`.
- It degrades silently on ordinary refactors the AST walker cannot resolve.
  The probe shows two such cases: a child looked up through a subscript
  (`children["brief"]`) is invisible to it, because the walker only resolves
  direct names and dotted attribute chains, not container indexing; and a
  behaviorally identical rewrite of the *same* campaign shape — moving
  `child.invoke(...)` into a helper function that the outer `add_node`
  callable calls without repeating `child` in its own argument list — is also
  invisible, because `find_subgraph_pregel` only recurses into a nonlocal that
  is itself a `Runnable`/`PregelProtocol`, not into an ordinary function's own
  closure. Two logically identical wrappers give two different detection
  results. A producer whose identity evidence depends on incidental code shape
  is a regression risk 0012 was written to avoid, even though the failure mode
  is "falls back to unknown" rather than a false positive.

Neither sub-form of Candidate 1 preserves the required set (input projection,
context, error paths, result folding) for campaign's actual call sites.

## Candidate 2: an explicit, construction-time export contract

A new, minimal producer-owned helper, `declare_children`, lets the factory —
which already holds every child object as a local variable — state the
node-id-to-child mapping once, by direct object reference, right before
returning the compiled graph:

```python
def declare_children(compiled_graph, children: Mapping[str, CompiledStateGraph]):
    unknown = sorted(set(children) - set(compiled_graph.nodes))
    if unknown:
        raise ValueError(f"declare_children: not a node id in this graph: {unknown}")
    compiled_graph.__agent_topology_children__ = dict(children)
    return compiled_graph
```

Campaign's factories would call it once per graph, unchanged otherwise:

```python
return declare_children(
    builder.compile(name=graph_id),
    {"prepare_brief": brief_child, "draft_copy": draft_child, "review_copy": review_child},
)
```

`_mapped_compiled_child` gains a second, independent evidence branch: after
its existing direct-bound check, it also accepts
`compiled_graph.__agent_topology_children__.get(node_id)` when that value is a
`CompiledStateGraph` and the node's declared identity is still the one mapped
at that id. This is additive — the existing direct-bound path, id derivation,
collision handling, and depth-budget recursion in `_extract_graph` are
untouched.

The probe proves this candidate preserves everything Candidate 1 could not,
using the exact `_prepare_brief` shape (a keyword-bound child, a narrower
per-child `Runtime[Context]`, an app exception caught and folded into
`last_error`, and result folding into a differently-shaped parent field):

- **Input projection, context narrowing, error translation, result folding**:
  unaffected, because `declare_children` changes nothing about how the node
  function runs. It is a no-op at runtime — pure metadata read only by
  `describe()`.
- **Pause/resume and state ownership**: proven with a real
  `langgraph.types.interrupt()` inside the child, an `InMemorySaver`
  checkpointer, and `Command(resume=...)`, with **no explicit `config`
  forwarded** to `child.invoke(...)` (matching campaign's actual call). The
  first `.invoke()` returns `__interrupt__` from the child; resuming completes
  the child and folds its result into the parent's `entry` field correctly.
  LangGraph propagates the ambient checkpointer/thread/namespace to a
  synchronously nested `.invoke()` call through `RunnableConfig` context
  variables without any explicit forwarding, for both the wrapped and the
  directly-bound shape alike — this part of the Epic's concern was already
  satisfied by the existing pattern; the gap was only in `describe()`'s static
  identity evidence.
- **Depth behavior**: a two-level probe (`root` → `sub` → `grand`) with
  `declare_children` called on both the root and the intermediate compiled
  graph materializes `main:sub` at depth 1 and `main:sub:grand` at depth 2,
  through the unmodified recursive budget in `_extract_graph`.
- **Multiple uses of one child**: the same compiled leaf object declared at
  two sibling node ids (`left`, `right`) produces two independent materialized
  graphs `main:left`/`main:right`, per ADR 0012's existing position-derived id
  rule — no shared-definition fact is asserted, matching that ADR's minimum
  example matrix row for repeated child use.
- **Unknown fallback**: a node not present in `__agent_topology_children__`
  stays `unknown/identity-unavailable` at every depth, byte-for-byte identical
  to today's shipped output — this is strictly additive, not a behavior change
  for undeclared nodes.
- **Full document validity**: `describe(root, depth=0|1|2, strict=True)`
  followed by `agent_topology.spec.validate_document` passes at every depth
  with zero gaps, for all of the above cases together in one document.
- **Rejects a wrong declaration early**: declaring a node id that is not
  actually a node in the graph raises `ValueError` at construction time,
  rather than silently doing nothing.

## Comparison table

| Requirement | 1a. Direct binding | 1b. Closure detection | 2. `declare_children` |
| --- | --- | --- | --- |
| Input projection (`raw_input` derivation) | Not representable in one node | N/A (detection only, no composition change) | Preserved (unchanged) |
| Context narrowing per call site | Not possible — child sees the parent's context object | N/A | Preserved (unchanged) |
| `InvalidInputError`/`ResumeDriftError` → `last_error` | No interception point; propagates uncaught | N/A | Preserved (unchanged) |
| Result folding into a reshaped parent field | Only shared-key pass-through | N/A | Preserved (unchanged) |
| Pause/resume, state ownership | Works | Works (irrelevant — no composition change) | Works (proven with `interrupt()`/`Command(resume=...)`) |
| Evidence basis | Runtime identity (`bound is CompiledStateGraph`) | Source/AST inspection of closures | Runtime identity, explicitly declared |
| Fragility | N/A — requires rewriting the six call sites | Silently blind to non-attribute indirection (e.g. dict lookup) | None observed; wrong node id rejected at construction |
| Consistent with ADR 0012's evidence bar | Yes, but unusable here | No — source inspection, explicitly excluded | Yes |

## Decision

Adopt Candidate 2. `agent_topology.langgraph` gains one new public function,
`declare_children(compiled_graph, children) -> compiled_graph`. The producer's
`_mapped_compiled_child` recognizes a declared child as an equally valid,
independent evidence source alongside the existing direct-bound check.
Everything else in ADR 0012 — id derivation
(`f"{parent_graph_id}:{parent_node_id}"`), collision handling, the depth
budget, and the revision-2 `x-topology-interpretation` extension — is
unchanged; this decision only adds a second way to reach the same
`_mapped_compiled_child` return value ADR 0012 already defined.

### Evidence ownership

- **agent-topology (this repository) owns**: the `declare_children` API
  surface, the `_mapped_compiled_child` extension, the evidence-kind label for
  the new source (`declared-child-call`, alongside the existing
  `compiled-child`), and cross-language parity tracking.
- **campaign-agent (external, campaign-owned) owns**: calling
  `declare_children` once per factory, at the two call sites named below. No
  change to any `_prepare_brief`-shaped function, node behavior, or state
  schema.

### Call-site identifiers

Unaffected. A declared child's materialized `graphs[].id` is still derived
solely from `parent_graph_id` and the caller's own node id
(`"prepare_brief"`, `"draft_copy"`, ...), never from anything inside
`declare_children`'s mapping.

### Multiple uses of one child

Unaffected — proven above. `declare_children` records a per-node-id mapping,
so binding the same compiled child at two node ids already produces two
independent materialized graphs under the existing position-derived rule.

### Depth behavior

Unaffected. `declare_children` supplies evidence one level at a time — each
compiled graph, including an already-materialized child, must carry its own
declaration for its own children if it wraps a further nested call. This
composes correctly with the existing recursive depth budget in
`_extract_graph`, proven to depth 2 above.

### Unknown fallback

Unaffected and unchanged: any node without a matching entry in
`__agent_topology_children__` renders exactly as today,
`subgraph: unknown/identity-unavailable`, at every depth.

## Compatibility with ADR 0012

Compatible by addition, not superseded. ADR 0012's identity rule was "a
confirmed compiled child... mapped by runtime identity, never by display name
or wrapper inspection." A `declare_children` entry is a runtime identity
mapping — a direct object reference the factory itself provides — supplied
explicitly at construction time rather than inferred by inspecting the node's
bound callable. It satisfies the letter of that rule via a second concrete
mechanism, not a relaxation of it. Because it introduces a new accepted
evidence *kind* under
[ADR 0008](0008-experimental-consumer-interpretation.md)'s `subgraph`
interpretation (`declared-child-call`, in addition to the existing
`compiled-child`), this ADR is the narrowly superseding decision anticipated
by [#179](https://github.com/agent-topology/agent-topology/issues/179)'s
acceptance criteria for that case: it amends only the evidence vocabulary,
naming a second recognized way to reach `subgraph: opaque-child` at depth 0 or
`subgraph: materialized-child` at positive depth. No `subgraph` value, no
core schema field, and no compatibility guarantee from ADR 0012 changes.

## Package/repository changes required

**agent-topology (this repository, implemented by
[#180](https://github.com/agent-topology/agent-topology/issues/180), not
here):**

- `packages/python/langgraph/src/agent_topology/langgraph/_describe.py` —
  extend `_mapped_compiled_child` (lines 128-137) with the
  `__agent_topology_children__` branch; extend `_subgraph_interpretation`'s
  evidence-kind vocabulary with `declared-child-call`.
- `packages/python/langgraph/src/agent_topology/langgraph/__init__.py` (or a
  new `_children.py`) — add and export `declare_children`.
- New conformance fixtures under `packages/python/langgraph/tests/` covering
  the cases this ADR's probe already exercises (reuse, depth, unknown
  fallback, rejected unknown node id). #180 copies this decision's probe as
  its starting fixture oracle, per its own implementation guard.
- `packages/typescript/langgraph/src/internal.ts` — no currently known
  TypeScript consumer uses this pattern (both git-agent and the inspected
  campaign-agent are Python/LangGraph-Python). Deferred: track parity only
  if/when a TypeScript consumer demonstrates the same wrapped-child shape,
  consistent with [ADR 0005](0005-vendor-neutrality-is-provisional-at-v0.md)'s
  provisional-core caveat on evidence from a second framework or language.
- `docs/decisions/DECISIONS.md` — add this ADR to the router and index (done
  in this change).

**campaign-agent (external, campaign-owned, requested via a filed issue, not
implemented here):**

- `src/campaign_agent/channel_concept/graph.py`, `create_graph` (currently
  returning `builder.compile(name=graph_id)` at line 1714): wrap the return
  with `declare_children(..., {"prepare_brief": brief_child, "draft_copy":
  draft_child, "review_copy": review_child})`.
- `src/campaign_agent/channel_production/graph.py`, `create_graph`: same,
  with `{"revise_copy": revision_child, "review_copy": review_child,
  "prepare_copy_feedback": feedback_prepare_child}`.
- A version bound on `agent-topology-langgraph` sufficient to require the
  release that ships `declare_children` (topology assigns the exact version
  once #180 publishes it; campaign's issue records the dependency, not a
  guessed version number).
- No other file changes. No behavior change to any node function, state
  schema, or the six `child.invoke(...)` call sites themselves.

**git-agent:** no exact change identified. Its one implemented graph
(`issue_resolution`) has no wrapped child call in the reviewed evidence; no
external request is filed for it.

## What we are explicitly not doing

- Implementing `_mapped_compiled_child`'s extension, `declare_children`, or
  any conformance fixture in `packages/python/langgraph/src` or
  `packages/typescript/langgraph/src`. That is
  [#180](https://github.com/agent-topology/agent-topology/issues/180)'s scope;
  this decision supplies its fixture oracle.
- Changing any campaign-agent call site's behavior. `declare_children` is
  metadata read only by `describe()`; it does not run during a real
  invocation.
- Verifying at runtime that a declared node actually calls `.invoke()`/
  `.ainvoke()` on the object it declares. That would require executing user
  node bodies during extraction, which [#178](https://github.com/agent-topology/agent-topology/issues/178)
  explicitly excludes ("no ... graph execution during extraction"). A wrong
  declaration is a campaign-owned correctness bug in the same sense a wrong
  `graph_id` already is under [ADR 0011](0011-document-local-consumer-addressable-graph-ids.md);
  the one guard this decision does add is rejecting a declared node id absent
  from the graph, which is checkable without invoking anything.
- Adding TypeScript producer parity now. No TypeScript consumer exhibits this
  pattern; parity is deferred, not skipped.
- Claiming full six-call-site materialization for campaign. This decision
  fixes the contract using one bounded probe; #180 applies it to all six
  sites against the real, re-pinned factories and re-runs the 11-factory
  inventory.
- Reopening ADR 0012's id derivation, collision handling, or depth-budget
  rules. None of them changes.

## Consequences

- [#180](https://github.com/agent-topology/agent-topology/issues/180) is
  unblocked to implement `declare_children` and extend
  `_mapped_compiled_child`, using this ADR's probe as its fixture oracle, and
  to file/track the campaign-agent dependency this decision records.
- A new evidence kind, `declared-child-call`, joins
  `x-topology-interpretation`'s existing `compiled-child` vocabulary for the
  `subgraph` fact. No core schema, `topologyVersion`, or
  `structureHash.algorithmVersion` change.
- Campaign's six wrapped call sites remain unmaterialized until campaign
  applies `declare_children`, which is now a filed, linked dependency rather
  than an unstated blocker.

## Revisiting

Revisit the `declared-child-call` evidence kind if a real consumer's
`declare_children` call ever drifts out of sync with what a node function
actually invokes (a documentation/lint check in the consuming repository, not
a topology-side runtime verification, would be the first response). Revisit
the TypeScript deferral if a TypeScript consumer demonstrates the same
wrapped-child shape.
