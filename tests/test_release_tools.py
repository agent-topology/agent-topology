import json
import re
import subprocess
from pathlib import Path

import pytest

from scripts import (
    check_release_source,
    release_guard,
    verify_python_artifacts,
    verify_spec_registry,
)


@pytest.mark.parametrize("ecosystem", ["python", "npm"])
@pytest.mark.parametrize("package", ["spec", "langgraph"])
def test_release_requires_prepared_version_and_release_branch(
    ecosystem: str,
    package: str,
) -> None:
    version = check_release_source.prepared_package(ecosystem, package)["version"]
    arguments = {
        "ref": "refs/heads/rc/0.1.0-beta.2",
        "spec_version": check_release_source.prepared_package("npm", "langgraph")[
            "peerDependencies"
        ]["@agent-topology/spec"],
    }
    check_release_source.validate_selection(ecosystem, package, version, **arguments)
    with pytest.raises(ValueError, match="differs from source"):
        check_release_source.validate_selection(
            ecosystem, package, "9.9.9", **arguments
        )
    for ref in (
        "",
        "refs/heads/main",
        "refs/heads/release/0.1.0-beta.2",
        "refs/tags/v0.1.0-beta.2",
        "refs/heads/rc/",
    ):
        with pytest.raises(ValueError, match="rc/<version>"):
            check_release_source.validate_selection(
                ecosystem, package, version, ref=ref
            )


def test_release_refuses_an_unprepared_spec_peer() -> None:
    with pytest.raises(ValueError, match="prepared peer"):
        check_release_source.validate_selection(
            "npm",
            "langgraph",
            check_release_source.prepared_package("npm", "langgraph")["version"],
            ref="refs/heads/rc/0.1.0-beta.2",
            spec_version="9.9.9",
        )


def test_resolve_producer_spec_version_accepts_the_prepared_source() -> None:
    spec_version = check_release_source.prepared_package("python", "spec")["version"]
    assert (
        check_release_source.resolve_producer_spec_version("langgraph") == spec_version
    )
    assert check_release_source.resolve_producer_spec_version("spec") == spec_version


def test_resolve_producer_spec_version_rejects_an_unsatisfied_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_prepared_package(ecosystem: str, package: str) -> dict:
        if package == "spec":
            return {"name": "agent-topology-spec", "version": "0.1.0b2"}
        return {
            "name": "agent-topology-langgraph",
            "dependencies": ["agent-topology-spec>=0.2.0,<0.4.0"],
        }

    monkeypatch.setattr(check_release_source, "prepared_package", fake_prepared_package)
    with pytest.raises(ValueError, match="does not satisfy"):
        check_release_source.resolve_producer_spec_version("langgraph")


@pytest.mark.parametrize(
    ("version", "specifier", "expected"),
    [
        ("0.1.0b2", ">=0.1.0b2,<0.2.0", True),
        ("0.1.0b1", ">=0.1.0b2,<0.2.0", False),
        ("0.2.0", ">=0.1.0b2,<0.2.0", False),
        ("0.1.0", ">=0.1.0b2,<0.2.0", True),
        ("1.2.11", ">=1.2.10,<=1.2.11", True),
        ("1.2.12", ">=1.2.10,<=1.2.11", False),
    ],
)
def test_satisfies_specifier_orders_prereleases_before_their_release(
    version: str, specifier: str, expected: bool
) -> None:
    assert check_release_source._satisfies_specifier(version, specifier) is expected


class _RecordingRunner:
    """A fake registry: scripted results per call, recording every command."""

    def __init__(self, results: list[subprocess.CompletedProcess]) -> None:
        self._results = list(results)
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess:
        self.commands.append(command)
        return self._results.pop(0)


def _completed(returncode: int, *, stdout: str = "", stderr: str = "") -> object:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_registry_preflight_installs_spec_before_the_producer_then_smokes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        verify_spec_registry, "resolve_producer_spec_version", lambda _pkg: "0.1.0b2"
    )
    runner = _RecordingRunner(
        [
            _completed(0),  # pip install spec pin
            _completed(0, stdout="0.1.0b2\n"),  # metadata check
            _completed(0),  # pip install producer wheel
            _completed(0),  # public smoke
        ]
    )
    wheel = tmp_path / "agent_topology_langgraph-0.1.0b2-py3-none-any.whl"

    verify_spec_registry.run_preflight("python", wheel, runner=runner)

    assert len(runner.commands) == 4
    assert runner.commands[0][:5] == [
        "uv",
        "pip",
        "install",
        "--python",
        "python",
    ]
    assert runner.commands[0][-1] == "agent-topology-spec==0.1.0b2"
    assert runner.commands[2][-1] == str(wheel)
    assert runner.commands[3][-1].endswith("scripts/smoke_langgraph_installation.py")


def test_registry_preflight_retries_a_not_yet_propagated_version_then_succeeds() -> (
    None
):
    """A "version not found" result right after publishing can be index lag,
    not rejection, so it is retried rather than treated as permanent."""
    sleeps: list[float] = []
    runner = _RecordingRunner(
        [
            _completed(
                1,
                stderr=(
                    "error: No solution found when resolving dependencies:\n"
                    "  Because there is no version of agent-topology-spec==0.1.0b2 "
                    "and you require agent-topology-spec==0.1.0b2, we can conclude "
                    "that your requirements are unsatisfiable."
                ),
            ),
            _completed(0),
        ]
    )

    verify_spec_registry.install_pinned_spec(
        "python", "0.1.0b2", runner=runner, sleep=sleeps.append
    )

    assert len(runner.commands) == 2
    assert sleeps == [2.0]


def test_registry_preflight_reports_a_persistently_missing_version() -> None:
    error = (
        "error: No solution found when resolving dependencies:\n"
        "  Because there is no version of agent-topology-spec==0.1.0b2 and you "
        "require agent-topology-spec==0.1.0b2, we can conclude that your "
        "requirements are unsatisfiable."
    )
    runner = _RecordingRunner([_completed(1, stderr=error) for _ in range(3)])

    with pytest.raises(RuntimeError, match="failed after 3 attempts") as excinfo:
        verify_spec_registry.install_pinned_spec(
            "python", "0.1.0b2", runner=runner, sleep=lambda _seconds: None
        )

    assert "no version of agent-topology-spec==0.1.0b2" in str(excinfo.value)
    assert len(runner.commands) == 3


def test_registry_preflight_reports_a_persistent_registry_failure() -> None:
    error = (
        "error: Request failed after 3 retries in 11.3s\n"
        "  Caused by: Failed to fetch: "
        "`https://pypi.org/simple/agent-topology-spec/`\n"
        "  Caused by: client error (Connect)\n"
        "  Caused by: dns error"
    )
    runner = _RecordingRunner([_completed(2, stderr=error) for _ in range(3)])

    with pytest.raises(RuntimeError, match="failed after 3 attempts") as excinfo:
        verify_spec_registry.install_pinned_spec(
            "python", "0.1.0b2", runner=runner, sleep=lambda _seconds: None
        )

    assert "dns error" in str(excinfo.value)
    assert len(runner.commands) == 3


def test_registry_preflight_rejects_incompatible_installed_metadata() -> None:
    runner = _RecordingRunner([_completed(0, stdout="0.1.0b1\n")])

    with pytest.raises(RuntimeError, match="incompatible metadata"):
        verify_spec_registry.verify_installed_spec_version(
            "python", "0.1.0b2", runner=runner
        )


def test_registry_preflight_never_touches_the_registry_for_an_unsatisfied_requirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_resolve(_package: str) -> str:
        raise ValueError("prepared agent-topology-spec version does not satisfy ...")

    monkeypatch.setattr(
        verify_spec_registry, "resolve_producer_spec_version", fake_resolve
    )
    runner = _RecordingRunner([])

    with pytest.raises(ValueError, match="does not satisfy"):
        verify_spec_registry.run_preflight(
            "python", tmp_path / "producer.whl", runner=runner
        )

    assert runner.commands == []


@pytest.mark.parametrize("name", ["release-python.yml", "release-npm.yml"])
def test_release_inputs_are_data_not_interpolated_shell(name: str) -> None:
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows" / name
    run_indent = None
    for line in workflow.read_text(encoding="utf-8").splitlines():
        indentation = len(line) - len(line.lstrip())
        if line.strip() and run_indent is not None and indentation <= run_indent:
            run_indent = None
        if re.match(r"\s*(?:- )?run:", line):
            run_indent = indentation
        if run_indent is not None:
            assert not re.search(
                r"\$\{\{\s*(?:inputs\.|github\.event\.inputs\.)", line
            ), (
                f"{name}: pass dispatch input through a quoted environment variable: "
                f"{line}"
            )


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


def test_prepared_lock_versions_match():
    check_release_source.check_version_copies()


@pytest.fixture
def version_fixture(tmp_path, monkeypatch):
    # Only four manifests and four tiny lockfiles; no source/dependency copies.
    for ecosystem in ("npm", "python"):
        for package, version in (("spec", "0.3.0"), ("langgraph", "0.7.0")):
            root = (
                tmp_path
                / "packages"
                / ("typescript" if ecosystem == "npm" else "python")
                / package
            )
            root.mkdir(parents=True)
            if ecosystem == "npm":
                manifest = {"name": f"@agent-topology/{package}", "version": version}
                if package == "langgraph":
                    manifest["peerDependencies"] = {"@agent-topology/spec": "0.3.0"}
                (root / "package.json").write_text(json.dumps(manifest))
                (root / "package-lock.json").write_text(
                    json.dumps(
                        {
                            "version": version,
                            "packages": {"": manifest, "../spec": {"version": "0.3.0"}},
                        }
                    )
                )
            else:
                (root / "pyproject.toml").write_text(
                    "[project]\n"
                    f'name = "agent-topology-{package}"\nversion = "{version}"\n'
                )
                (root / "uv.lock").write_text(
                    "[[package]]\n"
                    f'name = "agent-topology-{package}"\nversion = "{version}"\n'
                )
    monkeypatch.setattr(check_release_source, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize("ecosystem", ["npm", "python"])
@pytest.mark.parametrize("package", ["spec", "langgraph"])
def test_independent_bump_detects_missed_lock_copy(version_fixture, ecosystem, package):
    check_release_source.check_version_copies()
    root = (
        version_fixture
        / "packages"
        / ("typescript" if ecosystem == "npm" else "python")
        / package
    )
    manifest = root / ("package.json" if ecosystem == "npm" else "pyproject.toml")
    old = "0.3.0" if package == "spec" else "0.7.0"
    manifest.write_text(manifest.read_text().replace(old, "0.8.0"))
    with pytest.raises(ValueError, match="lock version differs"):
        check_release_source.check_version_copies()
    lock = root / ("package-lock.json" if ecosystem == "npm" else "uv.lock")
    lock.write_text(lock.read_text().replace(old, "0.8.0"))
    if ecosystem == "npm" and package == "spec":
        linked = version_fixture / "packages/typescript/langgraph/package-lock.json"
        data = json.loads(linked.read_text())
        data["packages"]["../spec"]["version"] = "0.8.0"
        linked.write_text(json.dumps(data))
    check_release_source.check_version_copies()
    check_release_source.validate_selection(
        ecosystem, package, "0.8.0", ref="refs/heads/rc/fixture", spec_version="0.3.0"
    )


def test_python_artifact_rejects_stale_dependency_bounds():
    with pytest.raises(ValueError, match="unexpected dependencies"):
        verify_python_artifacts._assert_metadata(
            {
                "Name": "agent-topology-langgraph",
                "Version": "0.7.0",
                "Requires-Python": ">=3.11,<3.15",
                "Requires-Dist": {"agent-topology-spec>=0.2.0,<0.4.0"},
            },
            distribution="agent-topology-langgraph",
            version="0.7.0",
            requirements={"agent-topology-spec>=0.3.0,<0.4.0"},
            archive=Path("fixture.whl"),
        )


@pytest.mark.parametrize(
    "name",
    [
        "python-packages.yml",
        "typescript-packages.yml",
        "release-npm.yml",
    ],
)
def test_workflows_do_not_copy_candidate_versions(name):
    workflow = check_release_source.ROOT / ".github/workflows" / name
    assert not re.search(r"--(?:spec-)?version\s+\d", workflow.read_text())
