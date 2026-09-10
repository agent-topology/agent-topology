# 0002. Record what could not be observed

- Status: Accepted
- Date: 2026-09-10

## Context

Extracting a graph's topology is not hard. What separates a document that can be
audited from a picture is whether it admits what it could not see.

Every extraction from a running system has blind spots. Interrupts raised inside
a node body do not appear in node metadata. Parallelism inside a single node is
invisible: a graph with a model node and a tool node looks like two nodes no
matter how many tool calls run at once. A router whose targets cannot be
enumerated may still be drawn as if its targets were known. Most introspection
tools emit a complete-looking result and say nothing about any of this. A reader
cannot tell the difference between "there is nothing there" and "we could not
look".

The current implementation does try to record this, but in a way that destroys
the signal. A marker for unobservable dynamic interrupts is attached to every
document, regardless of the graph. Completeness is therefore always false and
the strict mode always fails. A warning that is always on carries no
information, and a downstream viewer built on it would show a permanent
disclaimer banner.

The reason is that two different things are being written to the same place. One
is a property of the extractor: there are categories of behaviour this producer
cannot see in any graph. The other is a property of the graph in front of us:
this particular router's targets could not be determined. The first is constant
and belongs to the producer. The second varies per graph and is the actual
finding.

## Decision

The document records both, in separate places.

**Producer limitations** describe what this extractor cannot observe in
principle. They are the same for every graph produced by the same extractor at
the same version. They do not affect whether a given document is considered
complete.

**Gaps** describe something specific about the graph being described. They are
findings. A document with no gaps is complete; a document with gaps is not.

Gaps attach to the element they concern rather than to the document as a whole.
A single router with undeterminable targets should not make the entire graph
unreadable to a consumer. A consumer needs to know which node or edge is
uncertain so it can treat that region differently and trust the rest.

Where a gap concerns routing, it names the routing node, not only the targets
that were left dangling. The node whose behaviour is undetermined is the useful
subject. Naming only its orphaned targets also fails outright when a target has
another incoming edge, which is a real case in the current implementation.

## Consequences

- Completeness becomes a meaningful signal, and strict mode can succeed. Both
  are prerequisites for using this in any automated check.
- A consumer can degrade locally instead of globally: mark one region as
  unknown, keep the rest.
- Limitations must be versioned with the producer, since adding an observation
  capability removes a limitation and changes what past documents claimed.
- Some findings currently expressed as absence become explicit. A router whose
  targets could not be enumerated is recorded as such, rather than as a router
  with a plausible-looking set of edges.

The distinction is expected to survive a change of framework. Every system has
behaviour that cannot be determined statically; only the specific forms differ.
This makes it one of the few parts of the document we expect to be general
rather than shaped by the first producer, which is relevant to ADR 0005.

## What we are explicitly not doing

- **Assigning severity to gaps.** Whether an unknown region is acceptable
  depends on the consumer, and there is one consumer today.
- **Guaranteeing that the gap list is exhaustive.** We record blind spots we
  know about. Claiming to know all of them would be the same overconfidence this
  decision exists to avoid.
