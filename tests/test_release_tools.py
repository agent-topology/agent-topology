from pathlib import Path

import pytest

from scripts import release_guard, verify_python_artifacts


def _inspection() -> dict[str, object]:
    return {
        "artifacts": [
            {"filename": "agent_topology_spec-1.0.0.whl", "sha256": "abc"},
            {"filename": "agent_topology_spec-1.0.0.tar.gz", "sha256": "def"},
        ],
        "distribution": "agent-topology-spec",
        "package": "spec",
        "version": "1.0.0",
    }


def test_artifact_contents_are_derived_from_current_package_source(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "packages/python/langgraph/src/agent_topology/langgraph"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "_cli.py").write_text("", encoding="utf-8")
    cache_dir = package_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "_cli.pyc").write_bytes(b"generated")

    assert verify_python_artifacts._source_package_files(
        "langgraph", "langgraph", tmp_path
    ) == {"__init__.py", "_cli.py"}


def test_release_refuses_a_dirty_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_git(*args: str) -> str:
        return "commit" if args[0] == "rev-parse" else "?? untracked-file"

    monkeypatch.setattr(release_guard, "_git", fake_git)

    with pytest.raises(ValueError, match="dirty working tree"):
        release_guard.verify_worktree("commit")


def test_publish_allows_only_its_untracked_release_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = "\n".join(
        [
            "?? .release-bundle/dist/package.whl",
            "?? .release-bundle/release-receipt.json",
        ]
    )

    def fake_git(*args: str) -> str:
        return "commit" if args[0] == "rev-parse" else status

    monkeypatch.setattr(release_guard, "_git", fake_git)

    release_guard.verify_worktree(
        "commit", allowed_untracked_root=Path(".release-bundle")
    )

    status += "\n?? unrelated-file"
    with pytest.raises(ValueError, match="dirty working tree"):
        release_guard.verify_worktree(
            "commit", allowed_untracked_root=Path(".release-bundle")
        )


def test_release_refuses_missing_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        release_guard, "verify_worktree", lambda _commit, **_kwargs: None
    )

    with pytest.raises(ValueError, match="missing required checks"):
        release_guard.create_receipt(
            package="spec",
            version="1.0.0",
            dist_dir=Path("unused"),
            commit="commit",
            checks=[],
        )


def test_receipt_binds_package_version_commit_and_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        release_guard, "verify_worktree", lambda _commit, **_kwargs: None
    )
    monkeypatch.setattr(
        release_guard, "inspect_artifacts", lambda *_args, **_kwargs: _inspection()
    )
    checks = sorted(release_guard.required_checks("spec"))
    receipt = release_guard.create_receipt(
        package="spec",
        version="1.0.0",
        dist_dir=Path("unused"),
        commit="commit",
        checks=checks,
    )

    release_guard.check_receipt(
        receipt,
        package="spec",
        version="1.0.0",
        dist_dir=Path("unused"),
        commit="commit",
    )
    receipt["artifacts"][0]["sha256"] = "tampered"  # type: ignore[index]
    with pytest.raises(ValueError, match="does not match"):
        release_guard.check_receipt(
            receipt,
            package="spec",
            version="1.0.0",
            dist_dir=Path("unused"),
            commit="commit",
        )
