from __future__ import annotations

import json
from copy import deepcopy
from decimal import ROUND_FLOOR, DivisionByZero, Inexact, Rounded, localcontext

import pytest
from agent_topology.spec import (
    canonical_json,
    canonicalize_document,
    compute_structure_hash,
    finalize_document,
)


def _document() -> dict:
    return {
        "topologyVersion": "0.1",
        "provenance": {
            "generatedAt": "2026-09-10T19:00:00Z",
            "producer": {"name": "test-producer", "version": "1.0"},
            "framework": {"name": "test-framework", "version": "2.0"},
        },
        "producerLimitations": [],
        "structureHash": {
            "algorithm": "sha256",
            "algorithmVersion": "1",
            "value": "0" * 64,
        },
        "graphs": [
            {
                "id": "main",
                "name": "Example graph",
                "structure": {
                    "nodes": [
                        {"id": "target", "type": "task"},
                        {"id": "b", "interrupts": ["before", "after"]},
                        {"id": "a"},
                    ],
                    "edges": [
                        {
                            "id": "b-target",
                            "source": "b",
                            "target": "target",
                            "kind": "direct",
                        },
                        {
                            "id": "a-target",
                            "source": "a",
                            "target": "target",
                            "kind": "direct",
                        },
                    ],
                    "joins": [
                        {"id": "wait", "sources": ["b", "a"], "target": "target"}
                    ],
                    "entryNodeIds": ["b", "a"],
                    "exitNodeIds": ["target"],
                },
            }
        ],
        "completeness": {"status": "complete", "gaps": []},
    }


def test_declaration_order_does_not_change_canonical_output_or_hash() -> None:
    first = _document()
    reordered = deepcopy(first)
    structure = reordered["graphs"][0]["structure"]
    structure["nodes"].reverse()
    structure["edges"].reverse()
    structure["joins"][0]["sources"].reverse()
    structure["entryNodeIds"].reverse()
    structure["nodes"][1]["interrupts"].reverse()

    original = deepcopy(reordered)
    assert canonical_json(finalize_document(first)) == canonical_json(
        finalize_document(reordered)
    )
    assert compute_structure_hash(first) == compute_structure_hash(reordered)
    assert reordered == original


def test_multi_source_join_differs_from_independent_edges() -> None:
    joined = _document()
    joined["graphs"][0]["structure"]["edges"] = []
    independent = deepcopy(joined)
    independent["graphs"][0]["structure"]["joins"] = []
    independent["graphs"][0]["structure"]["edges"] = [
        {
            "id": f"{source}-target",
            "source": source,
            "target": "target",
            "kind": "direct",
        }
        for source in ("a", "b")
    ]

    assert compute_structure_hash(joined) != compute_structure_hash(independent)


def test_descriptive_metadata_and_extensions_are_not_hashed() -> None:
    first = _document()
    changed = deepcopy(first)
    changed["graphs"][0]["name"] = "A different label"
    changed["provenance"]["generatedAt"] = "2030-01-01T00:00:00Z"
    changed["producerLimitations"] = [
        {"code": "opaque", "message": "Descriptive limitation text."}
    ]
    changed["x-example"] = {"presentation": ["right", "left"]}

    assert compute_structure_hash(first) == compute_structure_hash(changed)


def test_structural_properties_are_hashed() -> None:
    first = _document()
    changed = deepcopy(first)
    changed["graphs"][0]["structure"]["nodes"][0]["type"] = "approval"

    assert compute_structure_hash(first) != compute_structure_hash(changed)


def test_hash_algorithm_version_is_independent_and_explicit() -> None:
    document = _document()
    document["topologyVersion"] = "a-future-format"

    assert compute_structure_hash(document)["algorithmVersion"] == "1"
    with pytest.raises(
        ValueError, match="unsupported structure hash algorithm version"
    ):
        compute_structure_hash(document, algorithm_version="2")


def test_canonicalize_document_sorts_graphs() -> None:
    document = _document()
    second_graph = deepcopy(document["graphs"][0])
    second_graph["id"] = "alpha"
    second_graph["structure"]["nodes"] = []
    second_graph["structure"]["edges"] = []
    second_graph["structure"]["joins"] = []
    second_graph["structure"]["entryNodeIds"] = []
    second_graph["structure"]["exitNodeIds"] = []
    document["graphs"].append(second_graph)

    assert [graph["id"] for graph in canonicalize_document(document)["graphs"]] == [
        "alpha",
        "main",
    ]


# ADR 0009 byte oracle, amended by ADR 0010:
# https://docs/decisions/0009-numeric-canonical-form.md and
# https://docs/decisions/0010-numeric-domain-parsed-value-narrowing.md, and
# their implementation criteria at 0009-implementation-criteria.md.
NUMERIC_BYTE_ORACLE = [
    ("signed-zero-positive", 0.0, "0"),
    ("signed-zero-negative", -0.0, "0"),
    ("integral-float", 1.0, "1"),
    ("small-integer-boundary-positive", 100, "100"),
    ("small-integer-boundary-negative", -100, "-100"),
    ("ordinary-fraction", 0.5, "0.5"),
    ("decimal-context-regression", 1.23456789, "1.23456789"),
    ("exponent-lower-threshold-fixed", 1e-6, "0.000001"),
    ("exponent-lower-threshold-exponential", 1e-7, "1e-7"),
    ("exponent-upper-threshold-fixed", 1e20, "100000000000000000000"),
    ("exponent-upper-threshold-exponential", 1e21, "1e+21"),
    ("safe-integer-neighbor-positive", 9007199254740991, "9007199254740991"),
    ("safe-integer-neighbor-negative", -9007199254740991, "-9007199254740991"),
    ("in-domain-integer-boundary-positive", 9007199254740992, "9007199254740992"),
    ("in-domain-integer-boundary-negative", -9007199254740992, "-9007199254740992"),
    # ADR 0010: a bare integer literal beyond 2^53 narrows to its nearest
    # binary64 double rather than being rejected, exactly as `JSON.parse`
    # already narrows it in TypeScript.
    ("narrowed-integer-boundary-positive", 9007199254740993, "9007199254740992"),
    ("narrowed-integer-boundary-negative", -9007199254740993, "-9007199254740992"),
]


@pytest.mark.parametrize(
    "value,expected_bytes",
    [case[1:] for case in NUMERIC_BYTE_ORACLE],
    ids=[case[0] for case in NUMERIC_BYTE_ORACLE],
)
def test_numeric_extension_byte_oracle(value: object, expected_bytes: str) -> None:
    document = _document()
    document["x-value"] = value
    document["graphs"][0]["x-nested"] = {"list": [value]}

    output = canonical_json(document)

    assert f'"x-value":{expected_bytes}' in output
    assert f'"x-nested":{{"list":[{expected_bytes}]}}' in output


def test_f8_e1_retained_minimized_candidate_canonical_bytes() -> None:
    # Verbatim 479-byte minimized input from agent-topology-testbed
    # observations/E1/run-a/minimized (sha256 ee86a4ed...af9d22): a single
    # empty graph with "x-e1": 0.0, the retained F8 regression candidate.
    raw = (
        '{"topologyVersion":"0.1","provenance":{"generatedAt":"2000-01-01T00:00:00Z",'
        '"producer":{"name":"a","version":"1"},"framework":{"name":"a","version":"1"}},'
        '"producerLimitations":[],"structureHash":{"algorithm":"sha256",'
        '"algorithmVersion":"1","value":'
        '"0000000000000000000000000000000000000000000000000000000000000000"},'
        '"graphs":[{"id":"a","structure":{"nodes":[],"edges":[],"joins":[],'
        '"entryNodeIds":[],"exitNodeIds":[]}}],'
        '"completeness":{"status":"complete","gaps":[]},"x-e1":0.0}\n'
    )
    assert len(raw.encode("utf-8")) == 479
    document = json.loads(raw)

    # Acceptance and canonical bytes are recorded separately from the
    # (placeholder) stored hash: schema acceptance is not exercised here.
    output = canonical_json(document)
    assert output.endswith('"x-e1":0}')

    computed_hash = compute_structure_hash(document)
    assert computed_hash["algorithm"] == "sha256"
    assert computed_hash["algorithmVersion"] == "1"


def test_out_of_safe_range_integer_extension_narrows_instead_of_rejecting() -> None:
    # ADR 0010: Python could hold this exactly as an arbitrary-precision
    # `int`, but TypeScript's `number` structurally cannot, so both languages
    # narrow it to the nearest binary64 double (round-half-to-even) instead
    # of one language rejecting what the other silently rounds.
    beyond_safe_range = 9007199254740993  # 2**53 + 1

    document_level = _document()
    document_level["x-value"] = beyond_safe_range
    assert '"x-value":9007199254740992' in canonical_json(document_level)

    nested = _document()
    nested["graphs"][0]["x-nested"] = {"list": [beyond_safe_range]}
    assert '"x-nested":{"list":[9007199254740992]}' in canonical_json(nested)


def test_astronomically_large_integer_extension_is_rejected() -> None:
    # No finite binary64 double can represent this magnitude at all, unlike
    # the merely-imprecise 2**53-neighborhood case above.
    beyond_double_range = 10**400

    document = _document()
    document["x-value"] = beyond_double_range
    with pytest.raises(ValueError, match="Out of range"):
        canonical_json(document)


def test_numeric_extension_survives_serialize_parse_canonicalize_round_trip() -> None:
    # ADR 0010's closure requirement: a value's canonical output, re-parsed
    # and canonicalized again, must be byte-identical to the first pass. This
    # is the exact regression from issue #124 - comparing two calls on the
    # *original* Python object (as the older idempotence test below does) is
    # insufficient, because it never exercises the type flip that JSON text
    # introduces between an integer-shaped float and a bare integer literal.
    for name, value, _ in NUMERIC_BYTE_ORACLE:
        document = _document()
        document["x-value"] = value
        document["graphs"][0]["x-nested"] = {"list": [value]}

        first_pass = canonical_json(document)
        reparsed = json.loads(first_pass)
        second_pass = canonical_json(reparsed)

        assert second_pass == first_pass, name


def test_non_finite_numeric_extension_is_rejected() -> None:
    for bad_value in (float("nan"), float("inf"), float("-inf")):
        document = _document()
        document["x-value"] = bad_value
        with pytest.raises(ValueError, match="Out of range"):
            canonical_json(document)


def test_numeric_extension_canonicalization_is_idempotent_and_non_mutating() -> None:
    document = _document()
    document["x-value"] = 0.0
    # Not numerically sorted: proves extension array order is preserved, not
    # collection-sorted like structural fields.
    document["graphs"][0]["x-nested"] = {"list": [-0.0, 1e21, 9007199254740992]}
    original = deepcopy(document)

    first = canonical_json(document)
    second = canonical_json(document)

    assert '"x-nested":{"list":[0,1e+21,9007199254740992]}' in first
    assert first == second
    assert document == original


def test_numeric_canonicalization_is_independent_of_decimal_context() -> None:
    document = _document()
    document["x-value"] = 1.23456789
    document["graphs"][0]["x-nested"] = {"list": [1.23456789]}
    original = deepcopy(document)
    original_hash = compute_structure_hash(document)
    expected = (
        '{"completeness":{"gaps":[],"status":"complete"},"graphs":[{"id":"main",'
        '"name":"Example graph","structure":{"edges":[{"id":"a-target",'
        '"kind":"direct","source":"a","target":"target"},{"id":"b-target",'
        '"kind":"direct","source":"b","target":"target"}],'
        '"entryNodeIds":["a","b"],"exitNodeIds":["target"],"joins":[{"id":"wait",'
        '"sources":["a","b"],"target":"target"}],"nodes":[{"id":"a"},{"id":"b",'
        '"interrupts":["after","before"]},{"id":"target","type":"task"}]},'
        '"x-nested":{"list":[1.23456789]}}],"producerLimitations":[],'
        '"provenance":{"framework":{"name":"test-framework","version":"2.0"},'
        '"generatedAt":"2026-09-10T19:00:00Z","producer":{"name":"test-producer",'
        '"version":"1.0"}},"structureHash":{"algorithm":"sha256",'
        '"algorithmVersion":"1","value":"'
        + "0" * 64
        + '"},"topologyVersion":"0.1","x-value":1.23456789}'
    )

    default_output = canonical_json(document)
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_FLOOR
        context.Emin = -10
        context.Emax = 10
        context.capitals = 0
        context.clamp = 1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        context.flags[DivisionByZero] = True
        context_state = (
            context.prec,
            context.rounding,
            context.Emin,
            context.Emax,
            context.capitals,
            context.clamp,
            dict(context.traps),
            dict(context.flags),
        )

        altered_output = canonical_json(document)

        assert (
            context.prec,
            context.rounding,
            context.Emin,
            context.Emax,
            context.capitals,
            context.clamp,
            dict(context.traps),
            dict(context.flags),
        ) == context_state

    assert default_output == altered_output == expected
    reparsed = json.loads(altered_output)
    assert reparsed["x-value"] == 1.23456789
    assert reparsed["graphs"][0]["x-nested"]["list"] == [1.23456789]
    assert document == original
    assert compute_structure_hash(document) == original_hash
