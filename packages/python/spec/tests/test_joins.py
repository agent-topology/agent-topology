import json
from copy import deepcopy
from pathlib import Path

import pytest
from agent_topology.spec import derived_join_edges, validate_document

ROOT = Path(__file__).resolve().parents[4]
CASES = json.loads((ROOT / "spec/derived-join-edges-cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_shared_join_connections(case):
    document = json.loads(
        (ROOT / "conformance/fixtures/linear-flow/expected.json").read_text()
    )
    structure = deepcopy(case["structure"])
    document["graphs"][0]["structure"] = structure
    assert validate_document(document) == []
    original = deepcopy(structure)
    links = derived_join_edges(structure)
    assert links == case["expected"]
    assert structure == original
    again = derived_join_edges(structure)
    assert again is not links
    assert all(a is not b for a, b in zip(links, again))
    if links:
        links[0]["source"] = "changed"
        assert again == case["expected"]
        assert structure == original
    structure["joins"].reverse()
    structure["nodes"].reverse()
    structure["edges"].reverse()
    for join in structure["joins"]:
        join["sources"].reverse()
    reordered = deepcopy(structure)
    assert derived_join_edges(structure) == case["expected"]
    assert structure == reordered
