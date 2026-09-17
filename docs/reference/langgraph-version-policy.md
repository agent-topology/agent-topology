# LangGraph version-range expansion policy

[Documentation home](../README.md)

[#12](https://github.com/agent-topology/agent-topology/issues/12) shipped a
narrow supported LangGraph range with strict runtime rejection outside it, and
required conformance evidence rather than only loosening metadata to expand
it. That safety bar stays fixed. This page is the policy for how and when that
evidence gets produced as new LangGraph minor and patch releases ship, so a
consumer on an untested release can answer "when might my LangGraph version be
supported?" without filing a question.

This page states the policy only. It does not expand either producer's
declared range; see [Installation and compatibility](compatibility.md) for the
current exact supported versions and install commands, and
[Supported versions](../0.1-contract.md#supported-versions) for the
authoritative manifests.

## Candidate releases

A LangGraph release is a candidate for qualification once it is a stable,
non-yanked release on the package's registry: PyPI for the Python producer.
Prerelease, dev, and yanked releases are excluded from the candidate set. That
exclusion changes only through a future issue that explicitly revises this
policy; it is never inferred from a release simply being newer.

## Evaluation cadence

A newly published stable patch release is reviewed against this policy within
seven days of its publication.

[#167](https://github.com/agent-topology/agent-topology/issues/167) adds a
weekly, and manually dispatchable, check that compares stable PyPI releases
against the compatibility manifest and surfaces any candidate this seven-day
review missed. The check only detects and reports a gap; it does not qualify a
release or edit the manifest (see [What this policy does not
do](#what-this-policy-does-not-do)).

## Evidence required before a version is added

A version is added to a producer's `testedVersions` manifest entry only after
all of the following exist for that **exact** release, per the [research
catalog's evidence rules](../research/README.md#evidence-rules) and [ADR
0003](../decisions/0003-canonical-ordering-and-versioned-structure-hash.md):

- the exact PyPI release resolved to its immutable upstream tag or commit,
- the minimum structural probes needed to confirm the producer's
  introspection surfaces still hold,
- a full pass of that producer's own test suite against the release, and
- a full pass of the shared conformance suite against the release.

Only a `verified` catalog entry — reproduced by a checked-in probe on the
exact version — may enter `testedVersions`. `source-verified` or `documented`
evidence is not sufficient on its own.

## Manifest list versus installable dependency bound

Runtime acceptance (`ensure_supported_langgraph_version` /
`ensureSupportedLangGraphVersion`) always checks the installed version against
the exact `testedVersions` list, never a range. Python packaging metadata may
still need to declare a contiguous installable bound (for example
`langgraph>=1.2.10,<=1.2.11`) so `pip` can resolve a real dependency graph, but
that bound is never authoritative for acceptance. A version inside the
installable bound that is missing from `testedVersions` is still refused at
runtime.

## Release RC freeze rule

Each beta release's RC freeze records the exact set of stable PyPI releases
considered for that release, as of the RC branch cut. A patch published after
the freeze is not retroactively pulled into that release; it remains refused
by the frozen RC and becomes a candidate for the next qualification issue or
producer release instead.

## Where to check status

- [Installation and compatibility](compatibility.md) lists the current exact
  supported versions and the safe installation command for each package.
- Open range-expansion work is tracked as GitHub issues, for example
  [#168](https://github.com/agent-topology/agent-topology/issues/168) and
  [#169](https://github.com/agent-topology/agent-topology/issues/169) for the
  1.3.x and 1.4.x qualification Features coordinated under
  [#165](https://github.com/agent-topology/agent-topology/issues/165).
- The [#167](https://github.com/agent-topology/agent-topology/issues/167)
  workflow's run summary lists any stable release this policy's seven-day
  review has not yet covered.
- A rejected install reports the exact tested versions and an installation
  command for one of them directly in the runtime error message.

## What this policy does not do

- It never auto-edits a compatibility manifest. Every `testedVersions` entry
  requires a human-reviewed pull request carrying the evidence above.
- It never infers support from upstream semver alone. A newer patch that looks
  compatible by version number is refused until it has its own evidence.
- It never silently accepts an untested patch. Refusal is explicit, both at
  runtime and in the detection check's output.
