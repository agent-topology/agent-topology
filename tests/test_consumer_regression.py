"""F1–F6 integration: real producers -> wire JSON -> independent spec consumers.

Run explicitly after building both TypeScript packages. No renderer or Airflow.
"""

import copy
import json
import runpy
import subprocess
from pathlib import Path

import pytest
from agent_topology.spec import (
    canonical_json,
    compute_structure_hash,
    derived_join_edges,
    validate_document,
)

ROOT = Path(__file__).resolve().parents[1]
KEY = "x-topology-interpretation"
interpretation_status = runpy.run_path(
    str(ROOT / "spec/tests/test_interpretation_examples.py")
)["interpretation_status"]
EXPECTED = json.loads((ROOT / "conformance/consumer/expected.json").read_text())


def run_json(*command):
    result = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def produced(tmp_path_factory):
    documents = {
        "python": run_json(
            "uv",
            "run",
            "--project",
            "packages/python/langgraph",
            "python",
            "conformance/consumer/generate.py",
        ),
        "typescript": run_json(
            "node", "packages/typescript/langgraph/tests/consumer-fixtures.mjs"
        ),
    }
    capture = tmp_path_factory.mktemp("producer-captures")
    for language, cases in documents.items():
        (capture / f"{language}.json").write_text(json.dumps(cases, indent=2) + "\n")
        assert set(cases) == set(EXPECTED), language
    return documents


def fact_meaning(fact):
    if fact["status"] == "unknown":
        return ["unknown", fact["reason"]]
    assert fact["evidence"]["source"]
    return ["known", fact["value"], fact["evidence"]["kind"]]


def semantic_records(document):
    records = copy.deepcopy(document["graphs"][0][KEY]["nodes"])
    for record in records:
        for name, fact in record.items():
            if name != "nodeId" and "evidence" in fact:
                # ADR 0008 allows language-specific source locators, not meanings.
                del fact["evidence"]["source"]
    return records


@pytest.mark.parametrize("name", EXPECTED)
def test_producer_meaning_and_order(produced, name):
    expected = EXPECTED[name]
    for language, documents in produced.items():
        document, reversed_document = documents[name]
        assert not validate_document(document), language
        assert interpretation_status(document) == "valid"
        assert document["topologyVersion"] == "0.1"
        assert document["structureHash"]["algorithmVersion"] == "1"
        # Normalize only the clock, preserving all metadata and evidence locators.
        reversed_document = copy.deepcopy(reversed_document)
        reversed_document["provenance"]["generatedAt"] = document["provenance"][
            "generatedAt"
        ]
        assert canonical_json(document) == canonical_json(reversed_document)
        graph = document["graphs"][0]
        structure = graph["structure"]
        records = {r["nodeId"]: r for r in graph[KEY]["nodes"]}
        assert list(records) == sorted(records)
        assert set(records) == {n["id"] for n in structure["nodes"]}
        assert graph[KEY]["traversalDepth"] == 0
        assert {
            n: fact_meaning(r["branch"]) for n, r in records.items() if "branch" in r
        } == expected["branches"]
        for node, fact in expected.get("children", {}).items():
            assert fact_meaning(records[node]["subgraph"]) == fact
        assert structure["entryNodeIds"] == expected["roots"]
        assert [
            n for n, r in records.items() if r["entry"]["observedRoot"]
        ] == expected["roots"]
        for node, record in records.items():
            entry = record["entry"]
            if node in {"__start__", "__end__"}:
                assert fact_meaning(record["sentinel"]) == [
                    "known",
                    "start" if node == "__start__" else "end",
                    "framework-sentinel",
                ]
                assert fact_meaning(entry) == [
                    "known",
                    "confirmed" if node == "__start__" else "not-entry",
                    "framework-entry",
                ]
            else:
                assert fact_meaning(record["sentinel"]) == [
                    "known",
                    "ordinary",
                    "ordinary-node",
                ]
                assert fact_meaning(entry) == ["unknown", "entry-not-established"]
        gaps = document["completeness"]["gaps"]
        assert [[g["code"], g["element"]["id"]] for g in gaps] == expected.get(
            "gaps", []
        )
        assert all(
            g["element"]["graphId"] == graph["id"] and g["element"]["kind"] == "node"
            for g in gaps
        )
        assert document["completeness"]["status"] == (
            "incomplete" if gaps else "complete"
        )
        before = canonical_json(document)
        links = derived_join_edges(structure)
        assert [[link["source"], link["target"]] for link in links] == expected.get(
            "joinConnections", []
        )
        assert links == sorted(links, key=lambda link: (link["joinId"], link["source"]))
        for link in links:
            join = next(j for j in structure["joins"] if j["id"] == link["joinId"])
            assert (
                link["source"] in join["sources"] and link["target"] == join["target"]
            )
            assert not any(
                e["source"] == link["source"] and e["target"] == link["target"]
                for e in structure["edges"]
            )
        if links:
            links[0]["source"] = "consumer-local-edit"
        assert canonical_json(document) == before
    assert semantic_records(produced["python"][name][0]) == semantic_records(
        produced["typescript"][name][0]
    )
    assert (
        produced["python"][name][0]["structureHash"]
        == produced["typescript"][name][0]["structureHash"]
    )


def test_same_shape_is_not_same_metadata(produced):
    for documents in produced.values():
        ordinary, child = (documents[name][0] for name in ("ordinary", "child"))
        assert ordinary["structureHash"] == child["structureHash"]
        assert ordinary["graphs"][0][KEY] != child["graphs"][0][KEY]
        single, multiple = (documents[name][0] for name in ("single", "list"))
        assert single["structureHash"] == multiple["structureHash"]
        assert semantic_records(single) == semantic_records(multiple)
        assert (
            documents["join"][0]["structureHash"]
            != documents["independent"][0]["structureHash"]
        )


def test_wire_consumption_legacy_and_untrusted_extensions(produced, tmp_path):
    documents = []
    statuses = []
    for producer in produced.values():
        for pair in producer.values():
            original = pair[0]
            for mode in ("valid", "absent", "unsupported", "invalid"):
                document = copy.deepcopy(original)
                graph = document["graphs"][0]
                if mode == "absent":
                    del graph[KEY]
                elif mode == "unsupported":
                    graph[KEY]["version"] = "future"
                elif mode == "invalid":
                    graph[KEY]["nodes"][0]["nodeId"] = "not-a-visible-node"
                assert not validate_document(document)
                assert compute_structure_hash(document) == original["structureHash"]
                assert graph["structure"] == original["graphs"][0]["structure"]
                assert graph["x-langgraph"] == original["graphs"][0]["x-langgraph"]
                assert document["completeness"] == original["completeness"]
                assert (
                    document["producerLimitations"] == original["producerLimitations"]
                )
                # Untrusted facts authorize no hiding or entry promotion.
                trusted = (
                    graph[KEY]["nodes"]
                    if interpretation_status(document) == "valid"
                    else []
                )
                hidden = [
                    r["nodeId"]
                    for r in trusted
                    if r.get("sentinel", {}).get("value") in {"start", "end"}
                ]
                assert hidden == (["__end__", "__start__"] if mode == "valid" else [])
                confirmed = [
                    r["nodeId"]
                    for r in trusted
                    if r.get("entry", {}).get("value") == "confirmed"
                ]
                assert confirmed == (["__start__"] if mode == "valid" else [])
                if mode == "absent":
                    graph[KEY] = copy.deepcopy(original["graphs"][0][KEY])
                    assert canonical_json(document) == canonical_json(original)
                    del graph[KEY]
                documents.append(document)
                statuses.append(mode)
    # Immutable, actual npm beta.2 capture from #95; never fabricate legacy output
    # by relabeling the current producer or overwriting historical evidence.
    legacy = json.loads(
        (ROOT / "docs/research/f1-f6-reproduction/results/beta.2.json").read_text()
    )["documents"]
    documents.extend(legacy.values())
    statuses.extend(["absent"] * len(legacy))
    path = tmp_path / "consumer-documents.json"
    path.write_text(json.dumps(documents))
    results = run_json(
        "node", "packages/typescript/spec/tests/consumer-fixtures.mjs", str(path)
    )
    assert len(results) == len(documents)
    for document, result, status in zip(documents, results, statuses, strict=True):
        assert not validate_document(document)
        assert interpretation_status(document) == result["status"] == status
        assert canonical_json(document) == result["canonical"]
        assert (
            compute_structure_hash(document)
            == result["hash"]
            == document["structureHash"]
        )
        assert [
            derived_join_edges(g["structure"]) for g in document["graphs"]
        ] == result["links"]
