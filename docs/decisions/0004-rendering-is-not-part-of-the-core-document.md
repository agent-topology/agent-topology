# 0004. Rendering is not part of the core document

- Status: Accepted
- Date: 2026-09-10

## Context

The document currently carries a diagram representation in its core, and the
conformance runner compares it.

That representation is specific to one framework and one version of it. A second
producer reading a different framework could not reproduce it, so a conformance
suite that compares it is testing agreement with a particular implementation
rather than agreement about a graph's structure. It also contradicts the
project's stated position that this is not a viewer.

The deeper problem is a slope. If diagram output is in the core and is part of
what conformance checks, then layout, labelling, direction, grouping, and
styling all become the project's problem in turn. Requests for them will be
reasonable, because the output is already there. Rendering has no natural
stopping point, and this project has one under ADR 0001.

## Decision

Diagram output moves out of the core into the framework-specific extension area,
and the conformance runner does not compare it.

Rendering remains supported as a **consumer** of the document rather than a part
of it. A separate renderer that reads only the document and produces a diagram
is welcome and useful: it demonstrates what the format enables in code, which is
what a tool builder actually evaluates, and it does so without the core taking
on a rendering contract.

Any such renderer must be able to display uncertainty. A renderer that turns a
document containing gaps into a confident-looking picture misrepresents it,
which is the failure ADR 0002 exists to prevent.

## Consequences

- Conformance compares structure only, and stops failing on presentation
  details that vary by framework and version.
- A second producer is no longer required to emit something it cannot
  meaningfully produce.
- Existing users of the diagram output must read it from the extension area.
  This is a breaking change and is worth making before the project is public.
- Requests for richer diagrams have a clear answer: they belong to a renderer,
  not to the core.

## What we are explicitly not doing

- **Removing diagram output.** It stays available, in the extension area, where
  it is understood to be framework-specific and is not part of the compared
  surface.
- **Shipping a renderer in the same package.** If one is built, it is a separate
  consumer with its own release cycle.
