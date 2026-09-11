"""Reject release dispatches outside an RC branch or its prepared versions."""

from __future__ import annotations

import argparse
import json
import os
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
