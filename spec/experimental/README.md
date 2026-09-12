# Experimental interpretation revision 1

[ADR 0008](../../docs/decisions/0008-experimental-consumer-interpretation.md)
owns this contract. These files do not change the core schema, public package
exports, or structure hash algorithm.

- `interpretation-v1.schema.json` validates the graph extension object only.
- `interpretation-cases.json` contains complete **authored contract documents**,
  including known positives, known negatives, unknown, legacy absent,
  unsupported-revision and invalid examples. They are not real producer output.
  Each document has its computed structure hash and a `canonicalSha256` digest
  of its complete canonical UTF-8 serialization, shared across languages.
- `shapeValid` records shape validation only. `extensionStatus` also accounts
  for placement, references, ordering and document-verifiable semantics.
  All examples pass core validation, including invalid extensions.
- `spec/tests/test_interpretation_examples.py` is the reference semantic oracle.
  It does not inspect a framework and cannot prove producer assertions true.
  `packages/typescript/spec/tests/interpretation.test.mjs` independently checks
  core validation, extension shape, canonical digests and hash exclusion.
  T3–T6 must additionally prove real producer evidence and semantic parity using
  the [implementation criteria](../../docs/decisions/0008-implementation-criteria.md).

Run from the repository root:

```bash
rtk uv run --project packages/python/spec --group test python -m pytest spec/tests/test_interpretation_examples.py
rtk npm --prefix packages/typescript/spec run check
```

The minimum ordinary/opaque pair has identical core fields and different
extension content. Both languages verify equal structure hashes and distinct
full-document canonical digests. This is an interpretation-cache boundary,
not a claim that metadata is covered by hash algorithm 1.
