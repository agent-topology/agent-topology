# 0001. Scope: topology extraction and trace correlation

- Status: Accepted
- Date: 2026-09-10

## Context

The library reads a compiled LangGraph object and emits a structured document
describing the graph: its nodes, its edges, and the parts of the graph it could
not observe. A conformance runner compares that output against recorded
fixtures.

While reviewing the producer we asked who the document is for. Three candidate
consumers came up, and each turned out to demand something different from the
document's core fields.

A **renderer** demands the least. Nodes, edges and labels are enough to draw a
picture. Its one real requirement is that it must be able to draw uncertainty,
because a renderer that turns an incomplete document into a confident picture is
lying.

A **policy or lint engine** demands the most, and it is the only consumer that
has to return a negative verdict. To claim that every path reaches an approval
step, it has to know the edge list is complete. Today it cannot know that. On
langgraph 0.2.76 a conditional edge with no path map draws edges to every node
and raises no gap, so a router that can go anywhere is recorded as an ordinary
declared branch. A policy engine reading that document passes it. That is a
false pass, and a false pass is worse than no answer.

A **path coverage generator** demands the strangest thing of all: the meaning of
each branch. It has to know whether a split chooses one target or runs all of
them. Today Send fan-out is recorded as a single conditional edge, so a
generator would count several alternative paths where there is really one path
that runs everything. It would also have to distinguish an all-join from an
any-join, which the current document does not.

Satisfying all three would mean adding branch semantics, join semantics,
three-valued logic for uncertainty, and a stability guarantee for node identity.
We are not in a position to design those fields honestly. There is exactly one
producer, and it reads LangGraph. Any field added now to answer a question we
have not actually hit would be shaped by how LangGraph happens to represent
things, and we would be unable to tell the difference between a general concept
and a local one.

## Decision

The scope of this library is:

1. Extract the topology of a compiled graph object into a structured document.
2. Record what the extraction could not observe, rather than emitting a document
   that appears complete.
3. Make that document usable for correlating a graph's declared structure with
   what actually happened at runtime.

Trace correlation is the first intended use, and it is chosen deliberately over
the three consumers above.

A static document cannot see dynamic behaviour. Interrupts raised inside a node
body are invisible. Fan-out width is unknown until it runs. Parallelism inside a
single node is invisible to any graph format. A runtime log has exactly the
information the document lacks, and the document has the structure the log
lacks. Together they cover each other's blind spots.

Trace correlation also tolerates uncertainty in a way the other consumers do
not. A policy engine must resolve every gap into a verdict. A correlation view
can show a known skeleton, mark the parts that are unknown, and remain useful.
That is the right demand to place on the document while there is only one
producer behind it.

## Consequences

Near-term work is limited to what this scope requires:

- Separate the producer's general limitations from the defects of a specific
  graph, so that a document about a well-formed graph can be complete and the
  strict exit code means something.
- Canonicalise ordering before hashing and before output, so that declaring the
  same topology in a different order yields the same result, and pin the
  supported library range tightly enough that a minor upgrade does not silently
  change the answer.
- Align the public API with the documentation, and expose the depth option
  through a supported keyword rather than an internal one.
- Add a gap that names the routing node whose targets could not be determined.
  Under this scope this matters because that node is exactly where a runtime log
  and the declared structure will fail to line up.

Known shortcomings are accepted for now and recorded rather than fixed:

- Send fan-out is classified as a branch. This produces a wrong answer for a
  coverage generator, which we are not building.
- The structure hash does not distinguish an all-join from an any-join.
- Framework-specific sentinel nodes appear alongside ordinary nodes.

Each of these becomes blocking only when a consumer that depends on it exists.

## What we are explicitly not doing

- **Rendering as a core concern.** Diagram output belongs in a
  framework-specific extension and is not compared by the conformance runner. A
  renderer built on the document is welcome as a separate example consumer; a
  renderer inside the core would make this a viewer, and viewers have no end.
- **Lint or policy rules.** Deferred until the document can support a negative
  verdict without false passes.
- **Path coverage generation.** Deferred until branch and join semantics are
  settled, because an incorrect coverage number is worse than none.
- **Claiming vendor neutrality.** The split between core fields and
  framework-specific ones is unverified while a single producer exists. This is
  addressed separately.

## Revisiting

Reopen this decision when any of the following happens:

- A second producer reading a genuinely different framework exists, which would
  let us tell general fields from LangGraph-shaped ones.
- Trace correlation is in real use and the correlation itself is blocked by a
  missing field. A field requested by a hypothetical consumer is not a reason to
  reopen; a field that trace correlation cannot proceed without is.
