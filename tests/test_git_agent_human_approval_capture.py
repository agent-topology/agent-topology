from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CAPTURE = ROOT / "docs" / "research" / "internal-consumer" / "git-agent" / "capture"
FIXTURE = CAPTURE / "fixtures" / "human-approval-interrupt-resume"

EXPECTED_HASHES = {
    "trace.json": ("6d708fb804136de63f8a2b4effc72e5a5ecbf63977ba74d42564ec6496eb170b"),
    "expected.json": (
        "84d67b3195f698adca5240c194bc815465f873b2c322070f0c45874cc14d122a"
    ),
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def test_fixture_is_pinned_to_the_documented_commit() -> None:
    trace = _fixture("trace.json")
    assert trace["provenance"]["consumer"]["commit"] == (
        "b67cb35a6195609a5d89976768fb5a4884f17ca1"
    )
    assert trace["provenance"]["consumer"]["ref"] == "main"
    assert trace["provenance"]["consumer"]["repository"] == (
        "https://github.com/milocosmopolitan/git-agent"
    )


def test_fixture_hashes_match_the_recorded_generation() -> None:
    for name, expected_digest in EXPECTED_HASHES.items():
        digest = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        assert digest == expected_digest, f"{name} drifted from its recorded hash"


def test_real_human_approval_node_pauses_once_and_resumes_without_a_second_pause() -> (
    None
):
    trace = _fixture("trace.json")
    expected = _fixture("expected.json")

    first, second = trace["invocations"]
    assert first["paused"] is True
    assert first["pausedAtNodeId"] == "human_approval"
    assert second["paused"] is False

    assert expected["firstInvocationPaused"] is True
    assert expected["secondInvocationPaused"] is False
    assert expected["pausedAtNodeId"] == "human_approval"


def test_human_approval_node_body_re_executes_on_resume_as_two_step_occurrences() -> (
    None
):
    # A real, surprising effect worth evidencing rather than assumed (ADR
    # 0002: interrupts raised inside a node body do not appear in static node
    # metadata) -- and, per #181, for git-agent's actual node, not a stand-in.
    expected = _fixture("expected.json")
    assert expected["nodeReExecutedOnResume"] is True
    assert expected["humanApprovalStepOccurrences"] == [1, 2]
    assert expected["stepOccurrencesByNode"]["human_approval"] == [1, 2]


def test_static_call_site_logical_run_occurrence_and_invocation_stay_distinct() -> None:
    trace = _fixture("trace.json")
    run_ids = {event["runId"] for event in trace["events"]}
    invocation_run_ids = {event["invocationRunId"] for event in trace["events"]}
    node_ids = {event["nodeId"] for event in trace["events"]}

    assert run_ids == {"capture-thread-human-approval-1"}
    assert invocation_run_ids == {"invocation-1", "invocation-2"}
    assert "human_approval" in node_ids

    # every node other than human_approval occurs exactly once as a step;
    # human_approval alone occurs twice, once per invocation.
    for event in trace["events"]:
        if not event["eventType"].startswith("step."):
            continue
        if event["nodeId"] == "human_approval":
            assert event["nodeOccurrence"] in (1, 2)
        else:
            assert event["nodeOccurrence"] == 1


def test_retry_attempts_are_kept_separate_from_this_minimal_resume_case() -> None:
    # #194 owns the dedicated minimal repeat-attempt fixture; this capture
    # asserts it observed none, rather than silently conflating "no retry
    # happened" with "retries were not measured."
    expected = _fixture("expected.json")
    assert expected["retryAttemptsObserved"] == 0
    assert expected["attemptOccurrencesByNode"] == {
        "triage_failure": [1],
        "draft_status_report": [1],
    }


def test_no_missing_or_ambiguous_evidence_was_guessed() -> None:
    trace = _fixture("trace.json")
    expected = _fixture("expected.json")
    assert trace["provenance"]["unresolvedEvidence"] == []
    assert expected["unresolvedEvidence"] == []


def test_no_real_identifiers_credentials_or_payloads_entered_the_fixture() -> None:
    trace = _fixture("trace.json")
    serialized = json.dumps(
        {"events": trace["events"], "invocations": trace["invocations"]}
    )
    for forbidden in ("credential", "secret", "password", "prompt"):
        assert forbidden not in serialized.casefold()


def test_no_real_effect_occurred() -> None:
    trace = _fixture("trace.json")
    assert trace["finalOutcome"] == "red_reported"
    sanitization = " ".join(trace["provenance"]["sanitization"])
    assert "FakeGitHubIssueMutatePort" in sanitization


def test_offline_replay_needs_only_the_standard_library() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(CAPTURE / "replay.py"), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Node body re-executed on resume: True" in result.stdout
    assert "Acceptance assertions: PASS" in result.stdout
