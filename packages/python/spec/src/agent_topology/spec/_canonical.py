"""Canonical document output and versioned structural hashing."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from copy import deepcopy
from decimal import Decimal
from typing import Any

STRUCTURE_HASH_ALGORITHM = "sha256"
STRUCTURE_HASH_ALGORITHM_VERSION = "1"

_NODE_HASH_FIELDS = ("id", "type", "subgraphId", "interrupts")
_EDGE_HASH_FIELDS = ("id", "source", "target", "kind")
_JOIN_HASH_FIELDS = ("id", "sources", "target")

# ADR 0009 (amended by ADR 0010): the supported numeric domain is exactly the
# finite binary64 values. TypeScript's public API only ever receives values
# already narrowed to a double by `JSON.parse`, so it cannot observe whether
# an out-of-domain magnitude started as an integer literal or an exponent
# literal; Python's `canonicalize_document` cannot stably keep that
# distinction either, because its own bare-digit integer spelling (e.g. `1e20`
# canonicalizes to `100000000000000000000`) decodes back through `json.loads`
# as a plain `int` indistinguishable from one a caller wrote directly. A
# domain boundary keyed on Python's `int`/`float` runtime type is therefore
# not closed under this module's own canonical JSON output. Instead, every
# JSON integer literal (Python `int`, decoded losslessly from JSON text with
# no `.` or exponent) is narrowed to its nearest binary64 double here, exactly
# as `JSON.parse` already narrows it in TypeScript, so canonicalization is
# idempotent under a JSON round trip and byte-identical across languages for
# every finite magnitude.
_NUMBER_DOMAIN_ERROR = "Out of range values are not JSON compliant"


def _ordered(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _ordered(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_ordered(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(_NUMBER_DOMAIN_ERROR)
        return value
    if isinstance(value, int):
        try:
            narrowed = float(value)
        except OverflowError:
            raise ValueError(_NUMBER_DOMAIN_ERROR) from None
        if not math.isfinite(narrowed):
            raise ValueError(_NUMBER_DOMAIN_ERROR)
        return narrowed
    return value


def _format_number(value: float) -> str:
    """Spell a finite, in-domain JSON number per ADR 0009's byte oracle.

    Implements ECMA-262's ``Number::toString`` (the same rule RFC 8785
    adopts): the shortest round-tripping decimal digit string, formatted as
    fixed-point or exponential depending on its decimal exponent. Callers
    always pass a `float`: `_ordered` narrows every JSON integer literal to
    its nearest binary64 double before this function ever sees it.
    """
    if value == 0:
        return "0"
    negative = value < 0
    magnitude = -value if negative else value
    decimal_value = Decimal(repr(magnitude))
    _, digit_tuple, exponent = decimal_value.normalize().as_tuple()
    digits = "".join(str(digit) for digit in digit_tuple)
    k = len(digits)
    n = exponent + k
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = f"{digits[:n]}.{digits[n:]}"
    elif -6 < n <= 0:
        body = f"0.{'0' * -n}{digits}"
    else:
        first, rest = digits[0], digits[1:]
        mantissa = f"{first}.{rest}" if rest else first
        signed_exponent = n - 1
        body = (
            f"{mantissa}e{'+' if signed_exponent >= 0 else '-'}{abs(signed_exponent)}"
        )
    return f"-{body}" if negative else body


def _encode(value: Any) -> str:
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(f"{_encode(key)}:{_encode(item)}" for key, item in value.items())
            + "}"
        )
    if isinstance(value, list):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return _format_number(value)
    return json.dumps(value, ensure_ascii=False)


def _sort_key(value: Any) -> str:
    return json.dumps(
        _ordered(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonicalize_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical copy of a topology document without mutating the input.

    Contract-defined structural collections are sets and are sorted here. Arrays in
    extensions and descriptive fields retain their order because the core contract
    does not define their semantics.
    """
    canonical = deepcopy(dict(document))

    for graph in canonical.get("graphs", []):
        structure = graph["structure"]
        for node in structure["nodes"]:
            if "interrupts" in node:
                node["interrupts"] = sorted(node["interrupts"])
        for join in structure["joins"]:
            join["sources"] = sorted(join["sources"])

        structure["nodes"] = sorted(structure["nodes"], key=_sort_key)
        structure["edges"] = sorted(structure["edges"], key=_sort_key)
        structure["joins"] = sorted(structure["joins"], key=_sort_key)
        structure["entryNodeIds"] = sorted(structure["entryNodeIds"])
        structure["exitNodeIds"] = sorted(structure["exitNodeIds"])

    canonical["graphs"] = sorted(canonical.get("graphs", []), key=_sort_key)
    return _ordered(canonical)


def canonical_json(document: Mapping[str, Any]) -> str:
    """Serialize a topology document to its byte-stable canonical JSON form."""
    return _encode(canonicalize_document(document))


def _selected_fields(
    value: Mapping[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    return {field: value[field] for field in fields if field in value}


def _structure_projection_v1(document: Mapping[str, Any]) -> dict[str, Any]:
    canonical = canonicalize_document(document)
    graphs: list[dict[str, Any]] = []

    for graph in canonical["graphs"]:
        structure = graph["structure"]
        graphs.append(
            {
                "id": graph["id"],
                "structure": {
                    "nodes": [
                        _selected_fields(node, _NODE_HASH_FIELDS)
                        for node in structure["nodes"]
                    ],
                    "edges": [
                        _selected_fields(edge, _EDGE_HASH_FIELDS)
                        for edge in structure["edges"]
                    ],
                    "joins": [
                        _selected_fields(join, _JOIN_HASH_FIELDS)
                        for join in structure["joins"]
                    ],
                    "entryNodeIds": structure["entryNodeIds"],
                    "exitNodeIds": structure["exitNodeIds"],
                },
            }
        )

    return {"graphs": graphs}


_HASH_PROJECTIONS: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "1": _structure_projection_v1,
}


def compute_structure_hash(
    document: Mapping[str, Any],
    *,
    algorithm_version: str = STRUCTURE_HASH_ALGORITHM_VERSION,
) -> dict[str, str]:
    """Compute the versioned hash field for a topology document's structure."""
    try:
        project_structure = _HASH_PROJECTIONS[algorithm_version]
    except KeyError:
        supported = ", ".join(sorted(_HASH_PROJECTIONS))
        raise ValueError(
            f"unsupported structure hash algorithm version {algorithm_version!r}; "
            f"supported versions: {supported}"
        ) from None

    projection = project_structure(document)
    payload = json.dumps(
        projection,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "algorithm": STRUCTURE_HASH_ALGORITHM,
        "algorithmVersion": algorithm_version,
        "value": hashlib.sha256(payload).hexdigest(),
    }


def finalize_document(
    document: Mapping[str, Any],
    *,
    algorithm_version: str = STRUCTURE_HASH_ALGORITHM_VERSION,
) -> dict[str, Any]:
    """Set the structure hash and return the canonical output document."""
    finalized = deepcopy(dict(document))
    finalized["structureHash"] = compute_structure_hash(
        finalized, algorithm_version=algorithm_version
    )
    return canonicalize_document(finalized)
