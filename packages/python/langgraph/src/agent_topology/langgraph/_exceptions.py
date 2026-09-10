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


class UnsupportedLangGraphVersionError(RuntimeError):
    """Raised before extraction when the installed LangGraph was not tested."""

    def __init__(
        self,
        *,
        installed_version: str,
        supported_specifier: str,
        tested_versions: tuple[str, ...],
    ) -> None:
        self.installed_version = installed_version
        self.supported_specifier = supported_specifier
        self.tested_versions = tested_versions
        tested = ", ".join(tested_versions)
        super().__init__(
            f"Unsupported LangGraph version {installed_version}. "
            f"agent-topology-langgraph has conformance evidence only for {tested}. "
            "Install a tested release with "
            f'`python -m pip install "langgraph{supported_specifier}"`.'
        )
