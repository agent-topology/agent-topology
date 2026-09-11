# agent-topology-spec

Validate, canonicalize, and hash agent-topology JSON documents in Python 3.11–3.14.
This package has no framework dependency and does not install a CLI.

```bash
python -m pip install "agent-topology-spec==0.1.0b1"
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
