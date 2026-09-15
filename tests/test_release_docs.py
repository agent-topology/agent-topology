from __future__ import annotations

import base64
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import check_release_docs, check_release_issue, verify_public_release


def _state() -> dict:
    return copy.deepcopy(check_release_docs.load_state())


def test_current_release_state_is_published_and_coherent() -> None:
    # check_published also asserts package READMEs select the published
    # version, which a prepared candidate (see the next test) deliberately
    # moves ahead of; that invariant intentionally pauses while a candidate
    # is active and resumes once its closeout PR clears it back to null.
    state = check_release_docs.load_state()
    if state.get("candidate") is not None:
        pytest.skip("an active candidate pauses full published-phase coherence")
    check_release_docs.check_phase("published")


def test_current_release_state_has_a_coherent_candidate() -> None:
    check_release_docs.check_phase("candidate")


def test_finalization_stage_uses_closeout_source_and_binds_qualified_commit() -> None:
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/release-finalize.yml"
    ).read_text(encoding="utf-8")
    stage = workflow.split("\n  complete:\n", maxsplit=1)[0]

    assert "ref: main" in stage
    assert "ref: ${{ inputs.qualified-commit }}" not in stage
    assert "QUALIFIED_COMMIT: ${{ inputs.qualified-commit }}" in stage
    assert '--commit "$QUALIFIED_COMMIT"' in stage
    workflow_verification = stage.split(
        "- name: Verify public artifacts and bind their workflow runs", maxsplit=1
    )[1].split("- name:", maxsplit=1)[0]
    assert "GH_TOKEN: ${{ github.token }}" in workflow_verification


def test_finalization_complete_accepts_an_already_public_prerelease() -> None:
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/release-finalize.yml"
    ).read_text(encoding="utf-8")
    complete = workflow.split("\n  complete:\n", maxsplit=1)[1]

    assert "--json isDraft,isPrerelease" in complete
    assert "test \"$(jq -r '.isPrerelease'" in complete
    assert "if [ \"$(jq -r '.isDraft'" in complete


def test_beta3_evidence_retains_receipts_and_cross_language_f8_replay() -> None:
    evidence_path = (
        Path(__file__).resolve().parents[1]
        / "docs/releases/evidence/v0.1.0-beta.3.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    receipt_verification = evidence["qualificationReceiptVerification"]
    assert receipt_verification["sourceCommit"] == evidence["sourceCommit"]
    assert "no rebuild difference" in receipt_verification["outcome"]
    assert {receipt["package"] for receipt in receipt_verification["receipts"]} == {
        package["name"] for package in evidence["packages"]
    }

    replay = evidence["f8RegistryReplay"]
    assert replay["input"]["x-numeric"][0:2] == [0.0, -0.0]
    results = {result["package"]: result for result in replay["results"]}
    assert set(results) == {"agent-topology-spec", "@agent-topology/spec"}
    assert all(result["inputAccepted"] is True for result in results.values())
    assert len({result["canonicalBytes"] for result in results.values()}) == 1
    assert (
        len(
            {
                json.dumps(result["structureHash"], sort_keys=True)
                for result in results.values()
            }
        )
        == 1
    )
    assert results["agent-topology-spec"]["version"] == "0.1.0b3"
    assert results["@agent-topology/spec"]["version"] == "0.1.0-beta.3"


def test_candidate_phase_requires_explicit_candidate(tmp_path: Path) -> None:
    state = _state()
    state["candidate"] = None
    path = tmp_path / "release-state.json"
    path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(
        check_release_docs.ReleaseDocsError,
        match="candidate phase requires candidate release state",
    ):
        check_release_docs.check_phase("candidate", state_path=path)


def test_release_state_rejects_duplicate_package(tmp_path: Path) -> None:
    state = _state()
    packages = state["coordinatedPublished"]["packages"]
    packages[-1] = copy.deepcopy(packages[0])
    path = tmp_path / "release-state.json"
    path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(check_release_docs.ReleaseDocsError, match="duplicates package"):
        check_release_docs.load_state(path)


def test_release_states_cannot_overlap(tmp_path: Path) -> None:
    state = _state()
    candidate = copy.deepcopy(state["coordinatedPublished"])
    candidate["branch"] = "rc/0.1.0-beta.2"
    state["candidate"] = candidate
    path = tmp_path / "release-state.json"
    path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(
        check_release_docs.ReleaseDocsError, match="must not overlap states"
    ):
        check_release_docs.load_state(path)


def test_new_published_release_requires_closeout_evidence() -> None:
    state = _state()
    published = copy.deepcopy(state["coordinatedPublished"])
    published.pop("sourceCommit")
    state["coordinatedPublished"] = published
    state["candidate"] = None
    state["partialPublications"] = []

    with pytest.raises(
        check_release_docs.ReleaseDocsError,
        match="published closeout requires a full sourceCommit",
    ):
        check_release_docs.check_published(state)


def test_install_checks_use_each_independent_package_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_release_docs, "ROOT", tmp_path)
    document = tmp_path / "install.md"
    release = {
        "packages": [
            {
                "name": "agent-topology-spec",
                "ecosystem": "python",
                "version": "0.1.0b7",
            },
            {
                "name": "agent-topology-langgraph",
                "ecosystem": "python",
                "version": "0.1.0b8",
            },
            {
                "name": "@agent-topology/spec",
                "ecosystem": "npm",
                "version": "0.1.0-beta.9",
            },
            {
                "name": "@agent-topology/langgraph",
                "ecosystem": "npm",
                "version": "0.1.0-beta.10",
            },
        ]
    }
    document.write_text(
        "agent-topology-spec==0.1.0b7\n"
        "agent-topology-langgraph==0.1.0b8\n"
        "@agent-topology/spec@0.1.0-beta.9\n"
        "@agent-topology/langgraph@0.1.0-beta.10\n",
        encoding="utf-8",
    )

    check_release_docs._assert_install_versions(  # noqa: SLF001
        release, {"install.md": tuple(check_release_docs.PACKAGE_LAYOUT)}
    )


def test_candidate_accepts_candidate_docs_and_current_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state()
    # `_read_manifest_version` resolves PACKAGE_LAYOUT paths, which were bound
    # to the real repository root at import time and are unaffected by the
    # ROOT monkeypatch below, so this candidate must match the real,
    # currently-prepared source manifests rather than an arbitrary version.
    candidate = copy.deepcopy(state["candidate"])
    state["candidate"] = candidate
    candidate_doc = tmp_path / "candidate.md"
    candidate_doc.write_text("Prepared in source; not published.", encoding="utf-8")
    python_producer = tmp_path / "packages/python/langgraph"
    python_producer.mkdir(parents=True)
    (python_producer / "pyproject.toml").write_text(
        '[project]\ndependencies = ["agent-topology-spec>=0.1.0b4,<0.2.0"]\n',
        encoding="utf-8",
    )
    npm_producer = tmp_path / "packages/typescript/langgraph"
    npm_producer.mkdir(parents=True)
    (npm_producer / "package.json").write_text(
        json.dumps({"peerDependencies": {"@agent-topology/spec": "0.1.0-beta.4"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(check_release_docs, "ROOT", tmp_path)
    monkeypatch.setattr(
        check_release_docs,
        "PACKAGE_READMES",
        {
            name: tmp_path / f"{index}.md"
            for index, name in enumerate(check_release_docs.PACKAGE_LAYOUT)
        },
    )
    monkeypatch.setattr(
        check_release_docs,
        "_assert_install_versions",
        lambda _release, _documents: None,
    )
    monkeypatch.setattr(
        check_release_docs,
        "_repository_path",
        lambda _value, _field: candidate_doc,
    )

    check_release_docs.check_candidate(state)


def _issue_event(body: str, *, state_reason: str = "completed") -> dict:
    return {
        "issue": {
            "body": body,
            "labels": [{"name": "area:release"}],
            "state_reason": state_reason,
        }
    }


def test_completed_release_issue_requires_finished_checklist() -> None:
    missing = check_release_issue.closure_violation(
        _issue_event("## Done when\n\n- [x] qualified\n- [ ] closeout merged")
    )
    assert missing == ["closeout merged"]


def test_completed_release_issue_requires_a_checklist() -> None:
    assert check_release_issue.closure_violation(_issue_event("## Outcome\nDone")) == [
        "at least one acceptance checkbox"
    ]


def test_completed_release_issue_accepts_finished_checklist() -> None:
    assert (
        check_release_issue.closure_violation(
            _issue_event("## Done when\n\n- [x] qualified\n- [X] closeout merged")
        )
        == []
    )


def test_not_planned_release_issue_requires_partial_outcome_and_successor() -> None:
    assert check_release_issue.closure_violation(
        _issue_event(
            "## Partial outcome\nArtifacts retained.", state_reason="not_planned"
        )
    ) == ["a successor issue link"]
    assert (
        check_release_issue.closure_violation(
            _issue_event(
                "## Partial outcome\nArtifacts retained; superseded by #200.",
                state_reason="not_planned",
            )
        )
        == []
    )
    unrelated = "See #100.\n\n## Partial outcome\nArtifacts retained."
    assert check_release_issue.closure_violation(
        _issue_event(unrelated, state_reason="not_planned")
    ) == ["a successor issue link"]


def test_non_release_issue_is_not_governed() -> None:
    event = _issue_event("- [ ] unfinished")
    event["issue"]["labels"] = [{"name": "area:docs"}]
    assert check_release_issue.closure_violation(event) == []


def test_public_evidence_binds_registry_digests_and_workflow_runs() -> None:
    content = b"qualified artifact"
    sha256 = hashlib.sha256(content).hexdigest()
    sha1 = hashlib.sha1(content).hexdigest()
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(content).digest()).decode()
    candidate = {
        "coordinatedVersion": "0.1.0-beta.4",
        "tag": "v0.1.0-beta.4",
        "branch": "rc/0.1.0-beta.4",
        "packages": [
            {"name": name, "ecosystem": ecosystem, "version": version}
            for name, ecosystem, version in (
                ("agent-topology-spec", "python", "0.1.0b4"),
                ("agent-topology-langgraph", "python", "0.1.0b4"),
                ("@agent-topology/spec", "npm", "0.1.0-beta.4"),
                ("@agent-topology/langgraph", "npm", "0.1.0-beta.4"),
            )
        ],
    }

    def fetch_json(url: str) -> dict:
        if url.endswith("/provenance"):
            return {"attestation_bundles": [{"publisher": {"kind": "GitHub"}}]}
        if "pypi.org" in url:
            name = (
                "agent-topology-langgraph"
                if "langgraph" in url
                else "agent-topology-spec"
            )
            version = "0.1.0b4"
            return {
                "info": {"version": version, "yanked": False},
                "urls": [
                    {
                        "filename": f"{name}-{version}.whl",
                        "url": f"https://files.example/{name}.whl",
                        "digests": {"sha256": sha256},
                    }
                ],
            }
        name = (
            "@agent-topology/langgraph"
            if "langgraph" in url
            else "@agent-topology/spec"
        )
        return {
            "versions": {
                "0.1.0-beta.4": {
                    "version": "0.1.0-beta.4",
                    "dist": {
                        "tarball": f"https://registry.example/{name}.tgz",
                        "shasum": sha1,
                        "integrity": integrity,
                        "attestations": {
                            "url": f"https://registry.example/attestations/{name}",
                            "provenance": {
                                "predicateType": "https://slsa.dev/provenance/v1"
                            },
                        },
                    },
                }
            }
        }

    commit = "a" * 40

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        run_id = command[3]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "headSha": commit,
                    "headBranch": "rc/0.1.0-beta.4",
                    "event": "workflow_dispatch",
                    "conclusion": "success",
                    "url": f"https://github.example/actions/runs/{run_id}",
                }
            ),
        )

    evidence = verify_public_release.collect_evidence(
        candidate,
        source_commit=commit,
        run_ids={
            package["name"]: str(index)
            for index, package in enumerate(candidate["packages"], 1)
        },
        fetch_json=fetch_json,
        fetch_bytes=lambda _url: content,
        runner=runner,
    )
    npm_artifact = next(
        package["artifacts"][0]
        for package in evidence["packages"]
        if package["name"] == "@agent-topology/spec"
    )
    assert npm_artifact["sha256"] == hashlib.sha256(content).hexdigest()

    assert evidence["sourceCommit"] == commit
    assert {package["name"] for package in evidence["packages"]} == {
        package["name"] for package in candidate["packages"]
    }
    assert all(package["workflowRun"] for package in evidence["packages"])


def test_public_evidence_rejects_registry_digest_mismatch() -> None:
    metadata = {
        "info": {"version": "0.1.0b4", "yanked": False},
        "urls": [
            {
                "filename": "package.whl",
                "url": "https://files.example/package.whl",
                "digests": {"sha256": "0" * 64},
            }
        ],
    }

    with pytest.raises(
        verify_public_release.PublicReleaseError, match="digest mismatch"
    ):
        verify_public_release._pypi_evidence(  # noqa: SLF001
            "agent-topology-spec",
            "0.1.0b4",
            fetch_json=lambda _url: metadata,
            fetch_bytes=lambda _url: b"different",
        )


@pytest.mark.parametrize("name", ["release-python.yml", "release-npm.yml"])
def test_package_release_workflows_require_candidate_documentation(name: str) -> None:
    workflow = (check_release_docs.ROOT / ".github" / "workflows" / name).read_text(
        encoding="utf-8"
    )
    assert "scripts/check_release_docs.py --phase candidate" in workflow


def test_finalization_stages_a_draft_before_published_closeout() -> None:
    workflow = (
        check_release_docs.ROOT / ".github/workflows/release-finalize.yml"
    ).read_text(encoding="utf-8")
    assert "scripts/check_release_docs.py --phase candidate" in workflow
    assert "scripts/check_release_docs.py --phase published" in workflow
    assert "--draft --prerelease" in workflow
    assert "--draft=false --prerelease" in workflow
    assert workflow.index("--draft --prerelease") < workflow.index(
        "--draft=false --prerelease"
    )


def test_issue_close_workflow_can_reopen_but_not_modify_contents() -> None:
    workflow = (
        check_release_docs.ROOT / ".github/workflows/release-issue-close.yml"
    ).read_text(encoding="utf-8")
    assert "issues: write" in workflow
    assert "contents: read" in workflow
    assert 'gh issue reopen "$ISSUE_NUMBER"' in workflow
    assert "check_release_issue.py" in workflow
