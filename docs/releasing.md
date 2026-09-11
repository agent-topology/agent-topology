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
5. Create the coordinated `v0.1.0-beta.1` Git tag, GitHub release, and announcement
   only after all four artifacts pass. The Python and npm sequences may run
   independently, but the specification package always precedes its producer within
   an ecosystem.

The protected workflows publish one selected package at a time. A successful run for
one package does not authorize another package and does not prove the four-package
preview complete.

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
