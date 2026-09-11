#!/usr/bin/env python3
"""Inspect one Python distribution's wheel and source distribution."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

PACKAGES = {
    "spec": {
        "distribution": "agent-topology-spec",
        "module": "spec",
        "generated_files": {"agent-topology.schema.json"},
        "requirements": {"jsonschema==4.26.0"},
        "scripts": {},
    },
    "langgraph": {
        "distribution": "agent-topology-langgraph",
        "module": "langgraph",
        "generated_files": set(),
        "requirements": {
            "agent-topology-spec<0.2.0,>=0.1.0b1",
            "langgraph<=1.2.11,>=1.2.10",
        },
        "scripts": {"agt": "agent_topology.langgraph._cli:main"},
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


def _metadata(raw: bytes, *, archive: Path) -> dict[str, Any]:
    message = BytesParser().parsebytes(raw)
    required = ("Name", "Version", "Requires-Python")
    missing = [field for field in required if not message.get(field)]
    if missing:
        raise ValueError(f"{archive.name} metadata is missing: {', '.join(missing)}")
    return {
        **{field: str(message[field]) for field in required},
        "Requires-Dist": set(message.get_all("Requires-Dist", [])),
    }


def _assert_metadata(
    metadata: dict[str, Any],
    *,
    distribution: str,
    version: str,
    requirements: set[str],
    archive: Path,
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
    if metadata["Requires-Dist"] != requirements:
        raise ValueError(
            f"{archive.name} has unexpected dependencies: "
            f"{sorted(metadata['Requires-Dist'])}"
        )


def _assert_wheel_scripts(
    archive: zipfile.ZipFile, members: list[str], *, scripts: dict[str, str]
) -> None:
    entry_points = [
        name for name in members if name.endswith(".dist-info/entry_points.txt")
    ]
    if not scripts:
        if entry_points:
            raise ValueError(f"{archive.filename} unexpectedly publishes entry points")
        return
    if len(entry_points) != 1:
        raise ValueError(
            f"{archive.filename} must contain exactly one entry_points.txt"
        )
    parser = configparser.ConfigParser()
    parser.read_string(archive.read(entry_points[0]).decode("utf-8"))
    actual = (
        dict(parser.items("console_scripts"))
        if parser.has_section("console_scripts")
        else {}
    )
    if actual != scripts:
        raise ValueError(f"{archive.filename} has unexpected console scripts: {actual}")


def _one(dist_dir: Path, suffix: str) -> Path:
    matches = sorted(dist_dir.glob(f"*{suffix}"))
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one *{suffix} in {dist_dir}, found {len(matches)}"
        )
    return matches[0]


def _source_package_files(package: str, module: str, source_root: Path) -> set[str]:
    package_dir = (
        source_root
        / "packages"
        / "python"
        / package
        / "src"
        / "agent_topology"
        / module
    )
    if not package_dir.is_dir():
        raise ValueError(f"package source directory does not exist: {package_dir}")
    return {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    }


def _inspect_wheel(
    wheel: Path,
    *,
    distribution: str,
    module: str,
    version: str,
    requirements: set[str],
    scripts: dict[str, str],
    expected: set[str],
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
            requirements=requirements,
            archive=wheel,
        )
        _assert_wheel_scripts(archive, members, scripts=scripts)
        license_member = (
            metadata_members[0].removesuffix("METADATA") + "licenses/LICENSE"
        )
        expected_license = (
            Path(__file__).resolve().parents[1] / "LICENSE"
        ).read_bytes()
        if (
            license_member not in members
            or archive.read(license_member) != expected_license
        ):
            raise ValueError(f"{wheel.name} must contain the repository license notice")
        message = BytesParser().parsebytes(archive.read(metadata_members[0]))
        if (
            message.get("Description-Content-Type") != "text/markdown"
            or not message.get_payload()
        ):
            raise ValueError(f"{wheel.name} must include its Markdown package README")

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
    sdist: Path,
    *,
    distribution: str,
    module: str,
    version: str,
    requirements: set[str],
    scripts: dict[str, str],
    expected: set[str],
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
            requirements=requirements,
            archive=sdist,
        )

        root = PurePosixPath(metadata_members[0]).parts[0]
        license_member = f"{root}/LICENSE"
        if license_member not in members:
            raise ValueError(f"{sdist.name} must contain the repository license notice")
        license_file = archive.extractfile(license_member)
        expected_license = (
            Path(__file__).resolve().parents[1] / "LICENSE"
        ).read_bytes()
        if license_file is None or license_file.read() != expected_license:
            raise ValueError(f"{sdist.name} has an incorrect license notice")
        if f"{root}/README.md" not in members:
            raise ValueError(f"{sdist.name} must include its package README")
        pyproject_member = f"{root}/pyproject.toml"
        pyproject_file = archive.extractfile(pyproject_member)
        if pyproject_file is None:
            raise ValueError(f"{sdist.name} is missing {pyproject_member}")
        project = tomllib.loads(pyproject_file.read().decode("utf-8"))
        actual_scripts = project["project"].get("scripts", {})
        if actual_scripts != scripts:
            raise ValueError(
                f"{sdist.name} has unexpected console scripts: {actual_scripts}"
            )

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


def inspect_artifacts(
    package: str, version: str, dist_dir: Path, source_root: Path = Path(".")
) -> dict[str, Any]:
    """Validate and describe the two artifacts for ``package``."""
    config = PACKAGES[package]
    expected = (
        _source_package_files(package, config["module"], source_root)
        | config["generated_files"]
    )
    wheel = _one(dist_dir, ".whl")
    sdist = _one(dist_dir, ".tar.gz")
    _inspect_wheel(
        wheel,
        distribution=config["distribution"],
        module=config["module"],
        version=version,
        requirements=config["requirements"],
        scripts=config["scripts"],
        expected=expected,
    )
    _inspect_sdist(
        sdist,
        distribution=config["distribution"],
        module=config["module"],
        version=version,
        requirements=config["requirements"],
        scripts=config["scripts"],
        expected=expected,
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
