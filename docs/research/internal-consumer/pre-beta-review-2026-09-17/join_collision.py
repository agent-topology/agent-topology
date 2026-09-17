"""Minimum legal-node-name join collision; no workflow invocation."""

import json
import operator
from typing import Annotated, TypedDict

from agent_topology.langgraph import describe
from agent_topology.spec import validate_document
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    values: Annotated[list[str], operator.add]


for label, sources in [
    ("reversed-sources", [["a", "b"], ["b", "a"]]),
    ("delimiter", [["a+b", "c"], ["a", "b+c"]]),
]:
    builder = StateGraph(State)
    for name in sorted({name for group in sources for name in group} | {"sink"}):
        builder.add_node(name, lambda state: {"values": []})
        if name != "sink":
            builder.add_edge(START, name)
    for group in sources:
        builder.add_edge(group, "sink")
    builder.add_edge("sink", END)
    compiled = builder.compile()
    try:
        document = describe(compiled, strict=True)
        print(
            json.dumps(
                {
                    "case": label,
                    "joins": document["graphs"][0]["structure"]["joins"],
                    "errors": validate_document(document),
                }
            )
        )
    except Exception as error:
        print(
            json.dumps(
                {
                    "case": label,
                    "exception": type(error).__name__,
                    "message": str(error),
                }
            )
        )
