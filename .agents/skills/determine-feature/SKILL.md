---
name: determine-feature
description: Assess one GitHub Feature before implementation, using its dependencies and repository evidence to decide whether it is a ready single-PR leaf. When it is too broad, create the minimum Task sub-issues and parent/dependency relationships, then report a dependency- and learning-aware work sequence. Use for "determine-feature 5" or before resolve-issue on a Feature. Does not implement code, create branches, or open pull requests.
---

# determine-feature

Turn one Feature into an honest executable boundary immediately before work
starts. The result is either a ready leaf Feature or the smallest useful set of
ready Task leaves. Then show what should run first and what becomes available
afterward.

This skill may create and relate GitHub Task issues under the target Feature.
It never implements the Feature, changes code, creates a branch, pushes, opens a
pull request, or closes an issue.

An explicit `determine-feature <NUMBER>` request authorises creation of the
minimum Task issues and relationships under that Feature. A request only to
inspect, explain, or propose a decomposition is read-only: return the proposed
graph without creating it. Neither form authorises edits to unrelated issues.

## Input

`determine-feature <FEATURE_NUMBER>` — `$1` is one open GitHub issue in the
current repository.

Resolve the repository rather than asking for it:

```bash
rtk gh repo view --json nameWithOwner -q .nameWithOwner
```

## 1. Read the operating contract

Read `README.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, and
`docs/decisions/DECISIONS.md`. Follow the router to every ADR named by the
Feature.

Read the target without a summarising filter so no acceptance criterion is
dropped:

```bash
gh issue view <FEATURE_NUMBER> \
  --json number,title,body,state,labels,parent,subIssues,blockedBy,blocking,milestone,comments,url
```

Require all of the following:

- the issue is open;
- it has exactly the `type:feature` work-type label;
- it has one parent Epic;
- its milestone, acceptance criteria, non-goals, decisions, and verification
  are identifiable.

If the issue is not a Feature, stop and report the correct workflow. Do not
relabel it by assumption.

If missing acceptance criteria or unresolved product intent permits materially
different decompositions, stop with the exact question that owns the choice.
Do not manufacture Tasks to hide an undefined Feature.

## 2. Build the real work graph

Read the parent Epic, existing sub-issues, every open blocker, and every issue
the Feature blocks. List the other open issues in the same milestone and load
their parent, blocker, and sub-issue fields. Hierarchy is not execution order;
`blockedBy` is the hard ordering relation.

Inspect local state before recommending work:

```bash
rtk git status --short --branch
rtk git worktree list
rtk git branch -a
```

Uncommitted files or an existing workbench that overlaps the Feature are real
work-in-progress evidence. Surface the overlap; never absorb, discard, or
overwrite it.

Get implementation context from graft before reading source:

```bash
[ -f graft/INDEX.md ] || graft build
graft ask "<Feature title plus literal symbols, files, and contract terms>" --source
```

Use `graft callers`, `graft skeleton`, or `graft grep` only when the question
requires that shape. If the relevant file is unindexed, use `rtk read` at the
smallest useful range.

## 3. Apply the dependency gate

If the Feature has an open blocker, it is not ready for implementation. Report
the blocker-first sequence and stop without creating Tasks. Upstream work may
still change the Feature boundary, so decomposing it now would create a stale
backlog.

An exception requires explicit user direction to refine the blocked Feature
now. In that case, copy only the external blockers that genuinely constrain each
new Task; GitHub does not inherit parent dependencies automatically.

## 4. Decide whether the Feature is one leaf

A sub-issue-free Feature is directly executable only when every answer below is
yes:

1. **One outcome** — the work produces one cohesive capability, not a bundle of
   independently valuable results.
2. **One review boundary** — implementation, contract updates, tests, and
   necessary documentation belong in one independently mergeable and reversible
   pull request.
3. **Decision complete** — no unresolved architecture, product, ownership, wire
   shape, compatibility, or release-authority choice remains.
4. **Concrete verification** — the acceptance criteria map to a bounded set of
   observable checks.
5. **Cohesive blast radius** — graft shows one connected change surface rather
   than unrelated packages or independently shippable paths.
6. **No overlapping work** — the working tree, worktrees, branches, and comments
   do not show someone already carrying the same change.

Do not use line count, file count, or an arbitrary duration as the deciding
test. A cross-file contract change can be one leaf; two unrelated one-line
changes are not.

If all answers are yes, create nothing. The Feature itself is the work unit and
the next command is:

```text
resolve-issue <FEATURE_NUMBER>
```

If the Feature already has sub-issues, it is a grouping issue rather than a
direct work unit. Map its acceptance criteria to the existing children first,
retain children that are still accurate, and create only a missing executable
boundary. Do not recreate a Task merely to make its title or body more uniform.

## 5. Create the minimum Tasks when it is not one leaf

Split only at independently reviewable boundaries revealed by the failed leaf
checks. Typical boundaries are:

- a decision or version-pinned research result that must exist first;
- a shared interface or foundation that enables later implementation;
- independently shippable implementation slices;
- migration, release, or operational work requiring separate authority.

Tests and documentation stay with the implementation they verify unless they
are independently valuable artifacts. Never create empty coordination Tasks or
one Task per acceptance-criteria bullet.

Before creating anything, search the Feature's existing children and the
milestone for an issue with the same outcome. Reuse an existing issue only when
its scope and ownership match; otherwise create the cheaper new Task rather than
distorting unrelated work.

Each new Task must:

- use `type:task` plus the relevant `area:*` labels inherited from the Feature;
- inherit the Feature's milestone and have no assignee unless the user requested
  one;
- use the Feature as its native parent;
- contain `Change`, `Done when`, `Verification`, and `Parent` sections;
- name the acceptance criteria it advances;
- be executable through one `resolve-issue` workbench and one pull request.

Create children with GitHub's native relationship:

```bash
rtk gh issue create \
  --title "<bounded Task title>" \
  --label type:task --label "<area label>" \
  --milestone "<Feature milestone>" \
  --parent <FEATURE_NUMBER> \
  --body-file -
```

After every issue number exists, add only necessary dependency edges:

```bash
rtk gh issue edit <TASK_NUMBER> --add-blocked-by <OTHER_TASK_NUMBERS>
```

Keep downstream issues blocked by the parent Feature. Do not repoint them to
individual Tasks: the Feature is the stable capability boundary and becomes
complete only after integrated acceptance verification.

Creation must be idempotent. Before retrying after a partial failure, reread the
children and match exact outcome and title. Report what was created and stop if
the graph cannot be reconciled without deleting, reparenting, or changing an
unrelated issue.

## 6. Verify the resulting graph

Reread the Feature and every child:

```bash
gh issue view <NUMBER> \
  --json number,title,parent,subIssues,blockedBy,blocking,labels,milestone,assignees,url
```

Verify that:

- every child has exactly one parent, the intended milestone, `type:task`, and
  the right area labels;
- Task dependencies are resolvable, acyclic, and point from prerequisite to
  dependent work;
- dependencies outside the Feature remain attached to the Feature unless they
  constrain one Task specifically;
- no duplicate Task was created;
- each terminal leaf is a valid `resolve-issue` unit.

## 7. Report the work sequence

Return two views.

**Target sequence** lists the Feature's Tasks in topological waves. Within the
same wave order work by:

1. decision or evidence that removes uncertainty;
2. shared foundations that unlock the most downstream work;
3. implementation and integration;
4. packaging, release, or other authority-sensitive operations.

**Milestone ready wave** lists every currently executable leaf Task or leaf
Feature in the milestone. Exclude issues with open blockers, parent grouping
issues, overlapping active work, and Features that still need decomposition.

Finish with exactly one recommended next command:

```text
resolve-issue <NEXT_LEAF_NUMBER>
```

Explain why it comes first, which issues it unlocks, and any overlapping local
work that must be reconciled first. Never imply that Epic numbering or sibling
order is a work sequence.

When all Tasks close, the Feature is not automatically done. Its acceptance
criteria require an integrated review before the Feature is closed and its
downstream issues become eligible.
