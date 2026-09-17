# 0013. Sentinel/branch promotion bar remains unmet; publish a compatibility floor

- Status: Accepted
- Date: 2026-09-17
- Scope: workspace
- Issue: [#163](https://github.com/agent-topology/agent-topology/issues/163)

## Context

[ADR 0008](0008-experimental-consumer-interpretation.md) accepted
`x-topology-interpretation` revision `"1"` as "a bounded interpretation
experiment, not policy verdicts," and closed with an explicit promotion bar:

> Promotion requires a follow-up ADR, a real consumer demonstrating the need,
> independent producer evidence including a structurally different framework,
> positive/negative/unknown fixtures in independent languages, a reproducible
> validation story, and an explicit migration/version/hash-coverage decision.
> Airflow source review and two LangGraph language implementations alone do
> not meet that bar.

[ADR 0005](0005-vendor-neutrality-is-provisional-at-v0.md), still in force,
independently names the same two facts as suspected framework leaks: "The
sentinel entry and exit nodes are one framework's internal convention... Branch
and fan-out are represented identically because that framework represents them
identically." Its own revisiting condition is unchanged: "Promote beyond v0
when a producer reading a framework with a materially different structural
model exists." [ADR 0012](0012-nested-graph-identity-traversal-and-compatibility.md)
added revision `"2"`'s `materialized-child` value and reaffirmed the same bar
without weakening it: "Revision 2 remains bound by ADR 0008's promotion bar."

That bar was set against synthetic and internal-research evidence only
(#94/#96/#97/#99, the F1–F6 reproduction, Airflow source review). No real
downstream consumer had shipped against the extension. [Issue #163](https://github.com/agent-topology/agent-topology/issues/163)
supplies the first one: cordboard, a first-party consumer, tracks its own
unresolved requirements against this project as AT-2 (sentinel discrimination)
and AT-3 (fan-out parallel semantics) in
[`cordboard-upstream-requirements.md`](https://github.com/agent-topology/cordboard/blob/a64cf9a8afa654f50f47e8e0584b534f4256a3b6/docs/decisions/cordboard-upstream-requirements.md).
This decision re-reviews the ADR 0008 bar against that evidence, as #163
requests, without reopening #94/#96/#97/#99's accepted decisions, without
changing what revision `"1"`/`"2"` mean, and without adding interpretation
facts beyond sentinel/branch.

### What cordboard's evidence actually shows

At its current committed state (`a64cf9a8`, 2026-09-15 entry, lines 20-41),
cordboard records AT-2/AT-3 as "여전히 실험적 해석이다" (still experimental
interpretation) — it has not asked this project to promote them, only to
decide their status. Reading the two items directly:

- **AT-2** (lines 79-98): cordboard's viewer needs to know whether to draw
  `__start__`/`__end__`. Today it reads `x-langgraph.sentinel`, and the
  complaint is that this fact lives only in a framework-specific extension a
  framework-neutral reader cannot use. The stated consumer-visible effect is
  presentational — "뷰어가 `__start__`/`__end__`를 그릴지" (whether the viewer
  draws them) — not a correctness or safety decision.
- **AT-3** (lines 100-116, corrected 2026-09-12): cordboard's R3 rule is a
  *warning*, not a rejection, per cordboard's own ADR-0015 ("never block
  connection"). Line 177 records that R3 is judged from core
  `edges[].kind`/`nodes[].interrupts` alone, without reading the extension;
  the `x-topology-interpretation` `branch` fact only improves the warning's
  wording — an `unknown` branch surfaces as "cannot confirm" instead of an
  overclaim. Nothing in cordboard's own connection or execution path is
  gated on this fact.

This is real evidence "a real consumer demonstrating the need" — the first
of the six ADR 0008 promotion requirements is satisfied for the first time.
It does not touch the other five. Cordboard's own AT-2/AT-3 evidence is
LangGraph-only, produced by the same two language implementations ADR 0008
already held insufficient on their own. No structurally different framework
producer exists in this repository or in cordboard's integration surface.
ADR 0005's revisiting condition — a producer reading a framework "where an
edge list does not exist in the source at all, and connections are derived
rather than declared" — remains unmet. The migration/version/hash-coverage
decision the bar requires for an actual promoted field has, correctly, never
been drafted, because there is nothing yet to migrate to.

## Decision

### Promotion is declined at this time; the bar is unchanged, not reopened

Sentinel and branch facts stay exactly where ADR 0008 and ADR 0012 put them:
inside `x-topology-interpretation`, never in `graphs[].structure` or any other
core field. This is not a new restriction — it is the direct consequence of
ADR 0008's promotion bar and ADR 0005's provisional-core gate, both still
unmet by the only evidence #163 supplies. Cordboard's report moves one of six
requirements from "no real consumer" to "one real consumer, LangGraph-only";
it does not supply the structurally different framework either ADR names as
the load-bearing missing piece. Reopening #94/#96/#97/#99's shipped shape, or
promoting on partial satisfaction of the bar, is explicitly out of scope here
and is not what this ADR does.

### Compatibility floor for the experimental extension

What #163 actually asks for when promotion does not happen is "the
compatibility/versioning guarantee a consumer can build against without risk
of silent removal or shape changes across revisions." ADR 0008 already
implied most of this piecemeal; this ADR states it once, explicitly, as a
guarantee a consumer may rely on rather than an incidental producer rule:

1. **No in-place redefinition.** A shipped revision's fields, accepted
   values, evidence meanings, and array/ordering rules never change under the
   same revision number. Any such change is a new revision (as ADR 0008
   already required of producers); a consumer pinned to `"1"` or `"2"` is
   never retroactively broken by a narrative or behavioral change to that
   number.
2. **Forward opacity is permanent.** A reader that recognizes only revision
   `"1"` treats every later revision as unsupported and opaque — never as a
   parse error, a crash, or a silently coerced value — for as long as the
   extension exists in any revision. This restates ADR 0008's negotiation
   rule as a durable promise, not an implementation detail a future revision
   could quietly drop.
3. **No silent removal.** Withdrawing `sentinel`, `branch`, or the extension
   entirely requires a superseding ADR plus a package release carrying
   migration notes, published no later than the release that stops emitting
   it (already stated in ADR 0008; restated here as binding on this facts
   pair specifically, since #163 is precisely the consumer this protects).
   Silent removal — a package upgrade that stops emitting a fact with no ADR,
   no changelog entry, and no migration note — is a violation of this ADR,
   not merely of prior practice.
4. **The floor does not extend to core status.** None of the above implies or
   promises eventual promotion, a `topologyVersion` bump, or hash-algorithm
   coverage. Those stay gated by ADR 0005 and ADR 0008 exactly as before.
   Consumers building against the compatibility floor above must not treat it
   as a signal that promotion is coming.

### What would reopen promotion

Unchanged from ADR 0008, stated concretely against what #163 supplied: a
structurally different framework's producer independently implementing
sentinel and/or branch facts, per ADR 0005's test (edges derived rather than
declared). Short of that, further real-consumer evidence does not by itself
clear the bar — but evidence that a fact is load-bearing for a consumer's
*correctness or safety* path, rather than presentation quality as cordboard's
current AT-2/AT-3 usage is, would be a materially different kind of "need"
than what was reviewed here and would be worth a fresh re-review even before
a second framework arrives.

## Consequences

- Cordboard, and any other consumer, can pin to `x-topology-interpretation`
  revision `"1"`/`"2"` today with the four guarantees above, instead of
  treating "experimental" as "may vanish or reshape without notice."
- No schema, `topologyVersion`, hash-algorithm, or package change. No new
  interpretation fact. Revision `"1"`/`"2"` meanings are unchanged.
- `docs/decisions/DECISIONS.md`'s routing and index tables, and
  `ARCHITECTURE.md`'s "Accepted experimental interpretation" section, gain a
  pointer to this ADR alongside ADR 0008/0012.
- [#165](https://github.com/agent-topology/agent-topology/issues/165)'s
  beta.5 "explicit stability decision for sentinel/branch interpretation" is
  satisfied by this ADR: the decision is that they remain experimental, under
  the compatibility floor above, until a structurally different framework or
  a correctness-load-bearing consumer need reopens the question.

## What we are explicitly not doing

- Promoting `sentinel` or `branch` facts into the core schema, or committing
  to a timeline for doing so.
- Reopening #94/#96/#97/#99's accepted decisions, or ADR 0008/0012's already
  -shipped revision `"1"`/`"2"` shape.
- Changing what revision `"1"` or `"2"` currently mean, or any already-shipped
  behavior.
- Adding new interpretation facts beyond sentinel and branch.
- Lowering ADR 0008's promotion bar or ADR 0005's provisional-core gate. This
  ADR interprets them against new evidence; it does not weaken either.

## Revisiting

Revisit promotion when a structurally different framework's producer
implements sentinel and/or branch facts (ADR 0005's test), or when a real
consumer demonstrates that leaving either fact experimental blocks a
correctness- or safety-relevant decision rather than a presentation one.
Revisit the compatibility floor itself only through a superseding ADR, never
through an issue or PR comment, per `CONVENTIONS.md`.
