#!/usr/bin/env python3
"""Exercise the installed LangGraph producer API and ``agt`` entry point."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

import agent_topology.langgraph
import agent_topology.spec
from langgraph.graph import END, START, StateGraph


def _minimal_graph():
    builder = StateGraph(dict)
    builder.add_node("step", lambda state: state)
    builder.add_edge(START, "step")
    builder.add_edge("step", END)
    return builder.compile()


def main() -> None:
    document = agent_topology.langgraph.describe(_minimal_graph())
    assert document["topologyVersion"] == "0.1"
    assert document["provenance"]["producer"]["name"] == "agent-topology-langgraph"

    assert document["provenance"]["producer"]["version"] == version(
        "agent-topology-langgraph"
    )

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        target = temporary / "graph.py"
        output = temporary / "topology.json"
        target.write_text(
            """from langgraph.graph import END, START, StateGraph

builder = StateGraph(dict)
builder.add_node("step", lambda state: state)
builder.add_edge(START, "step")
builder.add_edge("step", END)
graph = builder.compile()
""",
            encoding="utf-8",
        )
        executable = Path(sys.executable).with_name("agt")
        subprocess.run(
            [str(executable), "describe", f"{target}:graph", "--out", str(output)],
            check=True,
        )
        rendered = output.read_text(encoding="utf-8")
        cli_document = json.loads(rendered)
        assert rendered == agent_topology.spec.canonical_json(cli_document) + "\n"
        assert cli_document["provenance"]["producer"]["name"] == (
            "agent-topology-langgraph"
        )


if __name__ == "__main__":
    main()
