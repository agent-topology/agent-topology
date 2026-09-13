# 0010. Numeric domain closure: narrow parsed values instead of rejecting them

- Status: Accepted
- Date: 2026-09-12
- Scope: workspace
- Issue: [#124](https://github.com/agent-topology/agent-topology/issues/124)
- Amends: [ADR 0009](0009-numeric-canonical-form.md)

## Context

[ADR 0009](0009-numeric-canonical-form.md) picked the canonical byte spelling
for a JSON number and, alongside it, a domain boundary: a bare JSON integer
literal is in-domain only up to magnitude `2^53`; beyond that,
`canonicalize_document` / `canonicalizeDocument` must reject it outright,
because "Python could hold the exact value and TypeScript structurally
cannot." That boundary was enforced only in Python
([`_canonical.py`](../../packages/python/spec/src/agent_topology/spec/_canonical.py)),
keyed on the runtime type `json.loads` produces: a JSON integer literal
decodes to Python `int`, a literal with a `.` or exponent decodes to `float`,
and only the `int` case carried the magnitude check.

Issue #124, found during the pre-#105 review of `1d81f52`, shows this
boundary is not closed under this module's own canonical JSON output — the
same defect ADR 0009 itself exists to close, reintroduced one level up:

1. ADR 0009's own byte oracle requires `1e20` (a `float`, always in-domain
   under the "finite `binary64`" rule) to canonicalize to
   `"100000000000000000000"` — a bare digit string, indistinguishable in JSON
   text from an integer literal, per the same fixed/exponential spelling rule
   the ADR adopts from ECMA-262 / RFC 8785.
2. Re-parsing that output with `json.loads` decodes it to a Python `int` of
   magnitude `10**20`, well beyond `2^53`.
3. Canonicalizing that reparsed document a second time now hits the
   int-magnitude check and raises, even though the first pass accepted the
   identical logical value and the ADR's own oracle table requires it to.

`canonicalize_document(json.loads(canonical_json(document)))` therefore
raises for an input the same ADR 0009 table lists as in-domain. A domain
boundary keyed on Python's `int`/`float` runtime type cannot be closed under
JSON round-tripping in general, because that type is not preserved by the
type's own canonical spelling: any whole-valued `float` at or above the
`k ≤ n ≤ 21` fixed-point threshold spells as bare digits and reparses as
`int`.

A second, independent asymmetry follows from the same design. For the raw
extension literal `9007199254740993` (`2^53 + 1`), Python's `json.loads`
preserves it exactly as an `int` and `_canonical.py` rejects it; TypeScript's
`JSON.parse` has no arbitrary-precision integer type, narrows the literal to
the nearest `number` (`9007199254740992`) before `canonicalStringify` ever
sees it, and accepts the narrowed value — object-based APIs cannot recover
the discarded literal shape to reject it after the fact. Published beta.3
candidate documentation ([`CHANGELOG.md`](../../CHANGELOG.md) and
[the beta.3 release notes](../releases/v0.1.0-beta.3.md)) claims "both
packages now reject a bare JSON integer literal beyond magnitude `2^53`,"
which was never true of TypeScript and describes behavior this decision
replaces.

## Decision

### The supported domain is exactly the finite binary64 values, without a
### separate integer-literal magnitude boundary

ADR 0009's opening domain sentence — "the supported numeric domain is exactly
the finite IEEE 754 `binary64` values" — stands as written. This decision
strikes the integer-literal carve-out that followed it (the `2^53` rejection
clause) and replaces it with narrowing:

A JSON integer literal beyond magnitude `2^53` is in-domain. Python's
`canonicalize_document` narrows it to its nearest binary64 double —
`float(value)`, the same correctly-rounded, round-half-to-even conversion
`JSON.parse` already performs in TypeScript before `canonicalizeDocument`
receives it — rather than rejecting it. Every number in the canonicalization
pipeline, whether it began as a Python `int` or `float`, is therefore a
`float` by the time formatting runs; `_format_number` no longer has a
separate `int` code path, because the value it receives is always already a
double.

This closes the round trip: `1e20` canonicalizes to
`"100000000000000000000"` on every pass, whether the input is the original
`float` or a reparsed `int` of the same magnitude, because both narrow to the
identical double before formatting. It also removes the cross-language
asymmetry: `9007199254740993` now canonicalizes to `9007199254740992` in
both languages, deterministically, because both perform the identical
correctly-rounded decimal-to-double conversion for the same exact
mathematical value.

Only genuinely non-finite results are rejected: `NaN`, `±Infinity` (unchanged
from ADR 0009), and an integer literal so large that converting it to a
double overflows rather than rounds (Python's `float()` raises `OverflowError`
for a magnitude beyond `binary64`'s finite range; that is mapped to the same
"Out of range values are not JSON compliant" rejection path as the existing
non-finite check, per ADR 0009's implementation criteria — not a new,
differently shaped error).

### Precision-loss guarantee

An integer literal whose magnitude exceeds `2^53` is not guaranteed to
canonicalize to its exact original value. It canonicalizes to the nearest
binary64 double, identically in both languages. This is a documented,
deterministic narrowing, not an approximation that differs by
implementation: the same literal produces the same canonical bytes from
`agent_topology.spec` and `@agent-topology/spec` in every case, matching the
result either runtime's own `JSON.parse` would already produce. A consumer
that needs to preserve an integer's exact value beyond `2^53` must encode it
as a string in its `x-*` extension; the numeric domain does not offer
arbitrary-precision round-tripping and never did for TypeScript.

### No raw-token validation boundary

Neither public API validates the shape of the original JSON text token
(integer literal versus exponent literal versus decimal literal). TypeScript's
`canonicalizeDocument` / `canonicalStringify` accept only already-parsed
`TopologyDocument` values; `JSON.parse` has already discarded the literal
shape before either function can see it, so no check in `canonical.ts` can
ever recover or enforce it. Python's `canonicalize_document` / `canonical_json`
accept already-parsed `Mapping` values too — not raw JSON text — and, as
Context above shows, cannot use its own `int`/`float` runtime-type distinction
as a stable proxy for the original literal shape, because that distinction is
not preserved across the module's own canonical output. This decision does
not add a raw-token validation boundary to either API; it removes the one
Python had, because it was unenforceable consistently and not closed under
this module's own output.

### Compatibility with beta.3 and ADR 0009

`topologyVersion` stays `"0.1"`; `structureHash.algorithmVersion` stays
`"1"`. Both of ADR 0009's independent reasons for keeping numeric spelling
out of the version-1 hash projection — no core field is numeric, and
extensions are wholly excluded from the projection regardless of type — are
unaffected by this decision; neither depended on the integer-literal
boundary being struck here.

This decision does not reopen ADR 0009's byte-spelling algorithm, its
hash-exclusion reasoning, or its beta.2/beta.3 compatibility notes; those
stand as accepted. It amends exactly the integer-literal domain-boundary
clause under ADR 0009's "Supported numeric domain and its error behavior"
heading, superseding "beyond that ... `canonicalize_document` /
`canonicalizeDocument` must reject such a value outright ... rather than
silently narrowing it to the nearest double" with the narrowing rule above.
[ADR 0009](0009-numeric-canonical-form.md)'s own text is left unedited per
this repository's rule against rewriting an accepted decision's rationale; it
carries a pointer to this ADR instead.

## Consequences

- [`_canonical.py`](../../packages/python/spec/src/agent_topology/spec/_canonical.py)
  narrows every JSON integer literal to a double in `_ordered` instead of
  rejecting magnitudes beyond `2^53`; `_format_number` drops its `int` code
  path since it now only ever receives `float` values.
  [`canonical.ts`](../../packages/typescript/spec/src/canonical.ts) is
  behaviorally unchanged — it already narrowed via `JSON.parse` and never
  enforced the struck boundary — and its comment explaining the prior
  Python-only enforcement is corrected to describe the current, symmetric
  policy.
- [`0009-implementation-criteria.md`](0009-implementation-criteria.md)'s byte
  oracle table is corrected: the `9007199254740993` row moves from "rejected"
  to "narrows to `9007199254740992`," and gains negative-magnitude `2^53`
  boundary neighbors and explicit round-trip-idempotence coverage.
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) and the
  [0.1 contract](../0.1-contract.md) drop the "integer literals bounded by
  `2^53`" / "canonicalization rejects it explicitly rather than silently
  narrowing it" wording in favor of the narrowing rule above.
- [`CHANGELOG.md`](../../CHANGELOG.md) and the
  [beta.3 release notes](../releases/v0.1.0-beta.3.md) are
  corrected: they claimed both packages reject a bare integer literal beyond
  `2^53`, which was never true of TypeScript's actual behavior.
- The maintained Python canonical suite
  (`packages/python/spec/tests/test_canonical.py`) and the TypeScript
  cross-language contract suite
  (`packages/typescript/spec/tests/contract.test.mjs`) restore `1e20` to
  cross-language byte-parity coverage (previously filtered out as a harness
  artifact) and add a true serialize → parse → canonicalize idempotence
  regression, distinct from the existing same-object idempotence test.
- `structureHash` and every existing fixture hash are unaffected: no core
  field is numeric, and the version-1 hash projection excludes extensions
  regardless of type, exactly as ADR 0009 established.

## What we are explicitly not doing

- **Reopening ADR 0009's byte-spelling algorithm or its hash-boundary
  reasoning.** Both stand as accepted; only the integer-literal domain
  boundary changes.
- **Promising arbitrary-precision integer round-tripping.** The domain is
  exactly the finite binary64 values; a consumer needing exact big-integer
  semantics must use a string encoding, not a JSON number.
- **Adding a raw-token or pre-parse validation layer to either public API.**
  Both APIs operate on already-parsed values only; this decision states that
  explicitly rather than leaving it implicit.
- **Changing `topologyVersion` or `structureHash.algorithmVersion`.** Neither
  of ADR 0009's independent reasons for excluding numeric spelling from the
  hash depended on the boundary struck here.
- **Handing #105 anything beyond the corrected policy and byte oracle.**
  Artifact-bound verification against that oracle remains
  [#105](https://github.com/agent-topology/agent-topology/issues/105)'s job.
