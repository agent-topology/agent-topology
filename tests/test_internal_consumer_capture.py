from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CAPTURE = (
    ROOT / "docs" / "research" / "internal-consumer" / "agent-workflow-core" / "capture"
)

EXPECTED_HASHES = {
    "fixtures/tag-v0.1.0.beta.3/expected.json": (
        "0798b78dcdcc0d0a254f17126222ea9be1bf51050d001c7f5a18adf070fa8e93"
    ),
    "fixtures/tag-v0.1.0.beta.3/trace.json": (
        "a78752b1df9fd40494e0d95c8827fbc3c4ad3fc3511bad09c7522c1a40dcfc29"
    ),
    "fixtures/main-876f6a8a/expected.json": (
        "96c299c3eaba8e8557903c37fef7e7cf3f67aba9376ee8ca9972e072d82a5a7c"
    ),
    "fixtures/main-876f6a8a/trace.json": (
        "a46818476423d39cd9929ceb8e325bd7bc389aef3f9131fca8960b67820e29e9"
    ),
    "fixtures/commits.json": (
        "8131afc336233c7cf477410520e6231c5aa8af5b7ff0f69111264e246a469d9b"
    ),
}


def _fixture(relative: str) -> dict:
    return json.loads((CAPTURE / relative).read_text(encoding="utf-8"))


def test_fixtures_are_pinned_to_the_documented_commits() -> None:
    commits = _fixture("fixtures/commits.json")
    assert commits["scenarios"]["tag"]["commit"] == (
        "94cd31f58d8e94d55ea2d952c6db5508539ea53f"
    )
    assert commits["scenarios"]["tag"]["ref"] == "v0.1.0.beta.3"
    assert commits["scenarios"]["main"]["commit"] == (
        "876f6a8a4ba863424e1f85bc92f18dce59147957"
    )
    assert commits["packageVersionBothCommitsReport"] == "0.1.0b3"


def test_fixture_hashes_match_the_recorded_generation() -> None:
    for relative, expected_digest in EXPECTED_HASHES.items():
        digest = hashlib.sha256((CAPTURE / relative).read_bytes()).hexdigest()
        assert digest == expected_digest, f"{relative} drifted from its recorded hash"


def test_tag_scenario_has_no_resume_identity() -> None:
    trace = _fixture("fixtures/tag-v0.1.0.beta.3/trace.json")
    expected = _fixture("fixtures/tag-v0.1.0.beta.3/expected.json")

    assert trace["provenance"]["consumer"]["commit"] == (
        "94cd31f58d8e94d55ea2d952c6db5508539ea53f"
    )
    run_ids = {event["runId"] for event in trace["events"]}
    assert run_ids == {"invocation-1", "invocation-2"}
    assert expected["resumeIdentityPreserved"] is False


def test_main_scenario_preserves_resume_identity_via_event_run_id() -> None:
    trace = _fixture("fixtures/main-876f6a8a/trace.json")
    expected = _fixture("fixtures/main-876f6a8a/expected.json")

    assert trace["provenance"]["consumer"]["commit"] == (
        "876f6a8a4ba863424e1f85bc92f18dce59147957"
    )
    run_ids = {event["runId"] for event in trace["events"]}
    assert run_ids == {"logical-run"}
    assert expected["resumeIdentityPreserved"] is True


def test_no_real_identifiers_or_payloads_entered_the_fixtures() -> None:
    for relative in (
        "fixtures/tag-v0.1.0.beta.3/trace.json",
        "fixtures/main-876f6a8a/trace.json",
    ):
        trace = _fixture(relative)
        for event in trace["events"]:
            assert set(event) == {"sequence", "eventType", "graphId", "runId", "nodeId"}
        for invocation in trace["invocations"]:
            assert invocation["run_id"] in {"invocation-1", "invocation-2"}


def test_offline_replay_needs_only_the_standard_library() -> None:
    for scenario, expect_preserved in (("tag", "False"), ("main", "True")):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                str(CAPTURE / "replay.py"),
                "--scenario",
                scenario,
                "--check",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert (
            f"Resume identity preserved across invocations: {expect_preserved}"
            in result.stdout
        )
        assert "Acceptance assertions: PASS" in result.stdout
