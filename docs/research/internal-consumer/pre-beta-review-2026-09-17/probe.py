"""Compile real consumer factories and inspect them; never invoke a workflow.

Run with the consumer checkout's existing Python environment and -B.
The checkout supplies its construction-only test policy (campaign) or dev export
(git). Output summarizes current source behavior, not published-artifact support.
"""

import argparse
import importlib
import importlib.metadata
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("consumer", choices=["campaign-agent", "git-agent"])
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    sys.path[:0] = [
        str(root / "packages/python/spec/src"),
        str(root / "packages/python/langgraph/src"),
        str(args.checkout / "src"),
        str(args.checkout),
    ]
    from agent_topology.langgraph import describe
    from agent_topology.spec import validate_document
    from langgraph.graph.state import CompiledStateGraph

    names = (
        [
            "campaign_contract",
            "channel_concept",
            "channel_production",
            "copy_brief_prepare",
            "copy_draft",
            "copy_feedback_prepare",
            "copy_review",
            "copy_revision",
            "deliverable_report",
            "stakeholder_review",
        ]
        if args.consumer == "campaign-agent"
        else ["issue_resolution"]
    )
    rows = []
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
        for name in names:
            if args.consumer == "campaign-agent":
                support = importlib.import_module(f"tests.{name}.support")
                factory = importlib.import_module(f"campaign_agent.{name}").create_graph
                graph = factory(graph_id=name, policy=support.policy())
            else:
                graph = importlib.import_module("dev.issue_resolution").graph
            expected = Counter((s, t, "direct") for s, t in graph.builder.edges)
            for source, branches in graph.builder.branches.items():
                for branch in branches.values():
                    assert branch.ends is not None
                    expected.update(
                        (source, t, "conditional") for t in branch.ends.values()
                    )
            for source, node in graph.builder.nodes.items():
                expected.update((source, t, "conditional") for t in node.ends)
            for depth in [0, 1, 2]:
                doc = describe(graph, graph_id=name, depth=depth, strict=True)
                assert validate_document(doc) == []
                record = next(g for g in doc["graphs"] if g["id"] == name)
                structure = record["structure"]
                actual = Counter(
                    (e["source"], e["target"], e["kind"]) for e in structure["edges"]
                )
                assert actual == expected
                assert set(graph.builder.nodes) <= {n["id"] for n in structure["nodes"]}
                assert len(structure["joins"]) == len(graph.builder.waiting_edges)
                rows.append(
                    {
                        "graph": name,
                        "depth": depth,
                        "graphs": len(doc["graphs"]),
                        "nodes": len(structure["nodes"]),
                        "edges": sum(actual.values()),
                        "joins": len(structure["joins"]),
                        "completeness": doc["completeness"],
                        "staticInterruptNodes": [
                            n["id"] for n in structure["nodes"] if n.get("interrupts")
                        ],
                        "unknownChildNodes": [
                            n["nodeId"]
                            for n in record["x-topology-interpretation"]["nodes"]
                            if n.get("subgraph", {}).get("status") == "unknown"
                        ],
                    }
                )
    print(
        json.dumps(
            {
                "consumer": args.consumer,
                "head": subprocess.check_output(
                    ["git", "-C", str(args.checkout), "rev-parse", "HEAD"], text=True
                ).strip(),
                "langgraph": importlib.metadata.version("langgraph"),
                "producerSource": str(
                    Path(sys.modules["agent_topology.langgraph"].__file__).resolve()
                ),
                "rows": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
