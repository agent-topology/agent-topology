# Pre-beta source and consumer review — 2026-09-17

## Decision

Do not freeze the next candidate before resolving the join-identity defect and
reconciling the release acceptance criteria below. Current source represents the
declared outer structure of all 11 inspected consumer graphs. It does **not**
represent campaign-agent's complete parent/child hierarchy as currently wired.
git-agent's one implemented graph is structurally extractable; approval semantics
and trace occurrence correlation are separate, unverified integration claims.

This review prepares work; it does not implement product fixes, change accepted
contracts, file issues, or publish packages. “AI slop” is evaluated as unsupported
claims, stale evidence, contradictory instructions, and unnecessary abstraction;
no inference about who or what authored the code is made.

## Baselines and method

- agent-topology: `344954ee2df167e84df8cf072f7d8c067707da88`; release state records
  coordinated beta.4 and no active candidate.
- [campaign-agent snapshot](../campaign-agent/probe-2026-09-17.json): remote main
  `62089cc4a0adcd3703b22583246bf05ff69efc37`; no release or tag.
- [git-agent snapshot](../git-agent/probe-2026-09-17.json): remote main
  `b67cb35a6195609a5d89976768fb5a4884f17ca1`; no release or tag.
- Remote heads, GitHub release lists, and remote tags were checked on the review
  date. Both consumer environments ran LangGraph 1.2.11. Git-agent had a modified
  README at final inspection; inspected implementation files were unchanged.
- [probe.py](probe.py) compiles each real factory with construction-only policies,
  extracts at depth 0/1/2 with strict mode, checks schema/reference validation,
  node retention and exact declared edge multisets, and compares join counts.
  `invoke`/`ainvoke` are patched to fail. No workflow, model, approval, notification,
  Git operation inside a workflow, or external effect is executed.

## Consumer result

Counts include framework START/END sentinels. Every row passes declaration and
document checks at all three depths, yields one graph, has zero joins, zero gaps,
and no static interrupt nodes. This is one construction-policy sample per factory,
not proof of every configuration or runtime behavior.

| Consumer graph | Nodes | Edges | Hierarchy result |
| --- | ---: | ---: | --- |
| campaign_contract | 15 | 27 | Flat declared structure extracted |
| channel_concept | 29 | 69 | Three wrapped child calls remain unmaterialized |
| channel_production | 37 | 96 | Three wrapped child calls remain unmaterialized |
| copy_brief_prepare | 11 | 21 | Flat declared structure extracted |
| copy_draft | 11 | 21 | Flat declared structure extracted |
| copy_feedback_prepare | 11 | 21 | Flat declared structure extracted |
| copy_review | 11 | 21 | Flat declared structure extracted |
| copy_revision | 11 | 21 | Flat declared structure extracted |
| deliverable_report | 9 | 12 | Flat declared structure extracted |
| stakeholder_review | 17 | 35 | Flat declared structure extracted |
| issue_resolution (git-agent) | 21 | 44 | Flat declared structure extracted |

Detailed source evidence: [campaign review](../campaign-agent/review-2026-09-17.md)
and [git review](../git-agent/review-2026-09-17.md).

## Findings, ordered for release planning

### R1 — P1: producers emit invalid duplicate join identities

Input: three user nodes `a`, `b`, `sink`, with both `add_edge([a,b], sink)` and
`add_edge([b,a], sink)`. Compilation and drawable inspection succeed. Python
1.2.11 and JavaScript 1.4.14 producers both return two `join:a+b:sink` records,
even with strict mode. Each specification validator correctly rejects the result.
This is an element-address collision, not a SHA-256 collision or validator defect.

Cause: [Python join construction](https://github.com/agent-topology/agent-topology/blob/344954ee2df167e84df8cf072f7d8c067707da88/packages/python/langgraph/src/agent_topology/langgraph/_describe.py#L113-L125)
and [TypeScript join construction](https://github.com/agent-topology/agent-topology/blob/344954ee2df167e84df8cf072f7d8c067707da88/packages/typescript/langgraph/src/internal.ts#L168-L188)
sort sources but neither normalize repeated joins nor preserve unique occurrence
identities. `finalize_document` canonicalizes/hashes; it does not validate output.
Strict mode checks completeness gaps, not general conformance.

A second minimum case uses distinct source sets `[a+b,c]` and `[a,b+c]` with one
target. JavaScript emits duplicate `join:a+b+c:sink` ids. Python fails earlier in
LangGraph's drawable barrier channel (`InvalidUpdateError`); do not misattribute
that Python failure to topology's validator. Reproducers:
[Python](join_collision.py), [JavaScript](join_collision.mjs).

Impact: none of the 11 sampled consumers declares joins, so this is a general
producer release defect, not the cause of campaign's missing children.

Required work: define duplicate-declaration semantics, make generated join ids
unambiguous, and add cross-language fixtures for reversed sources, distinct
delimiter-bearing sets, and reversed declaration order. Preserve existing normal
case ids where possible. Verify produced documents with the independent validator
in conformance. Decide migration/hash consequences explicitly under ADRs 0003/0009
rather than silently changing valid historical outputs. A fix to both producers
needs an explicit version/publication choice; it does not fit an unchanged-npm
assumption without recording a deferred npm correction.

### R2 — P1 for full campaign support: real children are hidden by wrappers

`channel_concept` and `channel_production` now compile real child graphs but bind
lambdas to their parent nodes. Those lambdas call `child.invoke` after constructing
different child inputs/context and fold the result back into parent state. The
producer requires a directly mapped `CompiledStateGraph`; increasing depth cannot
recover these six links. The probe confirms one graph at depth 2 and
`subgraph.status=unknown`, reason `identity-unavailable`, on the call sites.

This behavior follows ADR 0012, not a regression in direct-child traversal.
`complete`/strict success is compatible with these unknown interpretation facts.
The seven campaign dynamic interrupt sites and git's human approval are likewise
absent from static interrupt metadata by design.

Required work: start with one real wrapper's input/result mapping and a minimal
parent/child integration. Prefer framework-visible composition if it preserves
state projection and resume behavior. If it cannot preserve behavior, propose an
explicit construction-time relationship/export contract with provenance and an
ADR; do not infer children from closure inspection, names, or source scanning.
Independent child exports can already inventory each graph but do not prove the
parent-child relation. Campaign owns its factory change, requested through its
issue tracker; topology owns any producer/contract change. Full hierarchy support
must remain unclaimed until that integration passes.

### R3 — P2: release issues disagree about beta.5 scope

As read on 2026-09-17, closed [#165](https://github.com/agent-topology/agent-topology/issues/165)
excludes future 1.3/1.4 qualification from beta.5 and places it under
[#177](https://github.com/agent-topology/agent-topology/issues/177).
Open [#166](https://github.com/agent-topology/agent-topology/issues/166) still says
the release exposes a 1.2/1.3/1.4 set, while
[#171](https://github.com/agent-topology/agent-topology/issues/171) requires the
1.3/1.4 cutoff and newly qualified versions. This can recreate the blocker that
#165 explicitly removed. [#170](https://github.com/agent-topology/agent-topology/issues/170)
also needs its release wording aligned with the final scope.

Required work: reconcile existing parent/child acceptance text before candidate
preparation. Keep future upstream tracking separate; do not widen the runtime
manifest to satisfy stale prose. Include R1's package-scope decision in that review.
These are live issue observations; issue bodies can change after this snapshot.

### R4 — P2: evidence and explanatory prose overstate what is established

- The 2026-09-15 consumer reports remain useful history, but campaign's parent
  composition is no longer merely a draft demand. Treating #154's generic recipe
  and synthetic addressing tests as full current-consumer support would overclaim
  their evidence. The dated reports here supersede that use, not the old snapshot.
- [ADR 0012](../../../decisions/0012-nested-graph-identity-traversal-and-compatibility.md)
  says structurally identical materialized graphs “hash identically per graph.”
  The shipped contract exposes a document hash, including graph IDs; there is no
  public per-graph identity-independent hash. Clarify that paragraph explicitly,
  preserving the call-site identity decision rather than inventing a new API.
- README promises that the producer “should be small” and implies configuration
  indicates a format problem, while documented `graph_id`, `depth`, and `strict`
  are legitimate controls. Replace that slogan with the actual responsibility
  boundary. This is editorial debt, not evidence for rewriting working code.

The layered spec/producer boundary, separate uncertainty checks, and experimental
extension are backed by accepted decisions and passing fixtures. This review found
no reason to replace them with a generic plugin registry, universal CLI loader,
closure crawler, or new graph framework. Keep fixes local to proven failures.

## Proposed execution sequence and acceptance

| Order | Work unit / owner | Minimum completion evidence | Dependency |
| --- | --- | --- | --- |
| 1 | Join identity repair / topology Python + TS | Both minimum probes produce valid unique identities, or explicitly reject upstream-unobservable input; declaration-order parity; normal fixtures unchanged or migration documented | None |
| 2 | Release scope reconciliation / topology maintainers | #166/#170/#171 agree with #165 and explicitly decide versions affected by order 1 | Order 1 scope decision, before RC freeze |
| 3 | Consumer hierarchy design / campaign + topology | One real wrapper preserves input/output and resume semantics while exposing an evidenced relation; unknown stays unknown otherwise | Independent of join repair |
| 4 | Correlation integration / consumer host | One child call and one pause/resume; topology graph/node address, run/attempt identity and repeated occurrence remain distinct | Order 3 for nested case |
| 5 | Documentation cleanup / topology | Dated support matrix and explicit boundaries; hash paragraph and release claims reconciled | Findings above |
| 6 | RC qualification / existing #170 → #171 → #172 | Frozen commit, changed-package artifact installs, matrix and exact receipts | Orders 1/2/5; order 3/4 if full consumer support is promised |

Do not make full campaign hierarchy a hidden acceptance criterion for a deliberately
limited beta. State its exclusion explicitly if deferred. Conversely, a beta
advertised as supporting these complete workflows must include orders 3/4.
No time estimates are inferred from code size; the unresolved wrapper contract is
the main design dependency.

## Verification and limits

- Python producer: 200 passed.
- Python spec + release tools + public docs: 178 passed.
- TypeScript spec check (build, formatting, types, tests): 43 passed.
- TypeScript producer check: 158 passed.
- Actual consumer extraction: 33 cases (11 factories × 3 depths), independent
  validation and declaration checks pass. Existing green suites do not cover R1.
- GitHub CI for reviewed HEAD recorded successful Python packages, TypeScript
  packages, and LangGraph compatibility workflows.
- No fresh release artifact qualification, registry installation, production
  policy coverage, runtime event capture, exhaustive security audit, or proof of
  all possible identifier/hash behavior is claimed. Consumer probes use source
  packages and existing local environments; initial direct runs lacked jsonschema,
  resolved through an ephemeral uv overlay without modifying consumer projects.
- An initial combined pytest console-script invocation could not import `scripts`;
  the documented `python -m pytest` invocation passed all 178 relevant tests.

## Reproduction

From the topology repository, after building local TS packages:

```sh
rtk uv run --project packages/python/langgraph --group test python -B docs/research/internal-consumer/pre-beta-review-2026-09-17/join_collision.py
rtk proxy node docs/research/internal-consumer/pre-beta-review-2026-09-17/join_collision.mjs
rtk uv run --no-project --python "$CAMPAIGN_CHECKOUT/.venv/bin/python" --with jsonschema==4.26.0 python -B docs/research/internal-consumer/pre-beta-review-2026-09-17/probe.py campaign-agent "$CAMPAIGN_CHECKOUT"
rtk uv run --no-project --python "$GIT_AGENT_CHECKOUT/.venv/bin/python" --with jsonschema==4.26.0 python -B docs/research/internal-consumer/pre-beta-review-2026-09-17/probe.py git-agent "$GIT_AGENT_CHECKOUT"
```

Set the two checkout variables to locally available checkouts of the pinned
canonical repositories. The scripts do not fetch or modify them. Collision probes
print observations (including validation failures), not a passing product test.
