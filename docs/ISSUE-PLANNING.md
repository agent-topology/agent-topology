# Issue planning

GitHub issues are delivery records, not architecture or roadmap records. ADRs
hold decisions, the roadmap holds intended outcomes, and issues break selected
outcomes into reviewable work.

## The model

```text
Milestone: one verifiable release outcome
└── Epic: a coordinated capability or outcome
    └── Feature: independently useful behaviour
        └── Task: one bounded implementation or verification unit
```

Use GitHub's native
[parent/sub-issue relationship](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues)
for the hierarchy. A level may be skipped when it adds no information: a small
Epic can contain Tasks directly. Do not create empty wrapper issues just to
preserve four levels.

### Milestone

A milestone answers “what must be true for this release outcome?” It is not a
bucket for everything worked on during a date range. Give it exit conditions,
and assign an issue only when closing that issue advances those conditions.

The first useful milestone should be `Foundation — usable Python producer`, with
exit conditions such as installable PyPI distributions, a conforming LangGraph
producer, meaningful completeness, deterministic output/hash behaviour, and a
documented `agt describe` path. This is pre-`0.1` foundation work: the README's
`0.1` outcome still requires evidence from two real producers. Do not put the
deferred TypeScript producer in the foundation milestone merely because the npm
namespace exists.

### Epic

An Epic coordinates several independently closable changes toward one
capability. Its body contains the outcome, scope, non-goals, success evidence,
relevant ADRs, risks, and its Feature/Task sub-issues. An Epic should not be the
unit a pull request closes.

Good initial Epics for the foundation milestone are:

- Spec and conformance foundation
- Python LangGraph producer
- CLI and document workflow
- PyPI packaging and release readiness

### Feature

A Feature is independently observable behaviour that a user or downstream tool
can rely on. It states acceptance criteria without prescribing every code step.
Examples include canonical document generation, element-local gap reporting,
or `agt describe` producing a file with strict-mode behaviour.

### Task

A Task is a bounded implementation, test, documentation, or release unit. It
should normally fit one pull request, name its verification, and close without
requiring sibling Tasks to be closed at the same moment. Split a Task when its
parts can fail or be reviewed independently.

## Classification

As of 2026-09-10 this repository is owned by a personal GitHub account, while
[native custom Issue Types are organization-managed](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/managing-issue-types-in-an-organization).
Use mutually exclusive type labels here:

- `type:epic`
- `type:feature`
- `type:task`
- `type:bug`

Use a separate, composable area axis:

- `area:spec`
- `area:conformance`
- `area:langgraph-python`
- `area:cli`
- `area:release`
- `area:docs`

Do not encode workflow status as labels; open/closed state and, if later needed,
a GitHub Project status field own that concern. Do not duplicate the
[milestone](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/about-milestones)
name in a label.

## Issue rules

- Every Feature and Task has exactly one parent issue.
- Every issue assigned to a milestone contributes to that milestone's exit
  conditions. Exploratory ideas stay unmilestoned.
- Dependencies use GitHub's blocked-by/blocking relationship rather than parent
  links; hierarchy and dependency answer different questions.
- PRs normally close Tasks or Bugs, not Epics.
- A scope or architecture dispute links to an ADR; it is not settled only in an
  issue comment.
- Closing all children is evidence for reviewing the parent, not automatic proof
  that the parent outcome was achieved.

## Suggested issue bodies

Epic:

```markdown
## Outcome
## Scope
## Non-goals
## Success evidence
## Decisions
## Risks
```

Feature:

```markdown
## User-visible capability
## Acceptance criteria
## Non-goals
## Decisions
## Verification
```

Task:

```markdown
## Change
## Done when
## Verification
## Parent
```

Create the milestone and Epics first. Create Features only for independently
valuable slices, then add Tasks just before implementation so early guesses do
not harden into a stale backlog.

## First-cut hierarchy

Create the following as the initial shape, then refine Features into Tasks only
after the package build tools and CLI ownership decision are known.

```text
Milestone: Foundation — usable Python producer
├── Epic: Spec and conformance foundation
│   ├── Feature: Versioned topology document schema
│   ├── Feature: Producer limitations and element-local gaps
│   ├── Feature: Canonical output and versioned structure hash
│   └── Feature: Language-neutral conformance fixtures
├── Epic: Python LangGraph producer
│   ├── Feature: Public describe API for compiled graphs
│   ├── Feature: Declared branches and multi-source joins
│   ├── Feature: Strict completeness behaviour
│   └── Feature: Refuse untested LangGraph versions
├── Epic: CLI and document workflow
│   ├── Task: Decide CLI ownership and extension model through an ADR
│   └── Feature: agt describe writes a topology document
└── Epic: PyPI packaging and release readiness
    ├── Feature: agent-topology-spec publishes agent_topology.spec
    ├── Feature: agent-topology-langgraph publishes agent_topology.langgraph
    └── Feature: Independent package build, test, and release checks
```

`agt diff` remains outside this first milestone until its ownership is decided.
It is a document consumer, not required to prove that the first producer can
derive a conforming document.
