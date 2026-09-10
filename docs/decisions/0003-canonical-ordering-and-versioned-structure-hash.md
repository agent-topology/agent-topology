# 0003. Canonical ordering and a versioned structure hash

- Status: Accepted
- Date: 2026-09-10

## Context

The document carries a hash of the graph's structure, intended as a compact way
to tell whether a topology changed.

It does not currently sort the collections it hashes. Declaring the same
topology in a different order produces a different hash. Moving from
langgraph 0.2.76 to 1.2.11, five of seven fixtures failed, and four of those
differed only in edge order. The graphs were identical.

This is worse than an ordinary bug because of where the value ends up. A hash
like this gets put in a continuous integration check. Once it is there, a false
change is not a wrong number on a screen; it is a build that fails for no
reason. People tolerate that once or twice and then stop trusting the check.
The supported library range is also currently loose enough that a routine
upgrade can move the value without anyone choosing to.

There is a second problem. A hash is a claim about what counts as the same
structure. Today a join declared as a single edge from several sources and a
join declared as separate edges hash identically, even though the first waits
for all sources and the second does not. A real difference in behaviour is being
declared equal.

This was initially assumed to be a limit of what can be extracted. It is not.
Both the Python and JavaScript builders keep multi-source edges in a separate
collection from ordinary edges, so the distinction survives compilation and is
readable at the same level as everything else we already read. The information
was never lost; the extractor does not look at it.

That changes what this decision has to say about it. An omission we can fix is
not a documented limitation.

## Decision

Ordering is canonicalised before hashing and before output. The same topology
yields the same document and the same value regardless of the order in which it
was declared or the order the underlying library happens to return.

The hash carries an explicit algorithm version. When the canonical form or the
set of hashed properties changes, the version changes with it, so a consumer can
distinguish "the graph changed" from "the way we hash changed". Producing both
the old and new value during a transition is permitted.

The supported library range is pinned narrowly enough that a version outside the
tested range is refused rather than silently producing a different answer.

Multi-source edges are read from the builder and represented distinctly from a
set of single-source edges arriving at the same target. The hash reflects that
distinction. Two graphs that wait differently do not hash the same.

What the hash covers is documented, including anything it deliberately treats as
equal, so that a passing check is not the only place a reader could discover
what was compared.

## Consequences

- Fixtures stop failing on ordering, and the remaining failures across library
  versions become real findings about the extraction rather than noise.
- The hash becomes usable in an automated check without generating false
  changes on upgrade.
- Version-tagging is an admission that the hash is not final, which is accurate
  while the underlying model is still incomplete.
- Graphs that use multi-source edges change hash relative to earlier output.
  This is expected, is a correction rather than drift, and is exactly what the
  version tag exists to communicate.
- Join handling becomes a property the fixtures must cover, including the pair
  that previously collapsed: a multi-source edge and the equivalent-looking set
  of single edges must produce different documents.
- The two ways of declaring a join are no longer interchangeable to a consumer,
  which is the point. A trace that shows a target running once after two
  upstream nodes means something different in each case.

## What we are explicitly not doing

- **Modelling concurrency beyond what is declared.** Recording that an edge
  waits for several sources is not the same as describing a parallel region, and
  we are not attempting the latter. Fan-out width and anything decided at
  runtime stay out of scope under ADR 0001.
- **Hashing labels, metadata, or anything descriptive.** The value answers a
  question about shape.
- **Promising stability across producer versions.** Stability is promised within
  an algorithm version. If a fix changes what we extract, the value changes, and
  the version tag is how that is communicated.
