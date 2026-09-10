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

Check each explicitly against `AGENTS.md` and report per item:

- **Security boundary** — no real credentials in source, fixtures, logs, errors,
  snapshots, docs, or agent context; no plaintext secret values in findings or
  diagnostics; the core still side-effect free (no network, telemetry, secret
  storage, or environment-dependent behavior).
- **Architecture** — detection still separate from policy enforcement; the
  public API still runtime-neutral; browser and Node.js compatibility intact.
- **Tests** — deterministic tests added for detector, redaction,
  overlap-resolution, or policy behavior changes. New false-positive /
  false-negative tradeoffs stated.
- **Governance** — ADRs under `docs/decisions` with `scope: workspace` (never
  `_notes/decisions`); `_notes/GOVERNANCE.md` policy when that file exists.

Run the gate yourself rather than trusting the PR's green tick:

```bash
rtk npm run ci
rtk cargo test && rtk cargo clippy   # when crates/ is touched
```

## 4. Wrap-up before close

The work that is easy to forget and expensive to add after the merge:

- `CHANGELOG.md` entry for anything user-visible.
- An ADR when the PR settled a decision, plus `rtk npm run decisions:validate`.
- Docs touched by the change — `README.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`,
  and the sibling `secret-scan.wiki` checkout when it is affected.
- The PR body closes its issue (`Closes #<ISSUE_NUMBER>`).
- The commit message `ghpr` generated actually describes the change.

Apply the fixes and the wrap-up locally, on the PR's branch, with ordinary
descriptive commit messages — the `wip: #<N>` rule belongs to `resolve-issue`
and is over once the PR exists.

## 5. Report, then stop

Give a verdict — ship / fix first / needs a decision — with findings ordered by
severity, each anchored to `file:line`, and the wrap-up items you completed.

Do **not** push, merge, or close without the user explicitly approving it.
Releases in particular require approval after tests pass and the public API and
changelog have been reviewed; see the release authority section of `AGENTS.md`.
