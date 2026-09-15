# Python quickstart

See the [beta.1 to beta.2 upgrade guide](../guides/upgrading-beta.2.md) for beta.2
package selections, hash baselines, and expanded-subgraph migration, and the
[beta.2 to beta.3 upgrade guide](../guides/upgrading-beta.3.md) for the
current published release, and the
[beta.3 to beta.4 upgrade guide](../guides/upgrading-beta.4.md) for the
current, unpublished candidate.

[Documentation home](../README.md) · [Compatibility](../reference/compatibility.md)

Create a small workflow and export its topology. This example needs Python
3.11–3.14 and no model, network service, or API key.

## Install

In a new directory, create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "agent-topology-langgraph==0.1.0b3"
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead.
The producer installs its compatible `agent-topology-spec` and LangGraph dependencies
and provides the `agt` command.

## Define a compiled graph

Save this as `graph.py`:

```python
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agent_topology.langgraph import describe
from agent_topology.spec import canonical_json


class State(TypedDict):
    message: str


def greet(state: State) -> dict[str, str]:
    return {"message": f"Hello, {state['message']}!"}


builder = StateGraph(State)
builder.add_node("greet", greet)
builder.add_edge(START, "greet")
builder.add_edge("greet", END)
graph = builder.compile()

if __name__ == "__main__":
    print(canonical_json(describe(graph)))
```

The graph is compiled, but `greet` is never called during extraction.

## Export and inspect

```bash
agt describe graph.py:graph --out topology.json
python -m json.tool topology.json
```

The target consists of the Python filename and its module-level object name,
separated by `:`. You can also use `python graph.py > topology.json` to exercise
the Python API directly.

The output contains a graph with ID `main`, nodes `__start__`, `greet`, and
`__end__`, and two direct edges. `completeness.status` is `complete` and
`completeness.gaps` is empty. The separate `dynamic-interrupts` producer limitation
is expected: the producer cannot see interrupts raised inside node bodies.

Repeated extraction changes `provenance.generatedAt`. Compare `structureHash` to
detect a structural change; do not compare the whole file for that purpose.

## Require completeness

```bash
agt describe graph.py:graph --out topology.json --strict
```

This example exits successfully. If another graph has an undeclared router target,
the CLI writes its incomplete document and returns status `6`. In Python, use
`describe(graph, strict=True)` and catch `IncompleteTopologyError`; its `document`
attribute contains the result.

Importing `graph.py` runs its module-level statements. Only inspect trusted Python
files, and place graph execution under an `if __name__ == "__main__"` guard or in
a separate entry point. The CLI does not invoke the graph itself.

Next: [understand the document](../guides/concepts.md),
[validate it as a consumer](../guides/consuming-documents.md), or
[look up CLI exit codes](../reference/cli.md).
