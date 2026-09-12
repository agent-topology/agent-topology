# 0009. Numeric canonical form and its hash boundary

- Status: Accepted
- Date: 2026-09-12
- Scope: workspace
- Issue: [#117](https://github.com/agent-topology/agent-topology/issues/117)

## Context

[F8](https://github.com/agent-topology/agent-topology-testbed/blob/e0e23c5e111db5a25fba736377d05f43df9fd5a0/findings/F8-extension-number-canonicalization/README.md),
backed by [E1](https://github.com/agent-topology/agent-topology-testbed/blob/e0e23c5e111db5a25fba736377d05f43df9fd5a0/observations/E1/README.md),
shows that published `agent-topology-spec==0.1.0b2` and
`@agent-topology/spec@0.1.0-beta.2` accept the same valid document and agree
on `structureHash` (`sha256`, algorithm version `1`), but emit different
full-document canonical bytes when an `x-*` extension carries a JSON number.
The retained minimum case is a 479-byte document containing one empty graph
and `"x-e1": 0.0`: Python's `canonical_json` emits `...,"x-e1":0.0}`;
TypeScript's `canonicalStringify` emits `...,"x-e1":0}`. Neither
[`_canonical.py`](../../packages/python/spec/src/agent_topology/spec/_canonical.py)
nor [`canonical.ts`](../../packages/typescript/spec/src/canonical.ts) defines
a number-spelling rule; each inherits whatever its own `json.dumps` /
`JSON.stringify` does. [ADR 0003](0003-canonical-ordering-and-versioned-structure-hash.md)
canonicalises collection order and hashes a versioned structural projection;
it never picked a byte spelling for the number type, because until E1 no
fixture or hand-written test put a number where canonical bytes were
compared.

Nothing in the checked-in [`agent-topology.schema.json`](../../spec/agent-topology.schema.json)
gives a core field a numeric type. Every place a JSON number can appear in a
`topologyVersion: "0.1"` document today is inside a producer- or
framework-owned `x-*` extension, which accepts arbitrary JSON. The version-1
structure-hash projection (`_structure_projection_v1` / `projectStructureV1`)
selects only `id`, `type`, `subgraphId`, `interrupts`, `source`, `target`,
`kind`, `sources`, `entryNodeIds`, and `exitNodeIds` — every one of them a
string or an array of strings — and drops every extension outright. Both
facts hold independently of each other; either alone already keeps a
numeric-spelling fix out of the hash.

`ARCHITECTURE.md`, `CONVENTIONS.md`, and the [0.1 contract](../0.1-contract.md)
currently say, in three near-identical sentences, that "a canonicalisation ...
change requires a new hash algorithm version." Read literally, that sentence
would force a `structureHash.algorithmVersion` bump for a numeric-spelling fix
that cannot change a single byte the version-1 projection hashes, for any
document the current schema allows. That reading is not what ADR 0003 argued
for — it argued for versioning changes that affect what the hash *compares* —
but the wording does not say so, and this Task exists partly to say so before
[#118](https://github.com/agent-topology/agent-topology/issues/118) has to
guess.

The approved beta.3 target keeps `topologyVersion` at `"0.1"` and
`structureHash.algorithmVersion` at `"1"` ([0.1 contract](../0.1-contract.md)).
This decision has to show that keeping both is consistent with fixing F8, or
say plainly that beta.3 is blocked pending a separate scope decision.

## Decision

### Canonical number spelling

A JSON number's canonical byte spelling is the result of the ECMAScript
`Number::toString` algorithm (ECMA-262, "ToString Applied to the Number
Type") applied to its IEEE 754 `binary64` value — the same rule
[RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) (the JSON Canonicalization
Scheme) adopts for the same reason: it is a total, deterministic, shortest
round-tripping function from every finite `binary64` value to a decimal
string, already specified by an external standard neither package owns, so
neither language's runtime default gets to be the tie-breaker by default.

Concretely, for a finite value `x`:

- `+0` and `-0` both spell `0`. Sign is not observable in canonical bytes.
- A negative value spells `-` followed by the spelling of its magnitude.
- Otherwise, take the shortest decimal digit string `s` (`k` digits, no
  leading zero) and decimal exponent `n` such that `s × 10^(n−k)` parses back
  to exactly `x` (ties broken toward the closer value, further ties toward an
  even last digit — the same "shortest round-trip" rule `repr(float)` and
  `Number::toString` each already implement; they just don't format the
  result the same way). Then:
  - if `k ≤ n ≤ 21`: the `k` digits of `s`, followed by `n − k` zeros — an
    integral spelling with no fraction and no exponent;
  - if `0 < n ≤ 21`: the digits of `s` with a `.` inserted after the `n`th
    digit;
  - if `-6 < n ≤ 0`: `0.` followed by `-n` zeros, followed by the digits of
    `s`;
  - otherwise: the first digit of `s`, then (if `k > 1`) a `.` and the rest
    of `s`, then `e`, then `+` or `-`, then the decimal digits of `|n − 1|` —
    exponential form, lower-case `e`, explicit sign, no leading zero in the
    exponent.

Byte oracle for finite `binary64` values (the
[0009 implementation criteria](0009-implementation-criteria.md) restate these
as the literal regression cases for #118):

| Value | Canonical bytes |
| --- | --- |
| `0.0` | `0` |
| `-0.0` | `0` |
| `1.0` | `1` |
| `-100` | `-100` |
| `100` | `100` |
| `0.5` | `0.5` |
| `1e-6` | `0.000001` |
| `1e-7` | `1e-7` |
| `1e20` | `100000000000000000000` |
| `1e21` | `1e+21` |

`1e-6`/`1e-7` and `1e20`/`1e21` are kept as adjacent pairs because they
straddle the two decimal/exponent thresholds above (`n = -6` is the last
fixed-point exponent below zero; `n = 21` is the last fixed-point exponent
before the format switches to exponential) — the pair, not either value
alone, is the regression that proves the boundary lands in the right place.
`0.0`/`-0.0` and `100`/`-100` are kept as pairs for the same reason: they are
the retained F8/E1 candidate and its sign-boundary neighbor.

### Supported numeric domain and its error behavior

The supported numeric domain is exactly the finite IEEE 754 `binary64`
values. `NaN` and `±Infinity` stay rejected exactly as they are today
(Python's `json.dumps(..., allow_nan=False)` already raises `ValueError`;
TypeScript's `ordered` already raises `TypeError` for
`!Number.isFinite(value)`); this decision does not relax that.

A JSON number literal with no `.` or exponent (an integer literal) decodes
losslessly in Python to an arbitrary-precision `int`, but in TypeScript every
JSON number, integer literal or not, decodes through `JSON.parse` straight to
a `binary64` double. An integer literal whose magnitude is at most `2^53`
(`9007199254740992`) round-trips through a double exactly in either
language, so it is in-domain and spells per the table above. Beyond `2^53`,
Python can hold the exact value and TypeScript structurally cannot — so
`canonicalize_document` / `canonicalizeDocument` must reject such a value
outright (the same rejection path as the existing non-finite check, not a
new, differently-shaped error) rather than silently narrowing it to the
nearest double. Emitting Python's exact integer would not be "losing
precision" in Python alone, but it would silently reintroduce exactly the
kind of byte divergence this decision exists to close, undetectably, since
nothing about a passing schema or a matching structure hash would reveal it.
A literal that already carries a `.` or exponent decodes to a double in both
languages before canonicalization ever runs, so it is always in-domain
(subject only to the finite-value restriction above) — the `2^53` integer
boundary is the only new domain edge this decision adds.

### Full-document serialization versus the version-1 hash projection

This is a full-document canonical-form decision. It does not touch
`structureHash.algorithmVersion`, for two independent reasons, either one of
which is sufficient on its own:

1. Every field the version-1 projection selects (`id`, `type`, `subgraphId`,
   `interrupts`, `source`, `target`, `kind`, `sources`, `entryNodeIds`,
   `exitNodeIds`) is a string or an array of strings in the current schema.
   There is no numeric core field for a spelling rule to touch.
2. Extensions — the only place a JSON number can currently appear — are
   wholly excluded from the version-1 projection regardless of type.

Point 2 alone would already be an answer, but it is not the reason relied on
here: it would stop protecting the hash the day a core field ever became
numeric, and nothing about that future change is decided by this ADR. Point 1
is the independent, present-tense fact that closes the question for the
schema as it exists today. Should a future ADR give a core field a numeric
type, *that* ADR carries the `structureHash.algorithmVersion` bump under the
general rule restated below — this decision does not pre-empt that and does
not need to.

`ARCHITECTURE.md`, `CONVENTIONS.md`, and the [0.1 contract](../0.1-contract.md)
each say "a canonicalisation ... change requires a new hash algorithm
version" without qualification. That sentence is corrected in all three (see
Consequences) to say what ADR 0003 actually meant: a hash-algorithm-version
bump is required when a canonicalisation change can alter the byte output of
the version-1 hash projection, or when the set of hashed structural
properties changes — not for every canonicalisation change anywhere in the
document. A canonicalisation change confined to fields or extensions the
projection excludes is a specification-package change, not a hash-algorithm
change.

### Compatibility with beta.3 and already-published bytes

`topologyVersion` stays `"0.1"`; `structureHash.algorithmVersion` stays `"1"`.
Both are justified above, not merely asserted: no core field is numeric, and
the hash-affecting reason (exclusion of extensions) is backed by the
independent, present-tense reason (no numeric core field exists to exclude
in the first place). Beta.3 is not blocked by this decision.

Published `0.1.0b2` / `0.1.0-beta.2` canonical bytes for documents whose
extensions carry numbers are historical and are not rewritten; the
[F8 finding](https://github.com/agent-topology/agent-topology-testbed/blob/e0e23c5e111db5a25fba736377d05f43df9fd5a0/findings/F8-extension-number-canonicalization/README.md)
already establishes that neither package's beta.2 artifact digests nor any
historical release-qualification receipt are affected by anything measured
here. Once the fixed specification packages release, re-canonicalizing the
*same* logical document that contains an extension number can produce
different full-document bytes than the same document canonicalized by a
beta.2 package — this is the fix, not drift, and is a **specification
package** version change (`agent-topology-spec` / `@agent-topology/spec`),
independent of `topologyVersion` and `structureHash.algorithmVersion`, per
the contract's existing independent-version-axes table. `structureHash`
values are unaffected for every document under the current schema, so any
consumer or CI check gated on hash equality sees no disruption.
Consumer-facing migration wording for this change is
[#104](https://github.com/agent-topology/agent-topology/issues/104)'s job,
not this ADR's; this section supplies the compatibility facts #104 needs and
does not re-litigate release mechanics owned by
[#107](https://github.com/agent-topology/agent-topology/issues/107).

## Consequences

- [`ARCHITECTURE.md`](../../ARCHITECTURE.md), [`CONVENTIONS.md`](../../CONVENTIONS.md),
  and the [0.1 contract](../0.1-contract.md) each replace their unqualified
  "canonicalisation ... requires a new hash algorithm version" sentence with
  the qualified rule above, and the contract gains a "Numeric canonical form"
  subsection stating the byte oracle and domain boundary normatively.
- [#118](https://github.com/agent-topology/agent-topology/issues/118) can
  implement `canonical_json` / `canonicalStringify` number handling against
  the [0009 implementation criteria](0009-implementation-criteria.md) without
  choosing its own spelling, domain boundary, or version-transition answer.
- Existing fixtures, hashes, and conformance results are unaffected: none of
  them place a number inside an extension today.
- A future ADR that gives a core field a numeric type inherits the general
  rule restated here (point 1 of the hash-boundary reasoning stops applying,
  point 2 alone is not enough on its own, and the field addition must carry
  its own `structureHash.algorithmVersion` decision); it does not inherit an
  exemption from this one.

## What we are explicitly not doing

- **Implementing the serializer fix.** That is
  [#118](https://github.com/agent-topology/agent-topology/issues/118), gated
  on this ADR by its own non-goals.
- **Promoting a core field to numeric, or inferring a broader numeric domain
  from E1's generated population.** E1's `-100..100` integers and seven
  finite floats are coverage evidence for the boundary cases above, not a
  ceiling or floor on what `x-*` extensions may contain within the domain
  this decision defines.
- **Adding a public API.** The oracle is a byte-spelling and domain rule for
  the existing `canonicalize_document` / `canonicalizeDocument` and
  `canonical_json` / `canonicalStringify` functions, not a new entry point.
- **Rewriting historical beta.2 artifacts or receipts.** Covered above under
  Compatibility.
- **Writing beta.3 consumer migration notes.** That is
  [#104](https://github.com/agent-topology/agent-topology/issues/104).
