# agent-topology-langgraph

Describe a compiled Python LangGraph workflow as an agent-topology JSON document.
Supports Python 3.11–3.14 and LangGraph 1.2.10–1.2.11. Untested framework versions
are refused before inspection.

```bash
python -m pip install "agent-topology-langgraph==0.1.0b4"
agt describe path/to/graph.py:graph --out topology.json
```

The target is a Python file and the name of its compiled graph object. Importing
the file executes its module-level statements; extraction does not invoke the
graph. Inspect trusted targets only.

```python
from agent_topology.langgraph import IncompleteTopologyError, describe

# compiled_graph is the result of your application's StateGraph.compile().
try:
    document = describe(compiled_graph, graph_id="invoice-intake", strict=True)
except IncompleteTopologyError as error:
    document = error.document
    print(document["completeness"]["gaps"])
```

The optional `graph_id` is a non-empty document-local address and defaults to
`main`; choose a distinct stable value before composing several outputs. The CLI
spells it `--graph-id`. The optional `depth` argument defaults to `0`, keeping
subgraphs opaque. Read
both graph-specific gaps and producer-wide limitations. Only gaps fail strict
mode. The CLI's `--strict` option still writes an incomplete document and exits
with status `6`.

Installation includes the specification dependency and the `agt` executable.
The document is a provisional 0.1 contract, not a runtime, viewer, or proof of
policy compliance.

[Python quickstart](https://github.com/agent-topology/agent-topology/blob/main/docs/getting-started/python.md)
· [Documentation](https://github.com/agent-topology/agent-topology/blob/main/docs/README.md)
· [Source and issues](https://github.com/agent-topology/agent-topology)

Licensed under the MIT License; see the included `LICENSE` file.
