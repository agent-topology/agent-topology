"""Verify the six wrapped call sites in channel_concept/channel_production
materialize as real parent/child hierarchy links, not just an updated graph
count, now that campaign-agent adopts `declare_children` (#63) against
agent-topology's #185 implementation.

Adapted from docs/research/internal-consumer/campaign-agent/verify_declared_children.py
for issue #171's qualification: run with the campaign-agent checkout's own
Python environment plus the clean-installed beta.5 candidate wheels
(agent_topology_spec-0.1.0b4, agent_topology_langgraph-0.1.0b5) on
sys.path via site-packages -- not the agent-topology source tree -- so this
reproduces #178's pinned consumer acceptance against the qualified
artifacts rather than source. Run with -B, at the commit that merges
milocosmopolitan/campaign-agent#63. Never invokes a workflow.

For each of the six declared relationships this asserts:
- At depth 0 the wrapped node's `x-topology-interpretation` subgraph fact is
  `status: known` with `evidence.kind: declared-child-call` (construction-time
  declaration, not a direct bind).
- At depth 2 the node is materialized (`structure.nodes[].subgraphId` set,
  `graphs[]` gains an entry for it) and that materialized child's node id set
  is identical to the declared child factory's own standalone `describe()`
  output -- proving the link points at the real child, not just incrementing
  a count.
"""

import argparse
import importlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

RELATIONSHIPS = {
    "channel_concept": {
        "prepare_brief": "copy_brief_prepare",
        "draft_copy": "copy_draft",
        "review_copy": "copy_review",
    },
    "channel_production": {
        "revise_copy": "copy_revision",
        "review_copy": "copy_review",
        "prepare_copy_feedback": "copy_feedback_prepare",
    },
}

SENTINELS = {"__start__", "__end__"}


def _compile(name, checkout):
    support = importlib.import_module(f"tests.{name}.support")
    factory = importlib.import_module(f"campaign_agent.{name}").create_graph
    return factory(graph_id=name, policy=support.policy())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    # Deliberately NOT prepending the agent-topology source tree: this
    # adapted copy verifies the clean-installed qualification-candidate
    # wheels (agent_topology_spec-0.1.0b4, agent_topology_langgraph-0.1.0b5)
    # from the active venv's site-packages, not the local source tree.
    sys.path[:0] = [
        str(args.checkout / "src"),
        str(args.checkout),
    ]
    from agent_topology.langgraph import describe
    from agent_topology.spec import validate_document
    from langgraph.graph.state import CompiledStateGraph

    with (
        patch.object(
            CompiledStateGraph, "invoke", side_effect=AssertionError("workflow invoked")
        ),
        patch.object(
            CompiledStateGraph,
            "ainvoke",
            side_effect=AssertionError("workflow invoked"),
        ),
    ):
        child_names = sorted(
            {child for m in RELATIONSHIPS.values() for child in m.values()}
        )
        standalone_node_ids = {}
        for child_name in child_names:
            child_graph = _compile(child_name, args.checkout)
            child_doc = describe(child_graph, graph_id=child_name, depth=0, strict=True)
            assert validate_document(child_doc) == []
            child_structure = next(
                g for g in child_doc["graphs"] if g["id"] == child_name
            )["structure"]
            standalone_node_ids[child_name] = frozenset(
                n["id"] for n in child_structure["nodes"] if n["id"] not in SENTINELS
            )

        links = []
        for parent_name, mapping in RELATIONSHIPS.items():
            parent_graph = _compile(parent_name, args.checkout)

            depth0 = describe(parent_graph, graph_id=parent_name, depth=0, strict=True)
            assert validate_document(depth0) == []
            depth0_facts = {
                n["nodeId"]: n["subgraph"]
                for n in next(g for g in depth0["graphs"] if g["id"] == parent_name)[
                    "x-topology-interpretation"
                ]["nodes"]
                if "subgraph" in n
            }

            depth2 = describe(parent_graph, graph_id=parent_name, depth=2, strict=True)
            assert validate_document(depth2) == []
            depth2_record = next(g for g in depth2["graphs"] if g["id"] == parent_name)
            depth2_nodes_by_id = {
                n["id"]: n for n in depth2_record["structure"]["nodes"]
            }
            depth2_graphs_by_id = {g["id"]: g for g in depth2["graphs"]}

            for node_id, child_name in mapping.items():
                fact = depth0_facts[node_id]
                assert fact["status"] == "known", (parent_name, node_id, fact)
                assert fact["evidence"]["kind"] == "declared-child-call", (
                    parent_name,
                    node_id,
                    fact,
                )

                subgraph_id = depth2_nodes_by_id[node_id].get("subgraphId")
                assert subgraph_id == f"{parent_name}:{node_id}", (
                    parent_name,
                    node_id,
                    subgraph_id,
                )
                materialized = depth2_graphs_by_id[subgraph_id]["structure"]
                materialized_node_ids = frozenset(
                    n["id"] for n in materialized["nodes"] if n["id"] not in SENTINELS
                )
                matches_standalone = (
                    materialized_node_ids == standalone_node_ids[child_name]
                )
                assert matches_standalone, (parent_name, node_id, child_name)

                links.append(
                    {
                        "parent": parent_name,
                        "nodeId": node_id,
                        "declaredChildGraph": child_name,
                        "depth0Evidence": fact["evidence"],
                        "materializedSubgraphId": subgraph_id,
                        "materializedNodeCount": len(materialized_node_ids),
                        "matchesStandaloneFactory": matches_standalone,
                    }
                )

    print(
        json.dumps(
            {
                "consumer": "campaign-agent",
                "head": subprocess.check_output(
                    ["git", "-C", str(args.checkout), "rev-parse", "HEAD"], text=True
                ).strip(),
                "langgraph": importlib.metadata.version("langgraph"),
                "producerSource": str(
                    Path(sys.modules["agent_topology.langgraph"].__file__).resolve()
                ),
                "hierarchyLinks": links,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
