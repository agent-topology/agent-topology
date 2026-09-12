# ADR 0009 implementation criteria

These requirements are part of [accepted ADR 0009](0009-numeric-canonical-form.md),
amended by [ADR 0010](0010-numeric-domain-parsed-value-narrowing.md). They
give [#118](https://github.com/agent-topology/agent-topology/issues/118) and
[#124](https://github.com/agent-topology/agent-topology/issues/124) the
literal byte oracle and regression matrix; they do not implement it.

**Amendment (ADR 0010, #124):** the byte-spelling rule below is unchanged.
The integer-magnitude domain boundary is not a rejection anymore — an
integer literal beyond `2^53` narrows to the nearest binary64 double in both
languages, exactly as `JSON.parse` already narrows it in TypeScript. Only
`NaN`, `±Infinity`, and a magnitude too large for any finite double to
represent (a Python `OverflowError` converting to `float`) are rejected.

## Shared gate for #118 / #124

- Implement the spelling rule exactly as ADR 0009 states it, and the
  narrowing rule exactly as ADR 0010 states it, in both
  [`_canonical.py`](../../packages/python/spec/src/agent_topology/spec/_canonical.py)
  and [`canonical.ts`](../../packages/typescript/spec/src/canonical.ts). Do
  not special-case zero alone, and do not let either runtime's existing
  default number formatting become the oracle by construction.
- Reuse each language's existing non-finite-number rejection path for the
  astronomically-out-of-range case; do not add a second, differently shaped
  error for the same "not a supported number" condition.
- Canonicalization must be idempotent under a full serialize → JSON parse →
  canonicalize round trip, not merely across two calls on the same in-memory
  object — the #124 regression is specifically the gap between those two.
- `structureHash.algorithmVersion` stays `"1"`; `topologyVersion` stays
  `"0.1"`. No fixture, hash test, or version constant changes.
- Extension array order, input non-mutation, idempotence, and
  structural-order invariance are unaffected by this change and must keep
  passing unchanged.

## Byte oracle

Add these to the maintained Python canonical suite
(`packages/python/spec/tests/test_canonical.py`) and the TypeScript
cross-language contract suite
(`packages/typescript/spec/tests/contract.test.mjs`), covering each numeric
case both as a document-level extension value and nested inside an extension
object/array, per #118's own done-when list — the projection and spelling
rule are structure-agnostic, but the regression should prove it, not assume
it.

| Case | Value(s) | Canonical bytes | Notes |
| --- | --- | --- | --- |
| F8/E1 retained candidate | `"x-e1": 0.0` (Python input) / `"x-e1": 0` (TypeScript input) | `"x-e1":0` | Use the retained 479-byte minimized input verbatim; do not rebuild an equivalent one. |
| Signed zero | `0.0`, `-0.0` | `0` | Sign is not observable in canonical bytes. |
| Integral float | `1.0` | `1` | No trailing `.0`. |
| Ordinary fraction | `0.5` | `0.5` | |
| Small-integer boundary | `-100`, `100` | `-100`, `100` | E1's declared integer-domain edges. |
| Exponent lower threshold | `1e-6`, `1e-7` | `0.000001`, `1e-7` | Adjacent pair; proves the fixed/exponential switch lands between them, not just that each value looks right in isolation. |
| Exponent upper threshold | `1e20`, `1e21` | `100000000000000000000`, `1e+21` | Adjacent pair; same reason at the top end. |
| In-domain integer boundary and safe neighbors | `9007199254740991` (`2^53 - 1`), `9007199254740992` (`2^53`), `-9007199254740991`, `-9007199254740992` | unchanged | Last adjacent magnitudes that round-trip exactly through a `binary64` double in both languages, on both signs. |
| Narrowed integer boundary (ADR 0010) | `9007199254740993` (`2^53 + 1`), `-9007199254740993` as bare JSON integer literals | `9007199254740992`, `-9007199254740992` | Not rejected: narrows to the nearest double (round-half-to-even), identically in both languages. Was previously specified as rejected; ADR 0010 corrects this. |
| Astronomically out of range | `10**400` as a bare JSON integer literal | rejected | No finite `binary64` double can represent this magnitude at all — distinct from the merely-imprecise `2^53`-neighborhood case above, which is in-domain. |
| Non-finite (unchanged) | `NaN`, `Infinity`, `-Infinity` | rejected | Existing behavior; confirm it is unchanged, not re-implemented. |

## Verification

- Reproduce the retained F8/E1 minimized input through both public spec APIs
  and record acceptance, canonical bytes, and the full computed hash tuple
  separately, exactly as #118 requires.
- Confirm the stored `structureHash` value for every existing fixture is
  byte-identical before and after the change.
- Confirm the `verify.py --pair` differential comparator semantics against
  `observations/E1/controls/altered-pair.json` are unaffected — this ADR does
  not touch hash comparison, only full-document canonical bytes.
- Confirm `canonicalize(json.loads(canonicalize(document)))` /
  `canonicalizeDocument(JSON.parse(canonicalStringify(document)))` produce
  byte-identical output to the first pass, for every row above, in both
  languages (ADR 0010, #124) — not just two calls on the same in-memory
  object.
