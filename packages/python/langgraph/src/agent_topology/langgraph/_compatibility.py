"""Enforce the producer's evidence-backed LangGraph compatibility contract."""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from importlib.metadata import version
from typing import TypedDict

from ._exceptions import UnsupportedLangGraphVersionError


class _CompatibilityContract(TypedDict):
    metadataSpecifier: str
    testedVersions: list[str]


@cache
def compatibility_contract() -> _CompatibilityContract:
    """Load the compatibility evidence shared by runtime checks and CI."""
    contract = json.loads(
        resources.files(__package__)
        .joinpath("_compatibility.json")
        .read_text(encoding="utf-8")
    )
    return _CompatibilityContract(
        metadataSpecifier=contract["metadataSpecifier"],
        testedVersions=contract["testedVersions"],
    )


def ensure_supported_langgraph_version() -> str:
    """Return the installed version or refuse an untested LangGraph release."""
    installed_version = version("langgraph")
    contract = compatibility_contract()
    if installed_version not in contract["testedVersions"]:
        raise UnsupportedLangGraphVersionError(
            installed_version=installed_version,
            supported_specifier=contract["metadataSpecifier"],
            tested_versions=tuple(contract["testedVersions"]),
        )
    return installed_version
