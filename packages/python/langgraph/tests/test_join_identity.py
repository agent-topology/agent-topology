"""Join identity fixes for issue #182.

conformance/fixtures/join-permuted-sources and join-repeated-declaration cover
the shared, cross-language-equal dedup cases (see conformance/README.md). This
file covers what cannot be a shared fixture: Python's upstream-unobservable
delimiter failure, general declaration-order stability for genuinely distinct
joins, and a negative control against over-eager deduplication. See ADR 0015.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

import pytest
from agent_topology.langgraph import describe
from agent_topology.spec import canonical_json, validate_document
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph


class _State(TypedDict):
    values: Annotated[list[str], operator.add]


def _step(_state: _State) -> dict[str, list[str]]:
    return {"values": []}


def test_delimiter_bearing_distinct_source_sets_fail_upstream_before_extraction():
    """[a+b, c] and [a, b+c] both encode as "a+b+c" under the old delimiter,
    but here LangGraph's own drawable construction collides on node names
    containing "+" before this producer's join logic ever runs. This is a
    distinct, upstream-unobservable failure, not a claim that a document was
    extracted; do not attribute it to this producer's join generation.
    """
    names = sorted({"a", "a+b", "b+c", "c"}) + ["sink"]
    builder = StateGraph(_State)
    for name in names:
        builder.add_node(name, _step)
        if name != "sink":
            builder.add_edge(START, name)
    builder.add_edge(["a+b", "c"], "sink")
    builder.add_edge(["a", "b+c"], "sink")
    builder.add_edge("sink", END)
    compiled = builder.compile()

    with pytest.raises(InvalidUpdateError):
        describe(compiled)


def test_reversed_join_declaration_order_yields_identical_document():
    """Two distinct joins (different source sets, different targets)
    canonicalize to the same document and hash regardless of which is
    declared first, per ADR 0003.
    """

    def build(*, reverse: bool) -> object:
        builder = StateGraph(_State)
        for name in ("a", "b", "c", "left", "right"):
            builder.add_node(name, _step)
        builder.add_edge(START, "a")
        builder.add_edge(START, "b")
        builder.add_edge(START, "c")
        declarations = [(["a", "b"], "left"), (["b", "c"], "right")]
        for sources, target in reversed(declarations) if reverse else declarations:
            builder.add_edge(sources, target)
        builder.add_edge("left", END)
        builder.add_edge("right", END)
        return builder.compile()

    forward = describe(build(reverse=False))
    reversed_document = describe(build(reverse=True))
    reversed_document["provenance"] = forward["provenance"]

    assert canonical_json(forward) == canonical_json(reversed_document)
    assert not validate_document(forward)
    ids = sorted(join["id"] for join in forward["graphs"][0]["structure"]["joins"])
    assert ids == ["join:a+b:left", "join:b+c:right"]


def test_distinct_source_sets_sharing_a_source_and_target_stay_distinct():
    """Deduplication keys on (sorted sources, target); a genuinely different
    source set must not collapse into an unrelated join even when the two
    sets overlap and share a target.
    """
    builder = StateGraph(_State)
    for name in ("a", "b", "c", "sink"):
        builder.add_node(name, _step)
    builder.add_edge(START, "a")
    builder.add_edge(START, "b")
    builder.add_edge(START, "c")
    builder.add_edge(["a", "b"], "sink")
    builder.add_edge(["a", "c"], "sink")
    builder.add_edge("sink", END)

    document = describe(builder.compile())

    assert not validate_document(document)
    ids = sorted(join["id"] for join in document["graphs"][0]["structure"]["joins"])
    assert ids == ["join:a+b:sink", "join:a+c:sink"]
