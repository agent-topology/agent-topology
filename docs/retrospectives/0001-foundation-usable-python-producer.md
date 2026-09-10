# Foundation — usable Python producer retrospective

- Milestone: [Foundation — usable Python producer](https://github.com/milocosmopolitan/agent-topology/milestone/1)
- Retrospective: [#33](https://github.com/milocosmopolitan/agent-topology/issues/33)
- Date: 2026-09-10

## Outcome

Foundation delivered a runnable Python-first topology stack: a canonical v0.1
document contract, a conforming LangGraph producer, the `agt describe` path, and
two independently buildable distribution artifacts with guarded release
automation. The implementation proves that a compiled LangGraph graph can be
turned into a deterministic document while preserving known uncertainty.

It did **not** publish either distribution. At retrospective opening there were
no release-workflow runs, GitHub releases, or PyPI projects for
`agent-topology-spec` or `agent-topology-langgraph`. “Installable” therefore
means the wheel and source distributions were built, inspected, and installed
in clean environments; it must not be read as evidence of registry publication.

## Planned versus delivered

| Planned exit condition | Delivered evidence | Assessment |
| --- | --- | --- |
| Versioned language-neutral contract | [Schema and validator](../../spec/agent-topology.schema.json), public `agent_topology.spec` utilities, valid and invalid schema cases | Demonstrated by runnable tests |
| Deterministic output and versioned structure hash | Canonicalisation tests cover reordered declarations, metadata exclusion, and join-versus-edge inequality | Demonstrated by runnable tests |
| Honest completeness | Producer limitations and element-local gaps are separate; strict mode raises only for graph gaps and retains the document | Demonstrated by API and conformance tests |
| Shared conformance | Eight minimum fixture recipes cover linear flow, routing, loops, fan-out, nesting, interrupts, unknown targets, and joins | Demonstrated against LangGraph 1.2.10 and 1.2.11 in CI |
| Usable Python producer | `agent_topology.langgraph.describe` accepts compiled graphs, supports depth and strictness, and rejects untested LangGraph versions | Demonstrated by 43 producer tests and the compatibility matrix |
| Document CLI | `agt describe path.py:object --out topology.json` has documented exit statuses 0 and 2–8 | Demonstrated by CLI tests; importing the target executes module-level construction but never runs the graph |
| Independent Python distributions | Separate Hatchling projects produce native namespace portions, inspectable wheels/sdists, and clean joint installations | Demonstrated for local and CI artifacts, not PyPI publication |
| Repeatable release path | Package selection, version substitution, artifact receipts, clean-tree checks, and Trusted Publishing gates exist | Dry runs found a missing transitive dependency in the coexistence environment; #33 corrects it and requires a remote rerun before closure |

The milestone also delivered useful detail that its original description did
not name: a compatibility manifest that drives the supported-version matrix, a
stable CLI failure taxonomy, packaged-schema validation, and a release receipt
that binds package, version, commit, filenames, digests, and completed checks.

## Work sequence and decomposition

The CLI ownership decision in [#13](https://github.com/milocosmopolitan/agent-topology/issues/13)
correctly preceded CLI implementation. The shared Python scaffold in
[#20](https://github.com/milocosmopolitan/agent-topology/issues/20) was the main
execution unlock: every later Python package, quality, and release change used
that foundation. `determine-feature` also made the right minimum split for
Feature #17: toolchain ownership and release automation could be reviewed and
corrected independently as Tasks #20 and #21.

The strongest product learning came from shared conformance in
[#8](https://github.com/milocosmopolitan/agent-topology/issues/8), because it
turned the schema and extraction claims into common executable examples.
However, it merged after producer Features #9–#11. Future work should establish
the minimum shared example before producer behavior that claims to conform to
it, while keeping the input graph no larger than the contract behavior being
measured.

Two ordering mistakes are visible in the delivery record:

- Feature #5 implemented the schema semantics attributed to sibling Feature #6,
  which was then closed manually from the same commit. The original Features
  were not independent review boundaries.
- The LangGraph distribution Feature #16 merged before the specification
  distribution Feature #15 even though the former depends on the latter's
  compatible packaged contract. Parallel work was reasonable; merge readiness
  should have been represented as an explicit dependency.

## Delivery workflow

### Keep

- ADR-first decisions before public ownership or contract changes.
- Graft-first context and blast-radius discovery.
- `determine-feature` as a just-in-time gate that creates only necessary Tasks.
- `resolve-issue` acceptance mapping and one workbench per executable leaf.
- `ghpr` human authorization, checklist reconciliation, and generated PR links.
- Shared fixtures, manifest-driven compatibility, clean installation, artifact
  inspection, and release receipts as executable evidence.

The trace database contains 13 completed `ghpr` runs for the implemented leaf
issues. Every recorded run passed its human gate, rewrote its `wip:` commit,
pushed its workbench, created a closing PR, and reconciled the issue checklist.
CI also caught two real release-workflow defects on PR #30: the release-tool
tests could not import `scripts`, and artifact inspection rejected an unlisted
`_cli.py`. Both were corrected before merge. The retrospective dry runs found a
third: the release workflow installed both local wheels with `--no-deps`, so the
joint import failed because `jsonschema` was absent even though standalone clean
installs and every preceding job passed. Issue #33 removes that flag and verifies
the corrected installation locally; its remote rerun remains a close condition.

### Change

- State the proof required by each milestone exit condition: local test, shared
  fixture, clean installation, remote workflow, registry publication, or real
  consumer evidence are not interchangeable.
- Review a parent Feature or Epic against its integrated criteria after children
  close; closed counts are an input, not the verdict.
- Express real cross-Feature merge dependencies, especially package and release
  boundaries, instead of relying on issue number or sibling order.
- Preserve a review record tied to the commit SHA, acceptance checklist, CI
  state, and documentation/ADR assessment.
- Use the repository's authoritative Python commands in `resolve-issue` and
  `review-pr`; derive them from `CONVENTIONS.md` rather than a generic template.

### Stop

- Treating a closed issue or green PR as proof of the user-visible outcome.
- Letting one Feature absorb a sibling's acceptance criteria without first
  correcting the work boundary.
- Applying npm, Cargo, detector/redaction, browser, Node.js, or unrelated wiki
  gates to this Python repository.
- Treating an absence of review findings as evidence that review occurred. All
  15 Foundation PRs have no persisted GitHub review or comment, so retrospective
  evidence can establish their code and CI results but can only infer the final
  review step.

## Risks and debt

- Vendor neutrality remains provisional because only LangGraph has emitted the
  contract. This is an accepted v0 limit, not evidence for a v1 claim.
- The supported LangGraph range is intentionally narrow at 1.2.10–1.2.11 and
  requires new conformance evidence before expansion.
- ADR 0001 still accepts incomplete Send fan-out semantics, no all/any join
  distinction, and framework sentinel nodes. These become blocking only for a
  consumer that needs the missing distinction.
- No consumer has yet correlated a topology document with runtime evidence, so
  the project's first intended use remains an architectural hypothesis.
- The first non-publishing release runs failed at namespace coexistence because
  transitive spec dependencies were omitted. The workflow correction requires a
  successful remote rerun after the branch is available; actual PyPI publication
  remains a separate authority-sensitive operation.

These risks remain recorded rather than inflated into speculative Tasks. All
accepted retrospective corrections fit in #33, so this retrospective creates no
follow-up issue.

## Next milestone recommendation

The next milestone should demonstrate uncertainty-preserving correlation between
a Foundation topology document and runtime evidence from real LangGraph runs.
Candidate Epics are:

1. Define minimum language-neutral trace-evidence fixtures and identity rules.
2. Build a Python document consumer that correlates observed nodes and edges
   without converting gaps or producer limitations into false certainty.
3. Evaluate the correlation on real workflows and document which existing core
   fields are sufficient or blocking.

This recommendation does not create or start the milestone. Its explicit
non-goals are a second producer, a v1 or vendor-neutrality claim, TypeScript,
rendering, policy verdicts, path coverage, `agt diff`, runtime collection,
hosting, and unrelated publication work.

## Verification evidence

- [Spec non-publishing release run](https://github.com/milocosmopolitan/agent-topology/actions/runs/34537138466)
  passed tests, quality, builds, inspection, and standalone installation, then
  failed at namespace coexistence because dependencies were intentionally omitted.
- [LangGraph non-publishing release run](https://github.com/milocosmopolitan/agent-topology/actions/runs/34537140247)
  passed those stages plus both LangGraph conformance boundaries, then reproduced
  the same namespace-coexistence failure.
- Main-branch package and compatibility workflows passed at commit
  `0ef7fefdd9af66557cd4af93aa530c329a447eb3` before the retrospective.
- Local retrospective verification reruns the package, schema, release-tool,
  conformance, formatting, lint, build, and artifact-inspection commands listed
  in [CONVENTIONS.md](../../CONVENTIONS.md).

## Documentation and decision check

The accepted ADRs still match the delivered architecture: the core remains
descriptive, uncertainty is explicit, hashes are versioned, rendering is
outside conformance, neutrality is provisional, packages are independent, and
the LangGraph distribution alone owns the Foundation CLI. No new or superseding
ADR is required. `CONVENTIONS.md` and the ADR router remain authoritative;
README, ARCHITECTURE, issue-planning guidance, and repository-local workflow
skills are corrected alongside this record where their status or commands had
drifted.
