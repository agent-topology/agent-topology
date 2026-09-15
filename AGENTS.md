# Agent instructions

## Required context

1. Read `README.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `docs/decisions/DECISIONS.md` before making material changes.

Project-wide ADRs live under `docs/decisions` with `scope: workspace`; do not

## Internal consumer reference repositories

These repositories are under active development and are reference inputs for
agent-topology consumer research:

- [agent-workflow-core](https://github.com/milocosmopolitan/agent-workflow-core)
- [campaign-agent](https://github.com/milocosmopolitan/campaign-agent)
- [git-agent](https://github.com/milocosmopolitan/git-agent)

Use these GitHub repository URLs as their canonical identities in documentation
and issues, not machine-specific local paths. Available local checkouts may be
read for evidence. Read access and filing relevant GitHub issues are authorized;
do not directly write or modify code in these repositories. Keep implementation
changes in agent-topology; request external changes through the owning
repository's issues when needed.

Record findings in `docs/research/internal-consumer/<repo>/`, with immutable
commit permalinks and a snapshot of the latest release tag and peeled commit, or
remote main when no release exists. Also record the inspected HEAD/main when it
differs from the release. Separate implemented behavior, approved designs, draft
plans, and unverified requirements; development status is not evidence of support.
See the [internal consumer research index](docs/research/internal-consumer/README.md).

## 일 좀 똑바로 하자

- 5분 이상 걸리는 명령을 제안하기 전에, 그 입력을 먼저 읽어서 검증한다. 검증 비용이 실행 비용보다 두 자릿수 작으면 무조건 먼저 검증한다.
- 시험/검증 작업에서는 "무엇을 측정하는가"와 "무엇이 입력으로 필요한가"를 분리한다. 입력은 측정 대상을 만족하는 최소 크기여야 한다.
- 기존 자산(이슈, 브랜치, 파일)에서 고르는 것이 유일한 선택지라고 가정하지 않는다. 새로 만드는 쪽이 더 싸면 그쪽을 먼저 제안한다.
- 반론이 들어오면, 내가 답하기 쉬운 반론이 아니라 실제로 제기된 반론에 답한다.

<!-- graft:start -->
## Graft — repo context graph

This repo is indexed in `graft/`: small linked markdown nodes that explain each
system and carry exact file:line spans, kept in sync with the code through git.

For ANY task here — understanding how something works, finding where code lives,
or scoping a change — get context from the graph before grepping or opening
source files. Re-ask freely (it's cheap) and reuse literal identifiers you
already have (symbol, error string, file name) as the query. New to this repo?
Run `graft map` first — a token-budgeted orientation (dir clusters, hubs,
hotspots), no LLM, no key.

- Run `graft ask "<your question>" --source` → ranked nodes with the relevant
  code spans inlined (each hit's ≤8-line crux by default; `--full` for whole
  definitions when the crux isn't enough). Match the tool to the task shape:
  for understanding or editing, the top node IS the answer — cite its
  `covers:` file:line spans and edit straight from `--source`. For
  exhaustive tasks ("every occurrence / every caller of this pattern"), ranked
  results are top-N, not complete — run `graft grep "<literal>"` instead
  (exhaustive over indexed files, grouped by enclosing symbol), falling back
  to raw `grep -rn` only for unindexed files.
- `graft skeleton <file>` → every definition's signature + span, ~10× cheaper
  than reading the file; use it to skim an API surface.
- `graft callers <symbol>` gives precomputed, exact edges — who calls this.
  Add `--direction out` for what it calls, or `--depth N` to walk
  transitively for the full blast radius. For structural questions, skip
  ranking and use this directly.
- Or browse: `graft/INDEX.md` lists every node; follow the links.
- Monorepos and folders of multiple repos rank fairly across sub-projects —
  hits carry `[scope/]` labels naming which one they're from. Narrow with
  `graft ask "<task>" --in <scope>/` once you know where you're working.

If a returned span is truncated ("+N more lines"), open the file at that exact
range before finalizing. Only open source files when a node genuinely lacks a
needed detail, and then at the exact file:line the node points to — never
re-read whole files.

After big code changes, refresh the graph with `graft build` (deterministic,
no API key, $0).
<!-- graft:end -->

## Tool precedence — graft first, rtk second

They answer different questions; do not let one stand in for the other.

- **Where is the code / who calls it / what does this change break** → graft
  (`graft ask`, `graft grep`, `graft skeleton`, `graft callers`). Query it
  before any `grep`, `rtk grep`, or whole-file read.
- **Compressing the output of a command you are already running** (build, test,
  git, gh, package managers) → prefix it with `rtk`. See `RTK.md`.

`rtk read` / `rtk grep` / `rtk find` are the fallback for files graft has not
indexed, or for opening the exact `file:line` graft already pointed you at.

## Issue workflow — feature gate plus two units of work

Both live in `.agents/skills/` so Claude Code and Codex read the same file.

| step | command                                           | ends at                                                         |
| ---- | ------------------------------------------------- | --------------------------------------------------------------- |
| 0    | `determine-feature <FEATURE_NUMBER>`              | a ready leaf Feature or minimal Task graph + work sequence       |
| 1    | `resolve-issue <ISSUE_NUMBER>`                    | a verified `workbench/<N>-<slug>` branch, committed, not pushed |
| 2    | _(you)_ `ghpr run <N> --trace-db …/giro.trace.db` | commit message written, PR opened                               |
| 3    | `review-pr <PR_NUMBER>`                           | final review + wrap-up done, ready to close                     |

`resolve-issue` owns the `wip: #<N>` commit-subject rule that `ghpr` depends on:
every commit on the branch carries that exact subject, with no body and no
trailers. Once the PR exists that rule is over.

Run `determine-feature` immediately before starting a Feature. It creates no
wrapper Task when the Feature is already one decision-complete PR boundary. If
the Feature is broader, resolve the Task leaves it creates rather than resolving
the parent Feature directly.

## Working from a GitHub issue

An issue URL carries no code vocabulary, so graft's prompt hook has nothing to
match on and injects nothing. Before touching source, read the issue body and
run `graft ask "<the issue title or the symbols it names>" --source` yourself.
A fresh worktree also has no `graft/` (it is gitignored) — run `graft build`
once before starting.

@RTK.md
