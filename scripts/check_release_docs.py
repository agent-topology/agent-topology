"""Validate the candidate-to-published documentation state transition."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "docs/releases/release-state.json"

PACKAGE_LAYOUT = {
    "agent-topology-spec": ("python", ROOT / "packages/python/spec/pyproject.toml"),
    "agent-topology-langgraph": (
        "python",
        ROOT / "packages/python/langgraph/pyproject.toml",
    ),
    "@agent-topology/spec": ("npm", ROOT / "packages/typescript/spec/package.json"),
    "@agent-topology/langgraph": (
        "npm",
        ROOT / "packages/typescript/langgraph/package.json",
    ),
}

PACKAGE_READMES = {
    "agent-topology-spec": ROOT / "packages/python/spec/README.md",
    "agent-topology-langgraph": ROOT / "packages/python/langgraph/README.md",
    "@agent-topology/spec": ROOT / "packages/typescript/spec/README.md",
    "@agent-topology/langgraph": ROOT / "packages/typescript/langgraph/README.md",
}


class ReleaseDocsError(ValueError):
    """The checked-in release state or its public documentation is incoherent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseDocsError(message)


def _repository_path(value: object, field: str) -> Path:
    _require(isinstance(value, str) and bool(value), f"{field} must be a path")
    path = (ROOT / value).resolve()
    _require(path.is_relative_to(ROOT), f"{field} escapes the repository")
    _require(path.is_file(), f"{field} does not exist: {value}")
    return path


def _validate_packages(packages: object, owner: str) -> dict[str, str]:
    _require(isinstance(packages, list), f"{owner}.packages must be a list")
    versions: dict[str, str] = {}
    for package in packages:
        _require(isinstance(package, dict), f"{owner}.packages entries must be objects")
        name = package.get("name")
        ecosystem = package.get("ecosystem")
        version = package.get("version")
        _require(name in PACKAGE_LAYOUT, f"{owner} has unknown package: {name}")
        expected_ecosystem = PACKAGE_LAYOUT[name][0]
        _require(
            ecosystem == expected_ecosystem,
            f"{owner}.{name} must use ecosystem {expected_ecosystem}",
        )
        _require(isinstance(version, str), f"{owner}.{name} version must be a string")
        pattern = (
            r"^\d+\.\d+\.\d+(?:a|b|rc)\d+$"
            if ecosystem == "python"
            else r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$"
        )
        _require(re.fullmatch(pattern, version) is not None, f"invalid {name} version")
        _require(name not in versions, f"{owner} duplicates package {name}")
        versions[name] = version
    _require(
        set(versions) == set(PACKAGE_LAYOUT), f"{owner} must name all four packages"
    )
    return versions


def _validate_release(release: object, owner: str, *, partial: bool = False) -> None:
    _require(isinstance(release, dict), f"{owner} must be an object")
    version = release.get("coordinatedVersion")
    _require(
        isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+-beta\.\d+", version),
        f"{owner}.coordinatedVersion must be a beta SemVer",
    )
    _require(release.get("tag") == f"v{version}", f"{owner}.tag must match its version")
    _repository_path(release.get("releaseNotes"), f"{owner}.releaseNotes")
    _validate_packages(release.get("packages"), owner)
    if partial:
        _require(
            isinstance(release.get("sourceCommit"), str)
            and re.fullmatch(r"[0-9a-f]{40}", release["sourceCommit"]),
            f"{owner}.sourceCommit must be a full commit hash",
        )
        evidence_path = _repository_path(release.get("evidence"), f"{owner}.evidence")
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        _require(evidence.get("schemaVersion") == 1, f"{owner} evidence schema")
        _require(
            evidence.get("coordinatedComplete") is False,
            f"{owner} evidence must remain incomplete",
        )
        _require(
            evidence.get("githubRelease") is None,
            f"{owner} evidence must not claim a GitHub release",
        )
        _require(
            bool(evidence.get("blockingDiscrepancies")),
            f"{owner} evidence must record blocking discrepancies",
        )
        for field in ("coordinatedVersion", "tag", "sourceCommit"):
            _require(
                evidence.get(field) == release.get(field),
                f"{owner} evidence {field} mismatch",
            )
        evidence_packages = evidence.get("packages")
        _require(isinstance(evidence_packages, list), f"{owner} evidence packages")
        expected = {
            (package["name"], package["version"]) for package in release["packages"]
        }
        actual = {
            (package.get("name"), package.get("version"))
            for package in evidence_packages
        }
        _require(actual == expected, f"{owner} evidence package set mismatch")
        for package in evidence_packages:
            _require(bool(package.get("workflowRun")), f"{owner} workflow run missing")
            artifacts = package.get("artifacts")
            _require(
                isinstance(artifacts, list) and artifacts, f"{owner} artifacts missing"
            )
            for artifact in artifacts:
                _require(bool(artifact.get("url")), f"{owner} artifact URL missing")
                _require(
                    bool(artifact.get("sha256") or artifact.get("integrity")),
                    f"{owner} artifact digest missing",
                )
                _require(
                    bool(artifact.get("provenanceUrl")),
                    f"{owner} artifact provenance missing",
                )
        _require(bool(release.get("reason")), f"{owner}.reason is required")
    else:
        _repository_path(release.get("migrationGuide"), f"{owner}.migrationGuide")


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    state = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(state, dict), "release state must be an object")
    _require(state.get("schemaVersion") == 1, "unsupported release-state schema")
    _validate_release(state.get("coordinatedPublished"), "coordinatedPublished")
    candidate = state.get("candidate")
    if candidate is not None:
        _validate_release(candidate, "candidate")
        _require(bool(candidate.get("branch")), "candidate.branch is required")
    partials = state.get("partialPublications")
    _require(isinstance(partials, list), "partialPublications must be a list")
    for index, partial in enumerate(partials):
        _validate_release(partial, f"partialPublications[{index}]", partial=True)
    versions = [state["coordinatedPublished"]["coordinatedVersion"]]
    versions.extend(partial["coordinatedVersion"] for partial in partials)
    if candidate is not None:
        versions.append(candidate["coordinatedVersion"])
    _require(
        len(versions) == len(set(versions)), "release versions must not overlap states"
    )
    return state


def _package_versions(release: dict[str, Any]) -> dict[str, str]:
    return {package["name"]: package["version"] for package in release["packages"]}


def _read_manifest_version(name: str) -> str:
    ecosystem, path = PACKAGE_LAYOUT[name]
    if ecosystem == "python":
        with path.open("rb") as source:
            return tomllib.load(source)["project"]["version"]
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def _expected_install(name: str, version: str) -> str:
    if name.startswith("agent-topology-"):
        return f"{name}=={version}"
    return f"{name}@{version}"


def _assert_install_versions(
    release: dict[str, Any], documents: dict[str, tuple[str, ...]]
) -> None:
    versions = _package_versions(release)
    for relative, names in documents.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for name in names:
            expected = _expected_install(name, versions[name])
            _require(expected in text, f"{relative} must select {expected}")


def check_published(state: dict[str, Any]) -> None:
    published = state["coordinatedPublished"]
    if published["coordinatedVersion"] != "0.1.0-beta.2":
        _require(
            isinstance(published.get("sourceCommit"), str)
            and re.fullmatch(r"[0-9a-f]{40}", published["sourceCommit"]),
            "published closeout requires a full sourceCommit",
        )
        evidence_path = _repository_path(
            published.get("evidence"), "coordinatedPublished.evidence"
        )
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        for field in ("coordinatedVersion", "tag", "sourceCommit"):
            _require(
                evidence.get(field) == published.get(field),
                f"published evidence {field} mismatch",
            )
        _require(
            bool(published.get("githubRelease")),
            "published closeout requires a GitHub release URL",
        )
    _assert_install_versions(
        published,
        {
            "README.md": tuple(PACKAGE_LAYOUT),
            "packages/python/spec/README.md": ("agent-topology-spec",),
            "packages/python/langgraph/README.md": ("agent-topology-langgraph",),
            "packages/typescript/spec/README.md": ("@agent-topology/spec",),
            "packages/typescript/langgraph/README.md": (
                "@agent-topology/spec",
                "@agent-topology/langgraph",
            ),
            "docs/getting-started/python.md": ("agent-topology-langgraph",),
            "docs/getting-started/typescript.md": (
                "@agent-topology/spec",
                "@agent-topology/langgraph",
            ),
        },
    )
    release_notes = _repository_path(
        published["releaseNotes"], "coordinatedPublished.releaseNotes"
    ).read_text(encoding="utf-8")
    _require(
        "published and verified" in release_notes.lower(),
        "published release notes must say published and verified",
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    _require(published["releaseNotes"] in readme, "README must link published notes")
    _require(published["migrationGuide"] in readme, "README must link migration guide")
    for partial in state["partialPublications"]:
        notes = _repository_path(
            partial["releaseNotes"], "partial release notes"
        ).read_text(encoding="utf-8")
        _require(
            "partial publication" in notes.lower(),
            f"{partial['coordinatedVersion']} notes must identify "
            "a partial publication",
        )


def check_candidate(state: dict[str, Any]) -> None:
    candidate = state.get("candidate")
    _require(candidate is not None, "candidate phase requires candidate release state")
    versions = _package_versions(candidate)
    for name, expected in versions.items():
        actual = _read_manifest_version(name)
        _require(
            actual == expected, f"{name} manifest is {actual}, expected {expected}"
        )
    _assert_install_versions(
        candidate,
        {
            str(PACKAGE_READMES["agent-topology-spec"].relative_to(ROOT)): (
                "agent-topology-spec",
            ),
            str(PACKAGE_READMES["agent-topology-langgraph"].relative_to(ROOT)): (
                "agent-topology-langgraph",
            ),
            str(PACKAGE_READMES["@agent-topology/spec"].relative_to(ROOT)): (
                "@agent-topology/spec",
            ),
            str(PACKAGE_READMES["@agent-topology/langgraph"].relative_to(ROOT)): (
                "@agent-topology/spec",
                "@agent-topology/langgraph",
            ),
        },
    )
    with (ROOT / "packages/python/langgraph/pyproject.toml").open("rb") as source:
        python_dependencies = tomllib.load(source)["project"]["dependencies"]
    expected_python_spec = versions["agent-topology-spec"]
    _require(
        any(
            dependency.startswith("agent-topology-spec")
            and expected_python_spec in dependency
            for dependency in python_dependencies
        ),
        "Python producer dependency must select the candidate specification",
    )
    npm_producer = json.loads(
        (ROOT / "packages/typescript/langgraph/package.json").read_text(
            encoding="utf-8"
        )
    )
    _require(
        npm_producer["peerDependencies"].get("@agent-topology/spec")
        == versions["@agent-topology/spec"],
        "npm producer peer must select the candidate specification",
    )
    notes = _repository_path(candidate["releaseNotes"], "candidate.releaseNotes")
    guide = _repository_path(candidate["migrationGuide"], "candidate.migrationGuide")
    for path in (notes, guide):
        _require(
            "not published" in path.read_text(encoding="utf-8").lower(),
            f"{path.relative_to(ROOT)} must identify the candidate as not published",
        )
    _assert_install_versions(
        state["coordinatedPublished"],
        {
            "README.md": tuple(PACKAGE_LAYOUT),
            "docs/getting-started/python.md": ("agent-topology-langgraph",),
            "docs/getting-started/typescript.md": (
                "@agent-topology/spec",
                "@agent-topology/langgraph",
            ),
        },
    )


def check_phase(phase: str, *, state_path: Path = STATE_PATH) -> None:
    state = load_state(state_path)
    if phase == "candidate":
        check_candidate(state)
    elif phase == "published":
        _require(
            state.get("candidate") is None, "published phase requires candidate=null"
        )
        check_published(state)
    else:
        raise ReleaseDocsError(f"unknown phase: {phase}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("candidate", "published"))
    parser.add_argument("--state", type=Path, default=STATE_PATH)
    return parser


def main() -> None:
    args = _parser().parse_args()
    check_phase(args.phase, state_path=args.state)
    print(f"release documentation is coherent for phase={args.phase}")


if __name__ == "__main__":
    main()
