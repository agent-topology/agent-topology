# 0005. Vendor neutrality is provisional at v0

- Status: Accepted
- Date: 2026-09-10

## Context

The long-term intent is a representation that several agent frameworks can be
described in, useful to people building tools across more than one of them. The
document is already split into core fields and a framework-specific extension
area on that basis.

That split is currently unverified. There is one producer, and it reads
LangGraph. A boundary between "general" and "framework-specific" that has only
ever been tested against one framework is an assertion, not a finding.

Evidence that the boundary is already leaking is visible in the core today. The
sentinel entry and exit nodes are one framework's internal convention sitting
alongside ordinary nodes. Interrupts as a concept entered the model through one
library's metadata key. Branch and fan-out are represented identically because
that framework represents them identically, even though choosing one target and
running all targets are different things in general.

The obvious way to test the boundary does not work. Reading the same framework
through a different entry point returns the same underlying graph object, so it
cannot reveal which parts of the model are local. It also produces unstable node
identifiers, which breaks the hash for unrelated reasons. Any re-review
condition that relies on it is untestable and should not be treated as evidence.

A second framework will not merely confirm or deny the boundary. It will supply
design input we do not currently have. The useful second framework is not one
that declares a graph in a similar way, because passing that tells us nothing.
It is one where an edge list does not exist in the source at all, and
connections are derived rather than declared. That forces questions the current
model does not raise: whether a recorded edge is a declared fact or an inference,
whether both belong in the same place, and who assigns node identity.

## Decision

The core is versioned at v0 and documented as provisional. The project does not
claim vendor neutrality until at least one producer reading a genuinely
different framework exists.

Provisional means the boundary may move. Fields now in the core may be
reclassified as framework-specific, and the reverse. Consumers should expect
this and are told so plainly rather than discovering it at a version bump.

When a field is proposed for the core, the test applied is whether it can be
pointed at in a system that does not declare its edges. If it cannot, it goes to
the extension area. This is a subtractive rule: the core holds what survives,
not what seems generally useful.

The core is expected to stay small under this rule, and that is the intended
outcome. A small core that a tool builder can rely on is worth more than a large
one that turns out to describe one library.

## Consequences

- Stating the limitation openly is a recruitment notice as much as a caveat.
  Whoever brings a second framework becomes a co-designer of the boundary, which
  is the only way it gets settled.
- Declaring v1 with a single producer would have the opposite effect. A later
  arrival would find a fixed format shaped by someone else's library and build
  their own instead.
- Repository boundaries follow this decision. Keeping the specification and
  conformance suite separate from the LangGraph producer decouples format
  versioning from library versioning, lets a third party build a producer
  elsewhere, and makes it structurally harder for us to bend the core toward one
  producer's convenience.
- Known leaks are recorded rather than fixed immediately. The sentinel nodes and
  the merged treatment of branch and fan-out are documented as suspected
  framework-shaped, to be revisited when there is a second framework to check
  them against.
- The gap and limitation model from ADR 0002 is the part we expect to generalise
  best, since every system has statically undeterminable behaviour.

## Revisiting

Promote beyond v0 when a producer reading a framework with a materially
different structural model exists, and the core has been adjusted in response to
what it revealed. Reading the same framework through another interface does not
satisfy this.
