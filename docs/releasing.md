# Releasing the 0.1 public preview

The repository publishes four independently versioned packages:

| Registry | Foundation package     | Producer package            |
| -------- | ---------------------- | --------------------------- |
| PyPI     | `agent-topology-spec`  | `agent-topology-langgraph`  |
| npm      | `@agent-topology/spec` | `@agent-topology/langgraph` |

The initial preview is beta.1: Python packages use the PEP 440 version `0.1.0b1`,
while npm packages use the SemVer version `0.1.0-beta.1`. That coordinated beta label
is a release choice, not a promise that later versions or release dates will remain
coordinated. The topology format and structure-hash algorithm have their own version
axes.

## Publication sequence

For beta.2 and later, prepare and qualify from `release/<version>` as described
below. The current candidate is [0.1.0-beta.2](releases/v0.1.0-beta.2.md).

1. Start from the reviewed source commit and confirm both package CI workflows are
   green. Run each release workflow with `publish` disabled before contacting a
   registry.
2. Publish `agent-topology-spec`, then `agent-topology-langgraph`, with
   `.github/workflows/release-python.yml`. The producer must name a compatible
   specification version.
3. Publish `@agent-topology/spec`, then `@agent-topology/langgraph`, with
   `.github/workflows/release-npm.yml`. The producer must name its specification peer
   version.
4. Install every exact version from its public registry in a clean environment and
   repeat the public smoke paths. Record the source commit, filenames, registry URLs,
   provenance, and digests in the GitHub release notes.
5. Create the coordinated `v<version>` Git tag, GitHub release, and announcement
   only after all four artifacts pass. The Python and npm sequences may run
   independently, but the specification package always precedes its producer within
   an ecosystem.

The protected workflows publish one selected package at a time. A successful run for
one package does not authorize another package and does not prove the four-package
preview complete.

The completed initial publication and its public-registry verification are recorded in
the [v0.1.0-beta.1 release notes](releases/v0.1.0-beta.1.md). Use that record as the
GitHub Release body so the coordinated tag, registry artifacts, qualification receipts,
source commits, and user-visible compatibility claims remain together.

## Release branches and immutable tags

`main` is the integration branch. Create `release/<version>` from the reviewed
integration commit when stabilizing a release, for example
`release/0.1.0-beta.2`. Prepare package versions, lockfiles, producer provenance
versions, compatible spec dependencies, release checks, and candidate notes there.
Send release fixes through PRs targeting that branch. Keep unrelated development
out of the candidate and merge release corrections back into main through a PR.

The branch name identifies the release being coordinated; it does not override
the independently selected versions of its packages. Python retains PEP 440
versions (`0.1.0b2`) while the branch and npm use SemVer (`0.1.0-beta.2`). The
document format and hash algorithm versions do not follow either automatically.

Package and framework-compatibility CI runs on pushes to `release/**`. Both manual
release workflows reject main, tags, and other branches. Dispatch inputs must
match the selected package's committed version; npm producer inputs must also
match its committed spec peer. Version selection belongs in reviewed source,
not an ad hoc build-time override. Use the release branch explicitly, for example:

```bash
gh workflow run release-python.yml --ref release/0.1.0-beta.2 -f package=spec -f version=0.1.0b2 -f publish=false
gh workflow run release-npm.yml --ref release/0.1.0-beta.2 -f package=spec -f version=0.1.0-beta.2 -f publish=false
```

Freeze the branch commit while qualifying and publishing the intended package set.
Any source change requires fresh qualification. Record artifact receipts and
registry verification before tagging the exact qualified commit as `v<version>`.
Never move a published version tag. Retain the release branch as the record of
preparation, and merge the release work back into main after publication.

The missing beta.1 tag was restored on 2026-09-11 at
`0e127d84d77904dd0a909fab0ea58862282ceae8`, the merge of the original release
notes in PR #74. The four package source trees match the qualified ancestor
commits listed in the beta.1 notes. This retrospective tag does not claim that
the artifacts were rebuilt from that merge or create a GitHub Release.

## Recovering a partial publication

If the sequence stops after any package is published:

1. Withhold the coordinated tag, GitHub release, and announcement. Record which exact
   packages, versions, artifact digests, provenance records, and source commit are
   publicly visible.
2. If a workflow timed out or returned an ambiguous result, query the registry and
   install that exact version before retrying. Never assume that an error means the
   registry rejected the upload.
3. Keep correctly published artifacts in place. Requalify and publish only the
   missing packages from the same reviewed source commit; do not republish a version
   that the registry already accepted.
4. If a published artifact is incorrect, stop the sequence. Do not overwrite or
   silently replace it. Use the registry's supported deprecation or withdrawal
   mechanism when appropriate, publish a corrected version of only the affected
   package, update dependent version constraints if needed, and record the divergence
   in `CHANGELOG.md` and the eventual release notes. Do not bump unrelated packages
   merely to make their versions match.
5. Resume the coordinated release only when the complete set of intended package
   versions passes clean registry installation and maps to the documented source.

These steps favor an explicit partial release over a falsely coordinated one. Package
availability and recovery notes remain visible until the sequence is complete.
