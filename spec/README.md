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

## Canonical output and structure hash

Algorithm version `1` sorts graphs, nodes, edges, joins, join sources, entry and
exit node identifiers, and interrupt locations before output and hashing. JSON
object keys are sorted and canonical output uses UTF-8 JSON without insignificant
whitespace. Arrays inside extensions and descriptive fields keep their declared
order because the core contract does not assign them set semantics.

The version `1` structure hash is SHA-256 over graph identifiers and these core
structural properties:

- node `id`, `type`, `subgraphId`, and `interrupts`;
- edge `id`, `source`, `target`, and `kind`;
- join `id`, `sources`, and `target`; and
- `entryNodeIds` and `exitNodeIds`.

It excludes graph names, provenance, producer limitations, completeness gaps,
extensions, labels, descriptive metadata, and the document's existing hash. A
multi-source join is hashed in the `joins` collection, so it cannot collapse to
the same input as separate incoming edges.

Install the Python contract utilities independently of any producer:

```bash
python3 -m pip install agent-topology-spec
```

The native namespace import exposes schema loading, validation, canonicalisation,
and hashing without importing or installing LangGraph:

```python
from agent_topology.spec import load_schema, validate_document

schema = load_schema()
errors = validate_document(document)
```

The package also exposes `canonicalize_document`, `canonical_json`,
`compute_structure_hash`, and `finalize_document`. `finalize_document` computes the
hash and returns the canonical output without mutating its input. The distribution
embeds the root `agent-topology.schema.json` at build time; that root file remains the
single checked-in schema authority.

Changing collection semantics or the set of hashed properties requires a new
algorithm version. Add a separate projection for that version, retain the old
projection while transition output is needed, update the schema's supported
`algorithmVersion`, and select the new version explicitly. Format and package
versions do not change implicitly as part of that transition.

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
