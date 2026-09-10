"""Public utilities for the agent-topology document contract."""

from ._canonical import (
    STRUCTURE_HASH_ALGORITHM,
    STRUCTURE_HASH_ALGORITHM_VERSION,
    canonical_json,
    canonicalize_document,
    compute_structure_hash,
    finalize_document,
)
from ._validation import load_schema, validate_document

__all__ = [
    "STRUCTURE_HASH_ALGORITHM",
    "STRUCTURE_HASH_ALGORITHM_VERSION",
    "canonical_json",
    "canonicalize_document",
    "compute_structure_hash",
    "finalize_document",
    "load_schema",
    "validate_document",
]
