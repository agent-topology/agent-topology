# Conformance fixtures

Each directory under `fixtures/` is one minimum graph used to measure one core
topology behavior. `fixture.json` is language-neutral test input and
`expected.json` is the single checked-in expected topology document. Producer
runners construct native framework objects from the input and compare their
core result with that expected document.

The fixture input is deliberately a small conformance recipe, not a public graph
authoring format or a shared producer API. It supports only the declarations the
current cases need:

- `nodes`, optionally with an inline `subgraph` recipe;
- `directEdges` with one source and target;
- `conditionalRoutes`, whose `targets` are either declared identifiers or
  `null` when destinations cannot be enumerated;
- `joins` with multiple sources and one target; and
- `interruptBefore` and `interruptAfter` node identifiers.

`$start` and `$end` name the framework-independent entry and exit sentinels in
fixture input. Expected documents use the canonical identifiers emitted by the
producer under test.

Conformance compares core graph structure, structure hashes, and graph-specific
completeness. Producer identity, framework version, producer-wide limitations,
descriptive graph names, and all `x-*` extensions are normalized because a
second producer cannot reproduce them. This also excludes LangGraph diagram and
rendering data from comparison, as required by ADR 0004.

The Python LangGraph runner is
`packages/python/langgraph/tests/test_conformance.py`, and the LangGraph.js runner
is `packages/typescript/langgraph/tests/conformance.test.mjs`. Both read these
same files and do not copy or redefine the expected documents.
