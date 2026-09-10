# Topology document contract

`agent-topology.schema.json` is the single checked-in authority for the
provisional v0.1 document shape. It uses JSON Schema Draft 2020-12. Unknown core
properties are rejected; extension properties must use a lower-case,
namespaced `x-*` key such as `x-langgraph`.

The core represents ordinary and conditional edges separately from multi-source
joins. Fan-out and loops are expressed by the resulting graph shape rather than
by inferred annotations. Expanded subgraphs are linked from a node with
`subgraphId`; opaque subgraphs need no invented contents. Static interrupt
locations may be recorded on nodes, while framework-only details remain in an
extension.

Producer-wide `producerLimitations` are separate from graph-specific
`completeness.gaps`. Each gap names a graph element, and the validator requires
`completeness.status` to be `complete` exactly when the gap collection is empty.

The three version axes are intentionally independent:

- `topologyVersion` versions the document contract;
- `structureHash.algorithmVersion` versions canonicalisation and hash coverage;
- `provenance.producer.version` is the producing package version.

JSON Schema validates the document shape and extension boundary. The repository
validator additionally checks identifier uniqueness, node/subgraph references,
gap element references, and the completeness invariant:

```bash
python3 -m pip install -r spec/requirements-test.txt
python3 spec/validate.py path/to/document.json
python3 -m unittest discover -s spec/tests -v
```

The examples under `tests/documents` measure schema behavior only. Shared graph
meanings and producer conformance fixtures belong under `conformance/` and are
introduced separately.
