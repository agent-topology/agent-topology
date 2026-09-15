#!/usr/bin/env python3
"""Import-safe compiled-object export recipe: fake policy/ports, tiny fixture
graph, real `agent_topology.langgraph.describe`.

Importing this module (`import recipe`, or letting some other tool's module
scanner load it) has no side effects: no graph is built, no LangGraph object
exists, and nothing is read from the filesystem or network. Every side effect
lives behind `build_compiled_graph` and `main`, which nothing but an explicit
call -- including `python recipe.py` itself -- triggers.

`build_compiled_graph(*, graph_id, policy, ports)` mirrors, without invoking,
the compile-time factory shape already inspected in both consumers this
recipe maps to (see README.md for full permalinks and disposition):

- campaign-agent's `campaign_contract.create_graph(*, graph_id, policy)`
  ("requires policy and uses graph ID as compile name",
  docs/research/internal-consumer/campaign-agent/README.md)
- git-agent's `issue_resolution.create_graph(*, graph_id, policy)`
  ("validates the graph ID and policy and compiles without runtime resource
  access", docs/research/internal-consumer/git-agent/README.md)

`FakePolicy`/`FakePorts` are this recipe's own inert stand-ins -- not
campaign-agent's `CampaignContractPolicy`, git-agent's
`IssueResolutionPolicy`, or any `agent_workflow_core.ports` type. Neither real
consumer's source, model gateway, checkpoint store, or effect port (GitHub,
notifications) is imported, touched, or executed here, and no campaign-agent
or git-agent workflow -- full or partial -- runs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

from agent_topology.langgraph import describe
from agent_topology.spec import canonical_json, validate_document
from langgraph.graph import END, START, StateGraph


@dataclass(frozen=True)
class FakePolicy:
    """Inert stand-in for a consumer policy object. Construction-only: no
    model, credential, or network configuration."""

    max_retries: int = 1


@dataclass(frozen=True)
class FakePorts:
    """Inert stand-in for consumer runtime ports (e.g. a model gateway). Real
    factories receive these per invocation through LangGraph's `context`
    parameter, never at compile time -- `build_compiled_graph` accepts one
    anyway and never reads it, to keep that compile-time absence an explicit,
    checked contract rather than an implicit one."""

    model_gateway: Any = None


def build_compiled_graph(*, graph_id: str, policy: FakePolicy, ports: FakePorts):
    """Compile a two-node fixture graph without touching `policy` or `ports`
    beyond the type check below, matching both inspected factories'
    compile-without-touching-invocation-time-resources contract."""

    if not isinstance(policy, FakePolicy):
        raise TypeError("policy must be a FakePolicy")
    if not isinstance(ports, FakePorts):
        raise TypeError("ports must be a FakePorts")

    def plan(_: dict[str, Any]) -> dict[str, Any]:
        return {}

    def act(_: dict[str, Any]) -> dict[str, Any]:
        return {}

    builder = StateGraph(dict)
    builder.add_node("plan", plan)
    builder.add_node("act", act)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "act")
    builder.add_edge("act", END)
    return builder.compile(name=graph_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graph-id",
        default="fixture-import-safe-export",
        help="value used both as the LangGraph compile name and, explicitly, "
        "as describe()'s document-local graph_id -- two separate identifiers "
        "agent-topology never conflates (see README.md, IC-04)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the document and print a one-line result instead of "
        "the full document",
    )
    args = parser.parse_args(argv)

    graph = build_compiled_graph(
        graph_id=args.graph_id, policy=FakePolicy(), ports=FakePorts()
    )
    document = describe(graph, graph_id=args.graph_id)
    errors = validate_document(document)
    if errors:
        raise SystemExit("recipe produced an invalid document:\n" + "\n".join(errors))
    if document["provenance"]["source"]["kind"] != "compiled-object":
        raise SystemExit(
            "expected provenance.source.kind == 'compiled-object', got "
            f"{document['provenance']['source']['kind']!r}"
        )

    if args.check:
        print(
            "ok: recipe compiled a fixture graph from fake policy/ports and "
            f"produced a valid compiled-object document (graph_id={args.graph_id!r})"
        )
    else:
        print(canonical_json(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
