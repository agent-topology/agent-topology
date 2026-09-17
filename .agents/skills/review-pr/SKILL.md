---
name: review-pr
description: Final review of an open pull request in this repo before it is merged or closed — graft-backed blast-radius check, the repo's security and governance gates, CI status, and the wrap-up work (changelog, ADR, docs, issue linkage). Use when asked to review a PR by number ("review-pr 44", "/review-pr 44", "final review of PR #44"). Proposes and applies fixes locally; never pushes, merges, or closes without explicit approval.
---

# review-pr

The second unit of work on an issue: `ghpr` has turned a `wip:` branch into a
PR, and this is the last pass before it closes. Two jobs — find what the diff
gets wrong, and finish what the diff left undone.

## Input

`review-pr <PR_NUMBER>` — the argument is the PR number (`$1`).

## 1. Load the change

```bash
rtk gh pr view <PR_NUMBER>
gh pr diff <PR_NUMBER>
rtk gh pr checks <PR_NUMBER>
```

Read the diff in full. Note the issue it closes — the PR body should link it —
and read that issue's acceptance criteria:

```bash
gh issue view <ISSUE_NUMBER> --json title,body
```

The criteria are the review's spec. A PR that is clean but incomplete still
fails.

## 2. Blast radius, from graft

A diff shows what changed, never what depended on it. For every symbol the
diff touches:

```bash
[ -f graft/INDEX.md ] || graft build
graft callers <symbol> --depth 2
graft ask "<the subsystem the diff touches>" --source
```

You are looking for call sites the PR did not update, invariants a node states
that the change now violates, and duplicated logic that graft shows already
exists elsewhere. Cite `file:line` for anything you flag.

## 3. Repo gates

Check each explicitly against `AGENTS.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`,
and the routed ADRs, and report per item:

- **Package direction** — the specification does not import a producer or
  framework, producers depend inward on the specification, and independently
  released namespace portions do not collide.
- **Document contract** — framework-only facts remain under `x-*`, limitations
  remain distinct from element-local gaps, and canonicalisation/hash changes use
  the correct format or algorithm-version decision.
- **Tests and conformance** — the smallest useful deterministic fixture or
  focused package test covers the behavior, and supported LangGraph claims have
  boundary evidence.
- **Governance** — material architecture choices have a routed proposed or
  superseding ADR; README and conventions do not silently reverse accepted ADRs.

Run the authoritative commands from `CONVENTIONS.md` rather than trusting the
PR's green tick. For the current Python Foundation:

```bash
rtk uv run --project packages/python/spec --group test pytest packages/python/spec/tests
rtk uv run --project packages/python/spec --group test pytest spec/tests
rtk uv run --project packages/python/spec --group test python -m pytest tests/test_release_tools.py
rtk uv run --project packages/python/langgraph --group test pytest packages/python/langgraph/tests
rtk uvx --from ruff==0.16.7 ruff format --check packages/python scripts tests
rtk uvx --from ruff==0.16.7 ruff check packages/python scripts tests
```

When packaging or release files change, also build and inspect both archive
formats, exercise clean installations and namespace coexistence, and run the
supported LangGraph compatibility matrix.

## 4. Wrap-up before close

The work that is easy to forget and expensive to add after the merge:

- Release notes or a changelog entry when the repository has an established
  destination and the change is user-visible.
- A routed ADR when the PR settles a material architecture decision, with the
  decision router and assembled architecture updated after acceptance.
- Relevant public, architecture, convention, contract, conformance, and
  issue-planning documentation updated with the behavior they own.
- The PR body closes its issue (`Closes #<ISSUE_NUMBER>`).
- The commit message `ghpr` generated actually describes the change.
- **If the issue carries the `area:release` label, check off its `- [ ]`
  acceptance boxes to `- [x]` in the issue body now, via `gh issue edit
  <ISSUE_NUMBER> --body-file <file>`, for every criterion this review just
  confirmed.** `.github/workflows/release-issue-close.yml` runs
  `scripts/check_release_issue.py` on the `issues: closed` webhook and
  reopens the issue immediately (with a `release-issue-close-guard` comment)
  if any box is still unchecked at that instant — it reads the issue body
  from the webhook payload captured at close time, not a later edit, so
  checking boxes *after* the PR merges and the issue auto-closes on `Closes
  #<N>` is too late and guarantees a reopen/re-close race. Do this edit
  before merging so the close-time snapshot already has every box checked.
  Non-release issues have no such guard and do not need this step.
- The final report records the reviewed commit SHA, acceptance-criteria mapping,
  CI state, and documentation/ADR assessment so the review can be audited later.

Apply the fixes and the wrap-up locally, on the PR's branch, with ordinary
descriptive commit messages — the `wip: #<N>` rule belongs to `resolve-issue`
and is over once the PR exists.

## 5. Report, then stop

Give a verdict — ship / fix first / needs a decision — with findings ordered by
severity, each anchored to `file:line`, and the wrap-up items you completed.

Do **not** push, merge, or close without the user explicitly approving it.
Releases in particular require approval after tests pass and the public API and
changelog have been reviewed; see the release authority section of `AGENTS.md`.
