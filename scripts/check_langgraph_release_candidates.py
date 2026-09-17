"""Detect stable PyPI LangGraph 1.3.x/1.4.x releases missing from the manifest.

This check only discovers and reports a gap between PyPI and the Python
producer's ``testedVersions`` compatibility manifest. See
``docs/reference/langgraph-version-policy.md`` for the qualification process;
this script never edits the manifest, opens an issue, or claims a reported
version is incompatible.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "langgraph"
CANDIDATE_MINORS = ("1.3", "1.4")
COMPATIBILITY_MANIFEST = (
    ROOT / "packages/python/langgraph/src/agent_topology/langgraph/_compatibility.json"
)

FetchJson = Callable[[str], dict[str, Any]]

# Covers only the plain `major.minor.patch` shape a stable, non-yanked PyPI
# release actually publishes under; any pre-release/dev/post suffix excludes it.
_STABLE_RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")


class RegistryQueryError(RuntimeError):
    """PyPI could not be queried; release status for the candidate set is unknown."""


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise RegistryQueryError(f"failed to query {url}: {error}") from error


def _is_candidate_minor(version: str) -> bool:
    return any(
        version == minor or version.startswith(f"{minor}.")
        for minor in CANDIDATE_MINORS
    )


def _is_yanked(files: list[dict[str, Any]]) -> bool:
    return bool(files) and all(file.get("yanked", False) for file in files)


def _upload_time(files: list[dict[str, Any]]) -> str:
    times = sorted(
        file["upload_time_iso_8601"]
        for file in files
        if file.get("upload_time_iso_8601")
    )
    return times[0] if times else ""


def candidate_releases(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Stable, non-yanked 1.3.x/1.4.x PyPI releases, oldest upload first."""
    releases = payload.get("releases", {})
    candidates = [
        {
            "version": version,
            "uploadTime": _upload_time(files),
            "url": f"https://pypi.org/project/{PACKAGE_NAME}/{version}/",
        }
        for version, files in releases.items()
        if _STABLE_RELEASE_RE.match(version)
        and _is_candidate_minor(version)
        and not _is_yanked(files)
    ]
    return sorted(
        candidates, key=lambda release: (release["uploadTime"], release["version"])
    )


def tested_versions(manifest_path: Path = COMPATIBILITY_MANIFEST) -> set[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return set(manifest["testedVersions"])


def find_missing_releases(
    *,
    fetch_json: FetchJson = _fetch_json,
    manifest_path: Path = COMPATIBILITY_MANIFEST,
) -> list[dict[str, str]]:
    """Candidate releases that are not in the manifest's ``testedVersions``."""
    payload = fetch_json(f"https://pypi.org/pypi/{PACKAGE_NAME}/json")
    tested = tested_versions(manifest_path)
    return [
        release
        for release in candidate_releases(payload)
        if release["version"] not in tested
    ]


def render_summary(missing: list[dict[str, str]]) -> str:
    if not missing:
        return (
            "## LangGraph 1.3.x/1.4.x release check\n\n"
            "No stable, non-yanked PyPI release is missing from "
            "`testedVersions`.\n"
        )
    lines = [
        "## LangGraph 1.3.x/1.4.x release check",
        "",
        f"{len(missing)} stable PyPI release(s) are not yet in `testedVersions`. "
        "This check only reports the gap: it does not edit the compatibility "
        "manifest, open an issue, or determine whether the release is "
        "compatible. See the LangGraph version-range expansion policy for the "
        "qualification process.",
        "",
        "| Version | Uploaded | PyPI |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| {release['version']} | {release['uploadTime']} | {release['url']} |"
        for release in missing
    )
    lines.append("")
    return "\n".join(lines)


def _render_registry_failure(error: RegistryQueryError) -> str:
    return (
        "## LangGraph 1.3.x/1.4.x release check\n\n"
        f"The PyPI registry query failed, so release status is unknown: {error}\n"
    )


def _write_summary(text: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(text)
    else:
        print(text)


def run() -> None:
    try:
        missing = find_missing_releases()
    except RegistryQueryError as error:
        _write_summary(_render_registry_failure(error))
        raise SystemExit(str(error)) from error

    _write_summary(render_summary(missing))
    if missing:
        raise SystemExit(
            f"{len(missing)} stable LangGraph release(s) missing from testedVersions"
        )


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()


if __name__ == "__main__":
    main()
