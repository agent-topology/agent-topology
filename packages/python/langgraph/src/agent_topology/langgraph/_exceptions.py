"""Public exceptions raised by the LangGraph producer."""

from typing import Any


class IncompleteTopologyError(RuntimeError):
    """Raised when strict extraction produces graph-specific gaps.

    Attributes:
        document: The canonical incomplete topology document, including every gap.
    """

    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        gap_count = len(document["completeness"]["gaps"])
        suffix = "gap" if gap_count == 1 else "gaps"
        super().__init__(
            f"Topology extraction is incomplete: {gap_count} graph-specific {suffix}."
        )
