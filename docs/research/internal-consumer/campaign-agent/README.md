# campaign-agent

[Repository](https://github.com/milocosmopolitan/campaign-agent) ·
[Snapshot](snapshot.json) · [Cross-consumer findings](../README.md)

Latest recheck: [2026-09-17 declared children](review-2026-09-17-declared-children.md)
verifies all six `channel_concept`/`channel_production` wrapped-child
relationships materialize as real hierarchy links at the commit adopting
`declare_children`. This report and [review-2026-09-17.md](review-2026-09-17.md)
below remain immutable historical interpretations of their own older commits.

## Version and implemented boundary

No tags or GitHub releases were found. Baseline and inspected remote main:
`5593bb77558525f9292c11bcb77db43729dc0328`.
[Metadata](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/pyproject.toml) pins core main
`876f6a8a4ba863424e1f85bc92f18dce59147957`;
[lockfile](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/uv.lock) selects LangGraph `1.2.11`.

The implemented `campaign_contract` factory declares ordinary callable/model
nodes, conditional destinations, self-retry edges and terminal outcomes. It
returns `builder.compile(name=graph_id)` without a checkpointer.
[Factory source](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/src/campaign_agent/campaign_contract/graph.py#L662-L754).
This inspected graph is flat; its model wrappers are not compiled child graphs.

## Current gaps

| Finding | Source evidence | Consequence |
| --- | --- | --- |
| IC-03: human pause is dynamic | [await_decision](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/src/campaign_agent/campaign_contract/graph.py#L449-L469) calls `interrupt(proposal)` inside a wrapper-backed node. | Static interrupt metadata cannot identify this gate. Correlate runtime pause/resume evidence; do not infer absence of approval from an empty interrupts field. |
| IC-05/04: factory and document identity need integration | [Factory](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/src/campaign_agent/campaign_contract/graph.py#L662-L754) requires policy and uses graph ID as compile name. | Compile explicitly, then pass the intended ID separately to `describe`. For CLI use, export that compiled object from an import-safe module. |
| IC-06: retry paths are structural; budgets and decisions are not | [Conditional edges](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/src/campaign_agent/campaign_contract/graph.py#L715-L752) include draft self-loops and decision outcomes. | Topology can expose possible paths, but cannot prove attempt counts, decision authority, or which route ran. |

## Planned subgraph demand, not an implemented failure

[copy_brief_prepare](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/docs/graph-design/copy-brief-prepare.md#L1-L36)
is an approved subgraph design assigning child checkpoint namespaces and result
mapping to the parent. [channel_production](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/docs/graph-design/channel-production.md#L1-L40)
is explicitly a **draft** parent workflow; its child composition and human cycles
must not be reported as an already running workflow. The
[repository implementation note](https://github.com/milocosmopolitan/campaign-agent/blob/5593bb77558525f9292c11bcb77db43729dc0328/README.md) also distinguishes test fixtures
from production graph registration.

IC-02 becomes important when these parents are implemented: increasing depth
currently exposes flattened drawable shape with an `expanded-subgraph-metadata`
gap, not fully inspected child routing/joins/interrupts or separate child graph
records. A reusable child appearing in multiple parent positions will also need
an explicit distinction between graph definition ID, call-site identity and
runtime checkpoint namespace. That mapping is a **pending integration question**,
not a proven collision in the current source.

## Smallest useful follow-up

First reproduce one dynamic gate with one pause/resume and a fake decision.
For future composition use a synthetic parent/child/grandchild, a separate child
join, and one wrapper-hidden child; measure depth and identity independently of
campaign content. Keep factory implementation and approved-design changes in
campaign-agent issues, while recursive extraction belongs in agent-topology.
No campaign graph execution was performed for this source review.
