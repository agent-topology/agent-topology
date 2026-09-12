"""Collect and verify public-registry evidence for a coordinated release."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import check_release_docs

ROOT = Path(__file__).resolve().parents[1]
FetchJson = Callable[[str], dict[str, Any]]
FetchBytes = Callable[[str], bytes]
Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class PublicReleaseError(RuntimeError):
    """Public release evidence is absent or disagrees with the frozen source."""


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json, application/vnd.pypi.integrity.v1+json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)


def _fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        return response.read()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublicReleaseError(message)


def _verify_hash(content: bytes, algorithm: str, expected: str, owner: str) -> None:
    actual = hashlib.new(algorithm, content).hexdigest()
    _require(actual == expected, f"{owner} {algorithm} digest mismatch")


def _verify_integrity(content: bytes, integrity: str, owner: str) -> None:
    algorithm, separator, encoded = integrity.partition("-")
    _require(
        bool(separator) and algorithm in hashlib.algorithms_available,
        "invalid integrity",
    )
    actual = base64.b64encode(hashlib.new(algorithm, content).digest()).decode()
    _require(actual == encoded, f"{owner} integrity mismatch")


def _pypi_evidence(
    name: str,
    version: str,
    *,
    fetch_json: FetchJson,
    fetch_bytes: FetchBytes,
) -> dict[str, Any]:
    metadata_url = f"https://pypi.org/pypi/{urllib.parse.quote(name)}/{version}/json"
    metadata = fetch_json(metadata_url)
    _require(
        metadata.get("info", {}).get("version") == version, f"missing {name}=={version}"
    )
    _require(not metadata.get("info", {}).get("yanked"), f"{name}=={version} is yanked")
    artifacts = []
    for artifact in metadata.get("urls", []):
        filename = artifact.get("filename")
        url = artifact.get("url")
        sha256 = artifact.get("digests", {}).get("sha256")
        _require(
            all(isinstance(value, str) for value in (filename, url, sha256)),
            "bad PyPI artifact",
        )
        content = fetch_bytes(url)
        _verify_hash(content, "sha256", sha256, filename)
        provenance_url = (
            "https://pypi.org/integrity/"
            f"{urllib.parse.quote(name)}/{version}/{urllib.parse.quote(filename)}"
            "/provenance"
        )
        provenance = fetch_json(provenance_url)
        _require(
            bool(provenance.get("attestation_bundles")),
            f"{filename} has no PyPI provenance",
        )
        artifacts.append(
            {
                "filename": filename,
                "url": url,
                "sha256": sha256,
                "provenanceUrl": provenance_url,
            }
        )
    _require(bool(artifacts), f"{name}=={version} has no public artifacts")
    return {
        "name": name,
        "version": version,
        "registry": "pypi",
        "metadataUrl": metadata_url,
        "artifacts": sorted(artifacts, key=lambda item: item["filename"]),
    }


def _npm_evidence(
    name: str,
    version: str,
    *,
    fetch_json: FetchJson,
    fetch_bytes: FetchBytes,
) -> dict[str, Any]:
    metadata_url = f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='')}"
    metadata = fetch_json(metadata_url)
    release = metadata.get("versions", {}).get(version)
    _require(isinstance(release, dict), f"missing {name}@{version}")
    _require(
        release.get("version") == version, f"registry returned wrong {name} version"
    )
    dist = release.get("dist", {})
    url = dist.get("tarball")
    sha1 = dist.get("shasum")
    integrity = dist.get("integrity")
    _require(
        all(isinstance(value, str) for value in (url, sha1, integrity)),
        "bad npm artifact",
    )
    content = fetch_bytes(url)
    _verify_hash(content, "sha1", sha1, f"{name}@{version}")
    _verify_integrity(content, integrity, f"{name}@{version}")
    attestations = dist.get("attestations", {})
    provenance_url = attestations.get("url")
    predicate = attestations.get("provenance", {}).get("predicateType")
    _require(
        isinstance(provenance_url, str)
        and predicate == "https://slsa.dev/provenance/v1",
        f"{name}@{version} has no SLSA provenance",
    )
    return {
        "name": name,
        "version": version,
        "registry": "npm",
        "metadataUrl": metadata_url,
        "artifacts": [
            {
                "filename": Path(urllib.parse.urlparse(url).path).name,
                "url": url,
                "sha1": sha1,
                "integrity": integrity,
                "provenanceUrl": provenance_url,
            }
        ],
    }


def _workflow_evidence(
    run_id: str,
    *,
    expected_commit: str,
    expected_branch: str,
    runner: Runner,
) -> str:
    _require(
        re.fullmatch(r"\d+", run_id) is not None, f"invalid workflow run id: {run_id}"
    )
    result = runner(
        [
            "gh",
            "run",
            "view",
            run_id,
            "--json",
            "headSha,headBranch,event,conclusion,url",
        ]
    )
    _require(result.returncode == 0, f"could not read workflow run {run_id}")
    run = json.loads(result.stdout)
    _require(run.get("headSha") == expected_commit, f"run {run_id} used another commit")
    _require(
        run.get("headBranch") == expected_branch, f"run {run_id} used another branch"
    )
    _require(run.get("event") == "workflow_dispatch", f"run {run_id} was not manual")
    _require(run.get("conclusion") == "success", f"run {run_id} did not succeed")
    url = run.get("url")
    _require(isinstance(url, str), f"run {run_id} has no URL")
    return url


def collect_evidence(
    candidate: dict[str, Any],
    *,
    source_commit: str,
    run_ids: dict[str, str],
    fetch_json: FetchJson = _fetch_json,
    fetch_bytes: FetchBytes = _fetch_bytes,
    runner: Runner = _run,
) -> dict[str, Any]:
    _require(re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None, "invalid commit")
    expected_branch = candidate["branch"]
    packages = []
    for package in candidate["packages"]:
        name = package["name"]
        _require(name in run_ids, f"missing qualification run for {name}")
        if package["ecosystem"] == "python":
            evidence = _pypi_evidence(
                name,
                package["version"],
                fetch_json=fetch_json,
                fetch_bytes=fetch_bytes,
            )
        else:
            evidence = _npm_evidence(
                name,
                package["version"],
                fetch_json=fetch_json,
                fetch_bytes=fetch_bytes,
            )
        evidence["workflowRun"] = _workflow_evidence(
            run_ids[name],
            expected_commit=source_commit,
            expected_branch=expected_branch,
            runner=runner,
        )
        packages.append(evidence)
    return {
        "schemaVersion": 1,
        "coordinatedVersion": candidate["coordinatedVersion"],
        "sourceCommit": source_commit,
        "tag": candidate["tag"],
        "registryVerifiedAt": datetime.now(UTC).isoformat(),
        "packages": packages,
    }


def _parse_runs(values: list[str]) -> dict[str, str]:
    runs: dict[str, str] = {}
    for value in values:
        name, separator, run_id = value.rpartition("=")
        _require(bool(separator) and name, f"invalid --run value: {value}")
        _require(name not in runs, f"duplicate --run for {name}")
        runs[name] = run_id
    return runs


def _find_release(state: dict[str, Any], version: str) -> dict[str, Any]:
    published = state["coordinatedPublished"]
    if published["coordinatedVersion"] == version:
        return published
    candidate = state.get("candidate")
    if candidate and candidate["coordinatedVersion"] == version:
        return candidate
    for partial in state["partialPublications"]:
        if partial["coordinatedVersion"] == version:
            return partial
    raise PublicReleaseError(f"{version} is not recorded in release state")


def verify_checked_evidence(
    release: dict[str, Any],
    evidence: dict[str, Any],
    *,
    fetch_json: FetchJson = _fetch_json,
    fetch_bytes: FetchBytes = _fetch_bytes,
) -> None:
    _require(evidence.get("schemaVersion") == 1, "unsupported evidence schema")
    fields = ["coordinatedVersion", "tag"]
    if release.get("sourceCommit") is not None:
        fields.append("sourceCommit")
    for field in fields:
        _require(
            evidence.get(field) == release.get(field), f"evidence {field} mismatch"
        )
    expected = {(item["name"], item["version"]) for item in release["packages"]}
    actual = {
        (item.get("name"), item.get("version")) for item in evidence.get("packages", [])
    }
    _require(actual == expected, "evidence package set mismatch")
    for recorded in evidence["packages"]:
        if recorded["registry"] == "pypi":
            current = _pypi_evidence(
                recorded["name"],
                recorded["version"],
                fetch_json=fetch_json,
                fetch_bytes=fetch_bytes,
            )
        else:
            current = _npm_evidence(
                recorded["name"],
                recorded["version"],
                fetch_json=fetch_json,
                fetch_bytes=fetch_bytes,
            )
        _require(
            current["artifacts"] == recorded["artifacts"],
            f"{recorded['name']} artifacts changed",
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--state", type=Path, default=check_release_docs.STATE_PATH)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    state = check_release_docs.load_state(args.state)
    release = _find_release(state, args.version)
    if args.command == "collect":
        _require(state.get("candidate") is release, "collect requires candidate state")
        _require(args.commit is not None, "collect requires --commit")
        _require(args.output is not None, "collect requires --output")
        evidence = collect_evidence(
            release,
            source_commit=args.commit,
            run_ids=_parse_runs(args.run),
        )
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        return
    _require(args.evidence is not None, "verify requires --evidence")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    verify_checked_evidence(release, evidence)


if __name__ == "__main__":
    main()
