# Issue plan for the pre-beta findings

Status: filed and adopted, 2026-09-17. The original planning drafts below are
retained for context; the linked GitHub issues are the current execution records.
Evidence: [review and reproducers](README.md).

## Filed issues

| Draft key | GitHub issue |
| --- | --- |
| C | [#178 — Consumer integration Epic](https://github.com/agent-topology/agent-topology/issues/178) |
| C1 | [#179 — Wrapped-child contract decision](https://github.com/agent-topology/agent-topology/issues/179) |
| C2 | [#180 — Campaign hierarchy implementation](https://github.com/agent-topology/agent-topology/issues/180) |
| C3 | [#181 — Real consumer correlation proof](https://github.com/agent-topology/agent-topology/issues/181) |
| J | [#182 — Join identity collision repair](https://github.com/agent-topology/agent-topology/issues/182) |
| D | [#183 — Support and hash documentation](https://github.com/agent-topology/agent-topology/issues/183) |

All six are assigned to beta.5. Native parents: #178 owns #179/#180/#181;
#166 owns #182/#183 alongside its existing release Tasks. Native blockers:
#180 waits for #179; #181 waits for #179/#180; #170 waits for #178/#182/#183
in addition to delivered #165. Existing #170 → #171 → #172 dependencies remain.
Milestone 9 and #166/#170/#171/#172 were updated to the expanded release outcome.
New issue bodies include Sonnet implementation guidance, pinned source evidence,
minimum inputs, explicit non-goals, decision gates and verification expectations.

## Recommended release outcome

Expand beta.5 to deliver valid collision-free producer output and evidence-backed
representation of the current campaign/git workflows, including campaign's six
parent-child relationships. This is a proposed change to milestone 9, which
currently requires a Python-only publication. Do not silently retain that old
package constraint or silently defer the consumer outcome.

Publish both changed producers; retain spec beta.4 packages only if the selected
solution leaves their contracts and implementation unchanged. Future Python
LangGraph 1.3/1.4 qualification remains under #177, outside this release. Current
framework baselines remain Python 1.2.10/1.2.11 and JavaScript 1.4.14.

The consumer contract decision may identify an additional package change. Record
that consequence before RC preparation rather than fixing a package set in advance.
If the intended release stays narrower, change its explicit outcome and move the
consumer Epic to a separate milestone; do not close it as satisfied by flat exports.

## Minimum issue set

Create six topology issues, retain the existing release Epic and its three Tasks.
No additional umbrella Epic or speculative implementation Tasks are needed.

| Key | Type | Proposed title | Parent | Native blocked-by | Release gate |
| --- | --- | --- | --- | --- | --- |
| J | Bug | Prevent duplicate and ambiguous join identifiers in both LangGraph producers | #166 (optional grouping) | None | Yes |
| D | Task | Align topology support and hash documentation with verified behavior | #166 | None | Yes |
| C | Epic | Represent and correlate the implemented campaign and git workflows | None | None | Yes, under proposed expanded outcome |
| C1 | Task | Decide an observable contract for campaign's wrapped child calls | C | None | Yes |
| C2 | Feature | Expose campaign parent-child topology without changing workflow behavior | C | C1 | Yes |
| C3 | Feature | Prove topology correlation across real consumer child calls and resume | C | C1, C2 for final nested proof | Yes |

Each Feature and Task has exactly one parent. Dependencies are separate native
relationships. C3's flat git capture can start while C1/C2 are open; C3 cannot close
before the nested campaign proof. External changes belong to owning repositories,
not this workspace's implementation branches.

## J — Prevent duplicate and ambiguous join identifiers in both LangGraph producers

Labels: `type:bug`, `area:conformance`, `area:langgraph-python`; use an existing
TypeScript area label if available. Proposed milestone: beta.5.

### Problem

At topology commit `344954ee2df167e84df8cf072f7d8c067707da88`, both producers return
invalid documents for two join declarations with sources `[a,b]` and `[b,a]` and
target `sink`: both records have `join:a+b:sink`. Strict extraction succeeds but
the independent spec validators reject the duplicate. JavaScript also collides
for distinct source sets `[a+b,c]` and `[a,b+c]`. The Python delimiter case fails
earlier in upstream drawable construction and must remain a distinct observation.

### Done when

- [ ] Establish repeated/permuted declaration semantics from supported framework
  behavior before choosing deduplication or occurrence identity. Record the
  decision and its hash/compatibility consequences; use an ADR if it changes an
  accepted contract. Do not assume duplicate declarations are semantically free.
- [ ] Both producers emit valid, uniquely addressable joins for supported inputs;
  distinct source sets cannot collapse through delimiter encoding.
- [ ] Upstream-unobservable input has an explicit, tested failure disposition,
  without inventing drawable structure or claiming it passed extraction.
- [ ] Minimum shared cases cover normal all-join versus independent incoming
  edges, permuted sources, repeated declarations, delimiter-bearing distinct
  source sets, and reversed declaration order. Use only necessary nodes.
- [ ] Semantically equivalent construction order yields identical canonical
  structure/hash. Existing valid fixtures keep their identities and hashes unless
  a justified migration is explicitly documented.
- [ ] Producer conformance independently validates output; a strict-mode success
  cannot hide these invalid documents in tests. Keep strict's gap semantics intact.
- [ ] Full supported-version producer suites pass in both languages; public API
  and CLI behavior for the Python failure case are covered.

### Verification / non-goals

Use the checked-in collision probes as failing baseline evidence, then shared
conformance and full producer suites. No generic graph-ID redesign, schema
relaxation, hash-algorithm change by assumption, or new runtime execution feature.
This can be one cohesive cross-language PR once semantics are decided; split a
decision Task only if that decision cannot be resolved within its existing ADRs.

## D — Align topology support and hash documentation with verified behavior

Labels: `type:task`, `area:docs`. Parent: #166. Proposed milestone: beta.5.

### Change / done when

- [ ] Publish the dated consumer review, snapshots and minimum reproducers in
  repository history; source links used by new issues point to committed evidence.
- [ ] Current navigation distinguishes the September 15 historical reports from
  the September 17 real-factory results. Preserve historical evidence rather than
  rewriting old support assertions as though they had been tested then.
- [ ] Add an explicit correction to ADR 0012's per-graph identical-hash wording:
  the public structure hash is document-scoped and includes graph IDs. Preserve
  the accepted call-site addressing decision; no new per-graph hash API is implied.
- [ ] Replace the configuration-is-a-format-problem README slogan with the actual
  producer responsibility and supported `graph_id`, `depth`, `strict` controls.
- [ ] Explain that graph-specific completeness, interpretation unknowns, dynamic
  interruptions, and successful runtime effects prove different things.
- [ ] Public documentation and relative-link checks pass. Link the open consumer
  work while it is incomplete; its eventual release notes belong to #170.

No broad style rewrite or subjective “AI-generated code” classification. This
Task can finish independently of C2/C3 by accurately documenting present limits.
If the evidence is already committed at filing time, mark that criterion supported
with its immutable commit rather than repeating the work.

## C — Represent and correlate the implemented campaign and git workflows

Label: `type:epic`. Proposed milestone: expanded beta.5.

### Outcome / success evidence

- [ ] All ten campaign factories and git's issue_resolution have validated
  topology from actual compiled factories at pinned consumer commits.
- [ ] All six campaign child call sites have evidenced relationships and retain
  parent identity. Independent child inventory alone does not satisfy this.
- [ ] One real nested call and each consumer's real pause/resume path correlate
  to topology while preserving graph/run/node/occurrence distinctions.
- [ ] Consumer and topology package versions, extraction commands and remaining
  limitations are reproducible. Any required external change is merged and pinned,
  not merely requested by issue.

### Scope / non-goals / risks

Children: C1, C2, C3. Decisions: ADRs 0001/0002/0008/0011/0012.
No model-service calls, notification delivery, repository mutation, or policy
verdict inferred from topology. Use fake ports and in-memory checkpoints.
State projection and result folding prevent treating a wrapper replacement as a
mechanical node substitution. External repository changes can gate completion.

## C1 — Decide an observable contract for campaign's wrapped child calls

Labels: `type:task`, `area:docs`, `area:langgraph-python`. Parent: C.

### Change / done when

- [ ] Use one actual campaign wrapper and a minimum parent/child graph to compare
  framework-visible composition against an explicit construction-time export
  relationship. Preserve input projection, context, result folding and error paths.
- [ ] Prove which candidate preserves child pause/resume and state ownership with
  a fake runtime. A source-only assertion is insufficient to choose the approach.
- [ ] Select one approach and state evidence ownership, call-site IDs, multiple
  uses of one child, depth behavior and unknown fallback. If neither works, record
  the blocker; do not weaken the Epic's outcome to mark this decision successful.
- [ ] Confirm compatibility with ADR 0012 or accept a narrowly superseding ADR
  before introducing wrapper relationship metadata or a new producer API.
- [ ] Record exact package/repository changes needed. Inspect external trackers
  and file the smallest campaign-owned implementation request if required; link
  its dependency from C2. Do the same for core/git only if evidence requires it.

No closure crawling, graph execution during extraction, hand-maintained shadow
topology, or selected implementation committed to an external repository here.
Deliverable: decision, minimum executable proof, and a bounded implementation scope.

## C2 — Expose campaign parent-child topology without changing workflow behavior

Label: `type:feature`. Parent: C. Blocked by: C1 and any resulting external change.

### User-visible capability / acceptance

- [ ] `channel_concept` exposes prepare_brief/copy_brief_prepare,
  draft_copy/copy_draft, review_copy/copy_review relationships.
- [ ] `channel_production` exposes revise_copy/copy_revision,
  review_copy/copy_review, prepare_copy_feedback/copy_feedback_prepare relationships.
- [ ] The accepted C1 contract, not name inference, supplies each relationship.
  Parent nodes remain addressable; distinct call sites remain distinct.
- [ ] Depth 0/1/2 and unknown wrappers obey the accepted compatibility decision;
  each materialized child retains its own routes, joins and interrupt declarations.
- [ ] Real factory inputs, output folding, errors and pause/resume retain behavior
  under fake ports. Extraction itself does not invoke user nodes.
- [ ] Re-run the 11-factory inventory against new immutable consumer commits and
  validate resulting documents; report actual hierarchy links, not just graph count.
- [ ] Version/publication and migration implications are fed into #170 before RC.

Run determine-feature immediately before implementation. Create implementation
Tasks then, only if topology adaptation and consumer evidence are independent PR
boundaries. An external implementation issue is not a substitute for this
integrated acceptance check.

## C3 — Prove topology correlation across real consumer child calls and resume

Label: `type:feature`. Parent: C. Depends on C1 and C2 for nested acceptance.

### User-visible capability / acceptance

- [ ] Capture a minimum path through git-agent's actual human_approval node and a
  campaign actual gate with fake input/ports, then resume. Do not substitute a
  generic synthetic interrupt for these consumer wiring proofs.
- [ ] Capture one of C2's actual campaign child calls and correlate parent and
  child events using the accepted mapping; display names are not identity.
- [ ] Keep a static call site, logical run, node occurrence, resume invocation and
  retry attempt distinct. A separate smallest repeat-attempt case may measure
  retry mechanics; do not grow the full campaign input to test those mechanics.
- [ ] Missing/unknown/ambiguous graph or node evidence stays unresolved and is
  replay-tested; no guessed matches or approval/effect-success conclusions.
- [ ] Store sanitized captures, expected matches, immutable consumer/core commits,
  capture commands and an offline replay without private checkout/network access.
- [ ] Identify the normalization adapter owner. Request external event changes
  through its owner if the real consumer evidence lacks required identity; never
  silently fabricate the missing fields in the capture.

Flat git capture can proceed independently. Run determine-feature before starting
this Feature and split only proven independent capture/adapter boundaries.

## Amend existing release records instead of creating duplicate release work

Apply these updates together when adopting the plan:

| Record | Proposed edit |
| --- | --- |
| Milestone 9 | Add J and C integrated outcomes; require publication of each actually changed package, including both producers; preserve exact framework baselines and future-version exclusion |
| #166 | Retitle to “Prepare and publish beta.5 producer fixes and consumer support”; remove the stale 1.2/1.3/1.4 promise and Python-only non-goal; retain artifact/publication/closeout evidence separation |
| #170 | Retitle to “Prepare the beta.5 candidate”; block on J, D, C; select final changed package versions after C1/C2; add migration and support matrix, pin tested consumer commits; keep unchanged spec versions only with evidence |
| #171 | Retitle to “Qualify the beta.5 changed-package artifacts”; remove mandatory 1.3/1.4 cutoff; qualify supported manifest versions, Python wheel/sdist and changed npm tarballs; clean-install with unchanged public peers; exercise collision fixes and approved consumer extraction |
| #172 | Retitle to “Publish and verify the beta.5 changed packages”; publish exact qualified artifacts independently, verify registry smoke/provenance for each, then immutable tag/release and coordinated closeout; retain partial-publication recovery |
| #165 | Leave closed; its interpretation/compatibility-policy outcome remains delivered. Link the new work from #166 instead of retroactively changing #165's acceptance |
| #177 / #167–#169 | No change; future framework qualification does not block beta.5 |

Proposed native dependency order:

```text
J ────────────────────────┐
D ────────────────────────┤
C1 → C2 → C3 → C acceptance├→ #170 → #171 → #172 → #166/milestone review
       external changes ──┘
```

The external-change arrow feeds C2/C3 acceptance, not a direct shortcut to release.
The Epic closes after integrated evidence review, not merely after child closure.

## Filing procedure and current evidence

Live topology open issues, #166's native children, milestone 9 and both consumer
open-issue lists were checked on 2026-09-17. Both consumer open lists were empty;
recheck before filing external requests because C1 may take time.

1. Preserve a committed immutable review/probe reference (check whether already
   committed). Put enough reproduction detail in J for it to stand on its own.
2. Create C, then C1/C2/C3; attach exactly one native parent to each child.
3. Create J and D; attach D to #166 and optionally group J there.
4. Replace temporary keys with issue numbers; add native dependencies and adopt
   the milestone/#166/#170/#171/#172 edits atomically as a planning operation.
5. Start J, D and C1 independently. Start flat git capture when useful. Create
   further Tasks at Feature readiness, and external requests only once their
   concrete scope is established.

This document is a proposed plan. It is not permission to publish packages or
modify campaign-agent/git-agent code in this workspace.
