#!/usr/bin/env python3
"""Inspect one Python distribution's wheel and source distribution."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from collections.abc import Iterable
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

PACKAGES = {
    "spec": {
        "distribution": "agent-topology-spec",
        "module": "spec",
        "wheel_files": {
            "__init__.py",
            "_canonical.py",
        },
    },
    "langgraph": {
        "distribution": "agent-topology-langgraph",
        "module": "langgraph",
        "wheel_files": {
            "__init__.py",
            "_compatibility.json",
            "_compatibility.py",
            "_describe.py",
            "_exceptions.py",
        },
    },
}


def _safe_members(names: Iterable[str], *, archive: Path) -> list[str]:
    members = list(names)
    unsafe = [
        name
        for name in members
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
    ]
    if unsafe:
        raise ValueError(f"{archive.name} contains unsafe paths: {unsafe}")
    return members


def _metadata(raw: bytes, *, archive: Path) -> dict[str, str]:
    message = BytesParser().parsebytes(raw)
    required = ("Name", "Version", "Requires-Python")
    missing = [field for field in required if not message.get(field)]
    if missing:
        raise ValueError(f"{archive.name} metadata is missing: {', '.join(missing)}")
    return {field: str(message[field]) for field in required}


def _assert_metadata(
    metadata: dict[str, str], *, distribution: str, version: str, archive: Path
) -> None:
    actual_name = metadata["Name"].lower().replace("_", "-")
    if actual_name != distribution:
        raise ValueError(
            f"{archive.name} names {metadata['Name']!r}, expected {distribution!r}"
        )
    if metadata["Version"] != version:
        raise ValueError(
            f"{archive.name} has version {metadata['Version']!r}, expected {version!r}"
        )
    python_bounds = {part.strip() for part in metadata["Requires-Python"].split(",")}
    if python_bounds != {">=3.11", "<3.15"}:
        raise ValueError(
            f"{archive.name} has unexpected Requires-Python "
            f"{metadata['Requires-Python']!r}"
        )


def _one(dist_dir: Path, suffix: str) -> Path:
    matches = sorted(dist_dir.glob(f"*{suffix}"))
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one *{suffix} in {dist_dir}, found {len(matches)}"
        )
    return matches[0]


def _inspect_wheel(
    wheel: Path, *, distribution: str, module: str, version: str, expected: set[str]
) -> None:
    with zipfile.ZipFile(wheel) as archive:
        members = _safe_members(archive.namelist(), archive=wheel)
        metadata_members = [
            name for name in members if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_members) != 1:
            raise ValueError(
                f"{wheel.name} must contain exactly one .dist-info/METADATA"
            )
        _assert_metadata(
            _metadata(archive.read(metadata_members[0]), archive=wheel),
            distribution=distribution,
            version=version,
            archive=wheel,
        )

    if "agent_topology/__init__.py" in members:
        raise ValueError(f"{wheel.name} must not own agent_topology/__init__.py")
    prefix = f"agent_topology/{module}/"
    actual = {
        name.removeprefix(prefix)
        for name in members
        if name.startswith(prefix) and not name.endswith("/")
    }
    if actual != expected:
        raise ValueError(
            f"{wheel.name} package contents differ: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    foreign = [
        name
        for name in members
        if name.startswith("agent_topology/") and not name.startswith(prefix)
    ]
    if foreign:
        raise ValueError(f"{wheel.name} contains another namespace portion: {foreign}")


def _inspect_sdist(
    sdist: Path, *, distribution: str, module: str, version: str, expected: set[str]
) -> None:
    with tarfile.open(sdist, "r:gz") as archive:
        members = _safe_members(
            (member.name for member in archive.getmembers()), archive=sdist
        )
        metadata_members = [
            name
            for name in members
            if name.count("/") == 1 and name.endswith("/PKG-INFO")
        ]
        if len(metadata_members) != 1:
            raise ValueError(f"{sdist.name} must contain exactly one root PKG-INFO")
        extracted = archive.extractfile(metadata_members[0])
        if extracted is None:
            raise ValueError(f"{sdist.name} PKG-INFO is not a regular file")
        _assert_metadata(
            _metadata(extracted.read(), archive=sdist),
            distribution=distribution,
            version=version,
            archive=sdist,
        )

    root = PurePosixPath(metadata_members[0]).parts[0]
    required = {f"{root}/pyproject.toml"} | {
        f"{root}/src/agent_topology/{module}/{name}" for name in expected
    }
    missing = required - set(members)
    if missing:
        raise ValueError(f"{sdist.name} is missing package files: {sorted(missing)}")
    if f"{root}/src/agent_topology/__init__.py" in members:
        raise ValueError(f"{sdist.name} must not own agent_topology/__init__.py")
    if not any(name.startswith(f"{root}/tests/") for name in members):
        raise ValueError(f"{sdist.name} does not contain its package tests")


def inspect_artifacts(package: str, version: str, dist_dir: Path) -> dict[str, Any]:
    """Validate and describe the two artifacts for ``package``."""
    config = PACKAGES[package]
    wheel = _one(dist_dir, ".whl")
    sdist = _one(dist_dir, ".tar.gz")
    _inspect_wheel(
        wheel,
        distribution=config["distribution"],
        module=config["module"],
        version=version,
        expected=config["wheel_files"],
    )
    _inspect_sdist(
        sdist,
        distribution=config["distribution"],
        module=config["module"],
        version=version,
        expected=config["wheel_files"],
    )
    artifacts = []
    for path in (wheel, sdist):
        artifacts.append(
            {
                "filename": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return {
        "artifacts": artifacts,
        "distribution": config["distribution"],
        "package": package,
        "version": version,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", choices=sorted(PACKAGES), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect_artifacts(args.package, args.version, args.dist_dir)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
