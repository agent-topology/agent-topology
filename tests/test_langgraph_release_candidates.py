from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from scripts import check_langgraph_release_candidates as check


def _manifest(tmp_path: Path, tested: list[str]) -> Path:
    path = tmp_path / "_compatibility.json"
    path.write_text(
        json.dumps({"metadataSpecifier": "", "testedVersions": tested}),
        encoding="utf-8",
    )
    return path


def _release(
    *, yanked: bool = False, uploaded: str = "2026-01-05T00:00:00"
) -> list[dict]:
    return [
        {
            "filename": "langgraph.tar.gz",
            "yanked": yanked,
            "upload_time_iso_8601": uploaded,
        }
    ]


def test_empty_candidate_set_is_a_successful_result(tmp_path: Path) -> None:
    payload = {"releases": {"1.2.10": _release(), "1.2.11": _release()}}
    missing = check.find_missing_releases(
        fetch_json=lambda _url: payload,
        manifest_path=_manifest(tmp_path, ["1.2.10", "1.2.11"]),
    )
    assert missing == []
    assert "No stable, non-yanked PyPI release is missing" in check.render_summary(
        missing
    )


def test_new_stable_release_is_reported_with_upload_time_and_url(
    tmp_path: Path,
) -> None:
    payload = {
        "releases": {
            "1.2.10": _release(),
            "1.3.0": _release(uploaded="2026-02-01T00:00:00"),
        }
    }
    missing = check.find_missing_releases(
        fetch_json=lambda _url: payload,
        manifest_path=_manifest(tmp_path, ["1.2.10"]),
    )
    assert missing == [
        {
            "version": "1.3.0",
            "uploadTime": "2026-02-01T00:00:00",
            "url": "https://pypi.org/project/langgraph/1.3.0/",
        }
    ]
    summary = check.render_summary(missing)
    assert "1.3.0" in summary
    assert "2026-02-01T00:00:00" in summary
    assert "https://pypi.org/project/langgraph/1.3.0/" in summary


def test_prerelease_and_dev_versions_are_excluded_from_candidates(
    tmp_path: Path,
) -> None:
    payload = {
        "releases": {
            "1.3.0rc1": _release(),
            "1.3.0.dev0": _release(),
            "1.4.0a1": _release(),
        }
    }
    missing = check.find_missing_releases(
        fetch_json=lambda _url: payload,
        manifest_path=_manifest(tmp_path, []),
    )
    assert missing == []


def test_yanked_release_is_excluded_from_candidates(tmp_path: Path) -> None:
    payload = {"releases": {"1.4.0": _release(yanked=True)}}
    missing = check.find_missing_releases(
        fetch_json=lambda _url: payload,
        manifest_path=_manifest(tmp_path, []),
    )
    assert missing == []


def test_finding_missing_releases_does_not_modify_the_manifest(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path, ["1.2.10"])
    before = manifest_path.read_text(encoding="utf-8")
    payload = {"releases": {"1.3.0": _release()}}
    check.find_missing_releases(
        fetch_json=lambda _url: payload, manifest_path=manifest_path
    )
    assert manifest_path.read_text(encoding="utf-8") == before


def test_registry_query_failure_is_a_distinct_error_from_a_missing_release() -> None:
    def fetch_json(_url: str) -> dict:
        raise check.RegistryQueryError("boom")

    with pytest.raises(check.RegistryQueryError):
        check.find_missing_releases(fetch_json=fetch_json)


def test_default_fetcher_wraps_a_network_failure_as_a_registry_query_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def urlopen(_request, timeout: float) -> None:  # noqa: ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(check.urllib.request, "urlopen", urlopen)
    with pytest.raises(check.RegistryQueryError):
        check._fetch_json("https://pypi.org/pypi/langgraph/json")  # noqa: SLF001


def test_run_succeeds_without_raising_when_nothing_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(check, "find_missing_releases", lambda: [])
    check.run()
    assert "No stable, non-yanked PyPI release is missing" in summary.read_text(
        encoding="utf-8"
    )


def test_run_fails_visibly_and_lists_the_missing_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    missing = [
        {
            "version": "1.3.0",
            "uploadTime": "2026-02-01T00:00:00",
            "url": "https://pypi.org/project/langgraph/1.3.0/",
        }
    ]
    monkeypatch.setattr(check, "find_missing_releases", lambda: missing)
    with pytest.raises(SystemExit):
        check.run()
    text = summary.read_text(encoding="utf-8")
    assert "1.3.0" in text
    assert "does not edit the compatibility manifest" in text


def test_run_reports_a_registry_failure_distinctly_from_a_missing_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    def fail() -> list[dict]:
        raise check.RegistryQueryError("network unreachable")

    monkeypatch.setattr(check, "find_missing_releases", fail)
    with pytest.raises(SystemExit):
        check.run()
    text = summary.read_text(encoding="utf-8")
    assert "registry query failed" in text.lower()
    assert "| Version |" not in text
