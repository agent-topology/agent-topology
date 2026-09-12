"""Consumer connections that retain multi-source join identity."""

from typing import Any


def derived_join_edges(structure: dict[str, Any]) -> list[dict[str, str]]:
    """Return fresh {joinId, source, target} records from a validated structure.

    Sort by joinId, then source, in Unicode code point order without normalization.
    Validate the containing document at the input boundary; this is not a validator.
    Read both edges and joins: these links retain AND convergence semantics and
    do not represent independent edge execution or ordinary edge IDs/kinds.
    """
    return sorted(
        (
            {"joinId": join["id"], "source": source, "target": join["target"]}
            for join in structure["joins"]
            for source in join["sources"]
        ),
        key=lambda link: (link["joinId"], link["source"]),
    )
