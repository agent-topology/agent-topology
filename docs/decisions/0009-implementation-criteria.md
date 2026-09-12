# ADR 0009 implementation criteria

These requirements are part of [accepted ADR 0009](0009-numeric-canonical-form.md).
They give [#118](https://github.com/agent-topology/agent-topology/issues/118)
the literal byte oracle and regression matrix; they do not implement it.

## Shared gate for #118

- Implement the spelling rule and the `2^53` integer-magnitude domain
  boundary exactly as ADR 0009 states them, in both
  [`_canonical.py`](../../packages/python/spec/src/agent_topology/spec/_canonical.py)
  and [`canonical.ts`](../../packages/typescript/spec/src/canonical.ts). Do
  not special-case zero alone, and do not let either runtime's existing
  default number formatting become the oracle by construction.
- Reuse each language's existing non-finite-number rejection path for the new
  out-of-domain-integer rejection; do not add a second, differently shaped
  error for the same "not a supported number" condition.
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
| In-domain integer boundary | `9007199254740992` (`2^53`) | `9007199254740992` | Last magnitude that round-trips exactly through a `binary64` double in both languages. |
| Out-of-domain integer | `9007199254740993` (`2^53 + 1`) as a bare JSON integer literal | rejected | Python could hold this exactly as `int`; TypeScript cannot as `number`. Canonicalization must raise/throw, never round. |
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
