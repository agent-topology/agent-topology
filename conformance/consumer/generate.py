"""Generate fixtures via the public Python producer; never read the oracle."""

import json
from pathlib import Path
from typing import TypedDict

from agent_topology.langgraph import describe
from langgraph.graph import StateGraph


class State(TypedDict):
    value: str


def forbidden(_state):
    raise AssertionError("Extraction executed a user node or router")


def single(_state) -> str:
    forbidden(_state)
    return "left"


def multiple(_state) -> list[str]:
    forbidden(_state)
    return ["left", "right"]


def compile_recipe(recipe, reverse=False):
    def ordered(values):
        return list(reversed(values)) if reverse else values

    builder = StateGraph(State)
    for node in ordered(recipe["nodes"]):
        runnable = (
            compile_recipe(node["child"], reverse) if "child" in node else forbidden
        )
        builder.add_node(node["id"], runnable)
    for source, target in ordered(recipe["edges"]):
        builder.add_edge(source, target)
    for sources, target in ordered(recipe.get("joins", [])):
        builder.add_edge(ordered(sources), target)
    for route in ordered(recipe.get("routes", [])):
        targets = route.get("targets")
        builder.add_conditional_edges(
            route["source"],
            multiple if route["returns"] == "list" else single,
            {target: target for target in ordered(targets)} if targets else None,
        )
    return builder.compile()


if __name__ == "__main__":
    recipes = json.loads(Path(__file__).with_name("recipes.json").read_text())
    print(
        json.dumps(
            {
                name: [
                    describe(compile_recipe(recipe, reverse))
                    for reverse in (False, True)
                ]
                for name, recipe in recipes.items()
            }
        )
    )
