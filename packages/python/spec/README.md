# agent-topology-spec

Validate, canonicalize, and hash agent-topology JSON documents in Python 3.11–3.14.
This package has no framework dependency and does not install a CLI.

```bash
python -m pip install "agent-topology-spec==0.1.0b2"
```

```python
import json
from pathlib import Path

from agent_topology.spec import compute_structure_hash, validate_document

document = json.loads(Path("topology.json").read_text(encoding="utf-8"))
errors = validate_document(document)
if errors:
    raise ValueError("\n".join(errors))
print(compute_structure_hash(document))
print(document["completeness"])
print(document["producerLimitations"])
```

Validation checks schema, references, and completeness; it does not verify the
recorded hash. `canonical_json` serializes canonical JSON; `finalize_document`
recomputes the hash and returns a canonical copy. These utilities do not mutate
their input or validate it automatically.

To derive documents from compiled Python LangGraph graphs, install
`agent-topology-langgraph` instead. Its specification dependency is installed
automatically.

The 0.1 format is provisional. Package versions, document format versions, and
hash algorithm versions are independent.

[Documentation](https://github.com/agent-topology/agent-topology/blob/main/docs/README.md)
· [Consumer guide](https://github.com/agent-topology/agent-topology/blob/main/docs/guides/consuming-documents.md)
· [Source and issues](https://github.com/agent-topology/agent-topology)

Licensed under the MIT License; see the included `LICENSE` file.

## Join connections (beta.3 partial publication)

The beta.3 partial publication exports `derived_join_edges(structure)`; coordinated
beta.2 does not. Wait for the corrected beta.4 release before adopting it from the
current installation path.

```python
from agent_topology.spec import derived_join_edges

# After validate_document(document) succeeds:
links = derived_join_edges(document["graphs"][0]["structure"])
```

The helper returns one fresh `{joinId, source, target}` record per join source,
sorted first by `joinId`, then by `source`, using lexicographic Unicode code point
order (shorter prefixes first, without normalization or locale collation). Empty
joins produce an empty list. Input objects and arrays are not mutated.

Consumers must read both `structure.edges` and `structure.joins`. Derived links
retain their join identity even when endpoints coincide with another join or a
direct edge. They describe the original join's AND convergence: all its sources
are required. They do not imply independent edge execution. Keep them separate
from ordinary edges; no ordinary edge `id` or `kind` is assigned. Validate the
containing document at the input boundary; the helper does not validate again.
