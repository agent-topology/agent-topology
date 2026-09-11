"""Reject release dispatches outside an RC branch or its prepared versions."""

from __future__ import annotations

import argparse
import json
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepared_package(ecosystem: str, package: str) -> dict:
    if ecosystem not in {"python", "npm"} or package not in {"spec", "langgraph"}:
        raise ValueError("unsupported release package")
    if ecosystem == "python":
        path = ROOT / "packages/python" / package / "pyproject.toml"
        project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    else:
        path = ROOT / "packages/typescript" / package / "package.json"
        project = json.loads(path.read_text(encoding="utf-8"))
    return project


_PRERELEASE_ORDER = {"a": 0, "b": 1, "rc": 2}

_VERSION_OPERATORS = {
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
    ">=": lambda left, right: left >= right,
    "<=": lambda left, right: left <= right,
    ">": lambda left, right: left > right,
    "<": lambda left, right: left < right,
}


def _version_key(version: str) -> tuple[tuple[int, ...], tuple[int, int]]:
    """Order a release segment and an optional a/b/rc pre-release suffix.

    Covers only the PEP 440 shapes this repo actually issues (dotted release
    numbers with an optional single pre-release suffix); it is not a general
    PEP 440 parser.
    """
    match = re.fullmatch(
        r"(?P<release>\d+(?:\.\d+)*)(?:(?P<label>a|b|rc)(?P<num>\d+))?", version
    )
    if match is None:
        raise ValueError(f"unsupported version format: {version!r}")
    release = tuple(int(part) for part in match["release"].split("."))
    label = match["label"]
    pre = (
        (_PRERELEASE_ORDER[label], int(match["num"]))
        if label is not None
        else (len(_PRERELEASE_ORDER), 0)
    )
    return release, pre


def _satisfies_specifier(version: str, specifier: str) -> bool:
    key = _version_key(version)
    for clause in specifier.split(","):
        match = re.fullmatch(r"\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*", clause)
        if match is None:
            raise ValueError(f"unsupported specifier clause: {clause!r}")
        operator, bound = match.groups()
        if not _VERSION_OPERATORS[operator](key, _version_key(bound)):
            return False
    return True


def _dependency_specifier(project: dict, name: str) -> str:
    for dependency in project["dependencies"]:
        match = re.fullmatch(rf"{re.escape(name)}([<>=!].+)", dependency)
        if match:
            return match.group(1)
    raise ValueError(f"{project['name']} does not declare a {name} dependency")


def resolve_producer_spec_version(package: str) -> str:
    """Resolve the prepared spec version a registry preflight should pin to.

    For ``langgraph``, confirms the prepared spec version satisfies the
    producer's committed dependency requirement first, so a preflight never
    pins to a version the producer does not actually accept, and never lets
    the registry choose an arbitrary latest version instead.
    """
    spec_version = prepared_package("python", "spec")["version"]
    if package == "spec":
        return spec_version
    producer = prepared_package("python", package)
    specifier = _dependency_specifier(producer, "agent-topology-spec")
    if not _satisfies_specifier(spec_version, specifier):
        raise ValueError(
            f"prepared agent-topology-spec version {spec_version!r} does not satisfy "
            f"{producer['name']}'s requirement {specifier!r}"
        )
    return spec_version


def check_version_copies() -> None:
    """Reject stale local package versions in independently owned lockfiles."""
    for package in ("spec", "langgraph"):
        project = prepared_package("npm", package)
        lock = json.loads(
            (ROOT / "packages/typescript" / package / "package-lock.json").read_text()
        )
        for copy in (lock, lock["packages"][""]):
            if copy["version"] != project["version"]:
                raise ValueError(f"npm {package} lock version differs from manifest")
        if package == "langgraph":
            peer = project["peerDependencies"]
            if lock["packages"][""]["peerDependencies"] != peer:
                raise ValueError("npm lock peer differs from manifest")
            spec = prepared_package("npm", "spec")
            if lock["packages"]["../spec"]["version"] != spec["version"]:
                raise ValueError("npm linked spec lock version differs from manifest")
    for package in ("spec", "langgraph"):
        lock = tomllib.loads(
            (ROOT / "packages/python" / package / "uv.lock").read_text()
        )
        for entry in lock["package"]:
            if entry["name"] in {"agent-topology-spec", "agent-topology-langgraph"}:
                name = entry["name"].removeprefix("agent-topology-")
                if entry["version"] != prepared_package("python", name)["version"]:
                    raise ValueError(
                        f"Python {package} lock version differs from {name} manifest"
                    )


def validate_selection(
    ecosystem: str,
    package: str,
    version: str,
    *,
    ref: str,
    spec_version: str = "",
) -> None:
    prefix = "refs/heads/rc/"
    if not ref.startswith(prefix) or not ref.removeprefix(prefix):
        raise ValueError("release workflows require an rc/<version> branch")
    project = prepared_package(ecosystem, package)
    if version != project["version"]:
        raise ValueError(
            f"selected version {version!r} differs from source {project['version']!r}; "
            "prepare and commit package versions before qualification"
        )
    check_version_copies()
    if ecosystem == "npm" and package == "langgraph":
        expected = project["peerDependencies"]["@agent-topology/spec"]
        if spec_version != expected:
            raise ValueError(f"spec-version must match the prepared peer {expected!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecosystem", choices=("python", "npm"), required=True)
    parser.add_argument("--package", choices=("spec", "langgraph"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--spec-version", default="")
    args = parser.parse_args()
    try:
        validate_selection(
            args.ecosystem,
            args.package,
            args.version,
            ref=os.environ.get("GITHUB_REF", ""),
            spec_version=args.spec_version,
        )
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
