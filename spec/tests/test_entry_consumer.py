"""Framework-free consumer examples; authored cases are not producer fixtures."""

import copy
import json
import runpy
from pathlib import Path

from agent_topology.spec import (
    canonical_json,
    compute_structure_hash,
    validate_document,
)

ROOT = Path(__file__).resolve().parents[2]
KEY = "x-topology-interpretation"
ORACLE = runpy.run_path(str(ROOT / "spec/tests/test_interpretation_examples.py"))[
    "interpretation_status"
]
CASES = {
    case["name"]: case["document"]
    for case in json.loads(
        (ROOT / "spec/experimental/interpretation-cases.json").read_text()
    )
}


def entry_view(document):
    """Example consumer policy, with local no-assertion fallback and no mutation."""
    assert not validate_document(document)
    status = ORACLE(document)
    result = {}
    for graph in document["graphs"]:
        records = (
            {r["nodeId"]: r for r in graph[KEY]["nodes"]}
            if status == "valid" and KEY in graph
            else {}
        )
        targets = {c["target"] for c in graph["structure"]["edges"]} | {
            c["target"] for c in graph["structure"]["joins"]
        }
        for node in graph["structure"]["nodes"]:
            fact = records.get(node["id"], {}).get("entry")
            result[(graph["id"], node["id"])] = fact or {
                "observedRoot": node["id"] not in targets,
                "status": "no-assertion",
                "extensionStatus": status,
            }
    return result


def assert_preserved(document):
    before = canonical_json(document)
    view = entry_view(document)
    assert canonical_json(document) == before
    stripped = copy.deepcopy(document)
    for graph in stripped["graphs"]:
        graph.pop(KEY, None)
    assert compute_structure_hash(stripped) == compute_structure_hash(document)
    return view


def test_disconnected_candidate_is_locally_unknown_even_when_complete():
    document = CASES["disconnected-candidate-with-complete-core"]
    assert document["completeness"] == {"status": "complete", "gaps": []}
    view = assert_preserved(document)
    assert view[("main", "start")]["value"] == "confirmed"
    assert view[("main", "target")] == {
        "status": "unknown",
        "observedRoot": True,
        "reason": "entry-not-established",
    }


def test_join_and_cycle_do_not_imply_negative_entry():
    joined = assert_preserved(CASES["join-target-not-root"])[("main", "joined")]
    assert joined["observedRoot"] is False
    assert joined["status"] == "unknown"
    cycle = CASES["confirmed-entry-with-incoming-cycle"]
    assert cycle["graphs"][0]["structure"]["entryNodeIds"] == []
    entry = assert_preserved(cycle)[("main", "start")]
    assert entry["observedRoot"] is False
    assert entry["value"] == "confirmed"


def test_legacy_invalid_unsupported_and_missing_are_not_negative():
    for name, status in [
        ("legacy-absent", "absent"),
        ("unsupported-revision", "unsupported"),
        ("wrong-observed-root", "invalid"),
    ]:
        facts = assert_preserved(CASES[name]).values()
        assert all(f["status"] == "no-assertion" for f in facts)
        assert all(f["extensionStatus"] == status for f in facts)
    document = copy.deepcopy(CASES["disconnected-candidate-with-complete-core"])
    records = document["graphs"][0][KEY]["nodes"]
    records[:] = [r for r in records if r["nodeId"] != "target"]
    assert assert_preserved(document)[("main", "target")]["status"] == "no-assertion"
    del records[0]["entry"]  # A remaining sentinel fact is not an entry assertion.
    assert assert_preserved(document)[("main", "start")]["status"] == "no-assertion"
