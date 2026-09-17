# 0014. Join identity: deduplicate equivalent declarations, encode sources unambiguously

- Status: Accepted
- Date: 2026-09-17
- Scope: workspace
- Issue: [#182](https://github.com/agent-topology/agent-topology/issues/182)
- Amends: [ADR 0003](0003-canonical-ordering-and-versioned-structure-hash.md)

## Context

[ADR 0003](0003-canonical-ordering-and-versioned-structure-hash.md) made
multi-source joins a distinct, canonically-ordered part of the document. It
did not consider what happens when a graph declares an *equivalent* join more
than once, or when a source node id itself contains the `+` character the
join id generator uses as a delimiter. Both producers compute a join's id as
`f"join:{'+'.join(sorted(sources))}:{target}"` from
[`_builder_structure`](../../packages/python/langgraph/src/agent_topology/langgraph/_describe.py)
and
[`builderStructure`](../../packages/typescript/langgraph/src/internal.ts),
one record per `builder.waiting_edges` / `builder.waitingEdges` entry, with no
deduplication and no escaping.

Two inputs, reproduced at topology commit `344954ee2df167e84df8cf072f7d8c067707da88`
and pinned in
[the pre-beta review](../research/internal-consumer/pre-beta-review-2026-09-17/README.md#r1--p1-producers-emit-invalid-duplicate-join-identities)
and its reproducers
([`join_collision.py`](../research/internal-consumer/pre-beta-review-2026-09-17/join_collision.py),
[`join_collision.mjs`](../research/internal-consumer/pre-beta-review-2026-09-17/join_collision.mjs)),
show this breaks element-address uniqueness:

1. **Reversed declaration order.** `add_edge(["a", "b"], "sink")` and
   `add_edge(["b", "a"], "sink")` both sort to `join:a+b:sink`. Both producers
   emit two join records with the identical id; `validate_document` /
   `validateDocument` correctly reject the result as a duplicate join id.
2. **Delimiter-bearing distinct source sets.** `["a+b", "c"] → sink` and
   `["a", "b+c"] → sink` are two different groupings, but both sort-and-join
   to the string `a+b+c`. JavaScript emits two `join:a+b+c:sink` records —
   the same duplicate-id failure as case 1, but from information loss in the
   encoding rather than from a repeated declaration. Python raises
   `langgraph.errors.InvalidUpdateError` from `compiled_graph.get_graph(xray=0)`
   — LangGraph's own drawable construction, called at
   [`_extract_graph`](../../packages/python/langgraph/src/agent_topology/langgraph/_describe.py)'s
   first line, before this producer's join logic runs — because LangGraph's
   internal channel naming has the identical `+`-join collision on its own
   internal names. This is a distinct, upstream-unobservable failure that
   happens to share a root cause; it is not evidence that this producer's
   join-id generation is what failed for that input.

`derived_join_edges` / `derivedJoinEdges` in `agent_topology.spec` /
`@agent-topology/spec` and the reference validator's duplicate-id check are
unaffected: they are correct given valid input, and the validator's rejection
of the duplicate ids above is exactly the intended behavior of ADR 0003's
"joins are structural collections, so ids must be unique" contract. The
defect is entirely in how each producer computes the `id`/groups declarations
into records, upstream of validation.

### What "duplicate" and "permuted" declarations mean at runtime

Before choosing between deduplicating equivalent declarations and giving each
one an occurrence-distinct identity, we checked what LangGraph itself does
with them, rather than assuming either answer:

```python
builder.add_edge(["a", "b"], "sink")
builder.add_edge(["b", "a"], "sink")
# builder.waiting_edges == {(("a", "b"), "sink"), (("b", "a"), "sink")}
# compiled.channels includes both "join:a+b:sink" and "join:b+a:sink"
compiled.invoke({"values": [], "sink_calls": []})
# => sink_calls == [1]  -- "sink" runs exactly once
```

LangGraph's Python builder stores `waiting_edges` as a `set` of
`(sources_tuple, target)`, so a literal repeat (`add_edge(["a", "b"], "sink")`
twice, identical order) collapses to one element automatically, before this
producer ever sees it. A *permuted* repeat (`["a", "b"]` then `["b", "a"]`)
does not collapse there — Python tuples differ by order, so the set keeps
both — and LangGraph allocates two distinct internal channels, `join:a+b:sink`
and `join:b+a:sink` (its own naming, unsorted, with the same `+`-delimiter
defect this ADR fixes for the public document). Despite that, invoking the
compiled graph runs `sink` exactly once: both channels are written by the
same two nodes, so they always become ready in the same superstep, and
LangGraph runs a node at most once per superstep regardless of how many of
its trigger channels fired.

LangGraph.js's builder stores `waitingEdges` as a `Set` of arrays added by
reference (`this.waitingEdges.add([startKey, endKey])`), so even a literal,
identically-ordered repeat is *not* deduplicated at the builder level —
JavaScript `Set` uses reference equality for arrays. Invoking the compiled
graph confirms the same runtime behavior as Python's permuted case: `sink`
still runs exactly once, because both waiting-edge entries are triggered by
the same writes.

The conclusion holds for both languages and both forms of repetition: **two
or more join declarations that share a sorted source set and target describe
one AND-barrier, not two.** LangGraph fires the target once per superstep in
which every source has written, no matter how many equivalently-grouped
declarations produced that barrier. This is unlike an ordinary edge, where
two declarations with the same `(source, target)` can be genuinely
independent OR-triggered paths (this is why `_edge_documents` /
`edgeDocuments` assigns duplicates an occurrence-numbered id instead of
deduplicating them — that precedent does not transfer to joins, and this ADR
does not change it).

## Decision

### Deduplicate joins by (sorted source set, target)

Both producers group `waiting_edges` / `waitingEdges` entries by
`(tuple(sorted(sources)), target)` and emit exactly one join record per
group, keeping the resulting `sources` sorted. Two or more declarations
naming the same source set and target — whether by exact repetition or by
permutation — collapse to one join in the output document, matching the
runtime semantics established above. A different source set, even one that
shares a source or a target with another join, remains a separate record.

### Encode sources so distinct groupings cannot collide

The join id's source segment escapes each sorted source id before joining
with `+`: backslash first (`\` → `\\`), then the delimiter (`+` → `\+`).
Every unescaped `+` in the encoded string is then a genuine boundary between
sources, so two differently-grouped source lists always encode to different
strings, regardless of what a node happens to be named. `["a", "b+c"]`
encodes to `a+b\+c`; `["a+b", "c"]` encodes to `a\+b+c` — distinct ids,
`join:a+b\+c:sink` and `join:a\+b+c:sink`. A source id containing neither
character is unaffected and produces byte-identical output to before this
change.

This escapes only the `+` join-source delimiter. It does not attempt a
general collision-free encoding across the whole `join:<sources>:<target>`
id (for example, a source or target containing `:`) — that is unreported,
untested, and out of the scope this issue set: "no generic graph-ID
redesign."

### The Python delimiter-collision input keeps its upstream disposition

No code changes for the Python `InvalidUpdateError` case: it is LangGraph's
own drawable construction failing on its own internal channel-naming defect,
before this producer's builder-structure logic runs, for the specific
combination of node names it happens to collide on. Inventing a document for
input this producer never receives, or reporting it as "extraction
succeeded," would misattribute a limitation the review explicitly warned
against conflating with this fix
([pre-beta review, R1](../research/internal-consumer/pre-beta-review-2026-09-17/README.md#r1--p1-producers-emit-invalid-duplicate-join-identities)).
[`test_join_identity.py`](../../packages/python/langgraph/tests/test_join_identity.py)
pins this as an explicit, tested expectation
(`pytest.raises(InvalidUpdateError)`) rather than leaving it an unobserved
crash, at the public `describe()` API. The CLI already had a generic
uncaught-exception path (`_describe_command`'s `except Exception` ->
`ExitCode.EXTRACTION`, printing the exception's type without fabricating a
document);
[`test_cli.py::test_delimiter_bearing_join_sources_is_an_extraction_failure`](../../packages/python/langgraph/tests/test_cli.py)
pins that this specific input takes that path and writes no output file,
rather than leaving the CLI's behavior for it untested. LangGraph.js does not
fail upstream for the equivalent input; its document is produced and
validated as part of the same fix.

### No structure-hash algorithm version change

`STRUCTURE_HASH_ALGORITHM_VERSION` stays `"1"`. Every existing valid
conformance fixture — none of which declares a permuted, repeated, or
`+`/`\`-bearing join — canonicalizes to the identical id, `sources`, and
hash as before this change; `conformance/fixtures/multi-source-join` is
unchanged byte-for-byte. The inputs this decision changes the output for
(cases 1 and 2 above) never had a valid prior document: the producer emitted
a `structure.joins` array that the independent validator rejected outright,
so there is no previously valid hash to preserve or migrate for them. This is
a defect correction within the algorithm ADR 0003 already defined, not a
redefinition of what the hash covers or how it orders collections.

## Consequences

- [`_builder_structure`](../../packages/python/langgraph/src/agent_topology/langgraph/_describe.py)
  and
  [`builderStructure`](../../packages/typescript/langgraph/src/internal.ts)
  group by `(sorted sources, target)` and escape each source before joining;
  every other extraction path (edges, branches, sentinels, entries) is
  unchanged.
- New shared conformance fixtures
  (`conformance/fixtures/independent-incoming-edges`,
  `conformance/fixtures/join-permuted-sources`,
  `conformance/fixtures/join-repeated-declaration`) exercise, identically in
  both languages: two ordinary edges converging without a join (contrasted
  against the existing all-join `multi-source-join` fixture), permuted
  duplicate declarations collapsing to one join, and repeated identical
  declarations collapsing to one join.
- Producer-specific tests
  ([`test_join_identity.py`](../../packages/python/langgraph/tests/test_join_identity.py),
  [`join-identity.test.mjs`](../../packages/typescript/langgraph/tests/join-identity.test.mjs))
  cover what cannot be a shared fixture: the Python upstream-unobservable
  delimiter disposition, the JavaScript delimiter-bearing valid-and-distinct
  disposition, declaration-order stability for genuinely distinct joins (per
  ADR 0003), and a negative control confirming two source sets that overlap
  and share a target still produce two distinct joins. A CLI-level test
  (`test_cli.py::test_delimiter_bearing_join_sources_is_an_extraction_failure`)
  pins the same Python disposition through `agt describe`.
- Both producers' full test suites pass unmodified against every manifest
  version (`packages/python/langgraph/src/agent_topology/langgraph/_compatibility.json`:
  LangGraph 1.2.10, 1.2.11; `packages/typescript/langgraph/src/compatibility.json`:
  LangGraph.js 1.4.14).
- `derived_join_edges` / `derivedJoinEdges` and the reference validator are
  unchanged; the validator's duplicate-join-id rejection remains exactly as
  strict, it simply no longer fires on this producer's own output for these
  inputs.

## What we are explicitly not doing

- **Redesigning graph-element ids in general.** This decision escapes exactly
  the `+` join-source delimiter; it does not attempt a collision-free scheme
  for arbitrary characters across the whole `join:<sources>:<target>` or
  `edge:<source>:<target>:<kind>:<n>` id shape.
- **Changing the structure hash algorithm version or ADR 0003's ordering,
  hashed-field, or multi-source-versus-independent-edges rules.** Only the
  Python/TypeScript producer logic that groups `waiting_edges` /
  `waitingEdges` into `structure.joins` records changes.
- **Giving repeated/permuted join declarations occurrence identity**, the way
  `_edge_documents` / `edgeDocuments` do for ordinary edges. The runtime
  evidence above shows this would misrepresent one AND-barrier as two.
- **Fixing LangGraph's own internal `+`-delimited channel-naming collision.**
  That is upstream, LangGraph Python's, and out of this repository's control;
  this decision only ensures this producer does not inherit it into a public
  document when LangGraph itself does not crash first.
- **A new runtime execution feature, schema relaxation, or weakening the
  independent validator.** The validator's behavior is unchanged; this
  decision makes both producers stop producing input it correctly rejects.
