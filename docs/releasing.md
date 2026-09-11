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

For beta.2 and later, prepare and qualify from `rc/<version>` as described
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

## Release candidate branches and immutable tags

`main` is the integration branch. Create `rc/<version>` from the reviewed
integration commit when stabilizing a release, for example
`rc/0.1.0-beta.2`. Prepare package manifests, lockfiles, compatible spec
dependencies, and candidate notes there. Each package manifest owns its version. Python producer provenance
reads installed distribution metadata (or its own pyproject.toml in a source
checkout); the npm producer reads its packaged package.json. CI artifact checks
and support-package selection read these prepared manifests.
Send release fixes through PRs targeting that branch. Keep unrelated development
out of the candidate and merge release corrections back into main through a PR.

The branch name identifies the release being coordinated; it does not override
the independently selected versions of its packages. Python retains PEP 440
versions (`0.1.0b2`) while the branch and npm use SemVer (`0.1.0-beta.2`). The
document format and hash algorithm versions do not follow either automatically.

Package and framework-compatibility CI runs on pushes to `rc/**`. Both manual
release workflows reject main, tags, and other branches. Dispatch inputs must
match the selected package's committed version; npm producer inputs must also
match its committed spec peer. Version selection belongs in reviewed source,
not an ad hoc build-time override. Use the RC branch explicitly, for example:

```bash
gh workflow run release-python.yml --ref rc/0.1.0-beta.2 -f package=spec -f version=0.1.0b2 -f publish=false
gh workflow run release-npm.yml --ref rc/0.1.0-beta.2 -f package=spec -f version=0.1.0-beta.2 -f publish=false
```

Freeze the branch commit while qualifying and publishing the intended package set.
Any source change requires fresh qualification. Record artifact receipts and
registry verification before tagging the exact qualified commit as `v<version>`.
Never move a published version tag. Retain the RC branch as the record of
preparation, and merge the release work back into main after publication.

The missing beta.1 tag was restored on 2026-09-11 at
`0e127d84d77904dd0a909fab0ea58862282ceae8`, the merge of the original release
notes in PR #74. The four package source trees match the qualified ancestor
commits listed in the beta.1 notes. This retrospective tag does not claim that
the artifacts were rebuilt from that merge or create a GitHub Release.

### Preparing package versions

Change only the independently selected package versions in their pyproject.toml
or package.json. Update the producer's spec dependency or peer only when its
compatibility selection changes; never copy the producer version into the spec.
Regenerate both Python locks with `uv lock --project packages/python/spec` and
`uv lock --project packages/python/langgraph`. Regenerate npm locks with
`npm install --package-lock-only --prefix packages/typescript/spec` and the
equivalent command for `packages/typescript/langgraph`; the producer lock also
records the linked local spec version.

Run release-tool tests (including the minimal independent-bump fixtures) and
`uv lock --check` for both Python projects, then npm clean installs and package
checks. Lock version guards reject stale root and linked-package copies.
Inspect each built artifact against prepared metadata and run clean-install
smokes to compare emitted provenance with the installed package version.
Dependency-name boundaries, runtime bounds, public exports, and file contents
remain independent artifact assertions. Release workflows package committed
metadata without rewriting support package versions or peers.

Update the current candidate notes. Historical beta.1 records and installation
guides intentionally selecting published versions are not version-bump targets.
Neither the topology format nor hash algorithm version changes for a package bump.

## Python producer environment protection

For [Task #78](https://github.com/agent-topology/agent-topology/issues/78), the
GitHub environment `pypi-agent-topology-langgraph` was aligned with
`pypi-agent-topology-spec` and `npm-public-preview` on 2026-09-11. The following
non-secret settings were read before the change and read back through the GitHub
API at 15:51 UTC after the change:

| Setting | Before | After |
| --- | --- | --- |
| Required reviewers | None (`protection_rules: []`) | User `milocosmopolitan` (ID `5334538`) |
| Deployment branch policy | `null` (unrestricted) | `protected_branches: false`, `custom_branch_policies: true` |
| Allowed deployment refs | No configured restriction; branch-policy endpoint returned HTTP 404 | Exactly one policy: `rc/*`, type `branch`, ID `59722545`; no tag policies |
| Prevent self-review | No reviewer rule | `false`, matching spec and npm |
| Administrator bypass | `can_admins_bypass: true` | `true`, unchanged and matching spec and npm |

The read-back confirmed the same reviewer and branch restriction on all three
environments. The existing spec and npm branch-policy IDs remained `59671098`
and `59707177`, respectively. Only the producer environment's protection settings
were changed; no publisher identity, token, registry configuration, or unrelated
environment was changed.

In `.github/workflows/release-python.yml`, the `selection` job maps
`inputs.package == 'langgraph'` to `distribution=agent-topology-langgraph`.
The `publish` job selects `pypi-${{ needs.selection.outputs.distribution }}`,
which resolves to this protected environment. This wiring was inspected and
required no workflow edit.

Publication remains a separate manual boundary after qualification: dispatch
from an allowed `rc/*` branch with `publish=true`, then obtain the configured
maintainer's environment approval before the `publish` job runs. A PR merge or
a successful `authorize` job does not supply that approval. The established model
allows the initiating maintainer to approve their own deployment and permits
administrator bypass; it does not enforce approval by a second person.
Maintainers should use the approval gate rather than bypass it. With
`publish=false`, the publish job is skipped. No release workflow or publication
was triggered to verify this configuration change.

Recheck the live rules and the complete branch-policy list before publication:

```bash
gh api repos/agent-topology/agent-topology/environments/pypi-agent-topology-langgraph \
  --jq '{name, can_admins_bypass, deployment_branch_policy, protection_rules: [.protection_rules[] | {type, prevent_self_review, reviewers: [.reviewers[]? | {type, id: .reviewer.id, login: .reviewer.login}]}]}'
gh api --paginate repos/agent-topology/agent-topology/environments/pypi-agent-topology-langgraph/deployment-branch-policies \
  --jq '{total_count, branch_policies}'
```

These endpoints expose configuration, not credentials. This record verifies the
configured approval and branch boundary, not a live deployment approval exercise.

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
