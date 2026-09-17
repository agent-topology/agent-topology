from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CAPTURE = ROOT / "docs" / "research" / "internal-consumer" / "git-agent" / "capture"
FIXTURE = CAPTURE / "fixtures" / "repeat-attempt"

EXPECTED_HASHES = {
    "trace.json": ("8b11e14d0c05d43968686bd1e090429c11636f0a12dc765816a859859f3fd7c0"),
    "expected.json": (
        "9b434c7bfcbfe85c6be7bf077c241d830ebcade6d10fbb2a8dbfc6fe75afc6e8"
    ),
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def test_fixture_hashes_match_the_recorded_generation() -> None:
    for name, expected_digest in EXPECTED_HASHES.items():
        digest = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        assert digest == expected_digest, f"{name} drifted from its recorded hash"


def test_fixture_is_synthetic_and_needs_no_consumer_checkout() -> None:
    # #181: "do not grow the full campaign/git-agent input to test retry
    # mechanics." This fixture pins no external consumer commit -- it is
    # built only against langgraph, already a direct dependency of this
    # repo's own packages/python/langgraph package.
    trace = _fixture("trace.json")
    assert trace["provenance"]["consumer"] is None
    assert trace["provenance"]["framework"]["name"] == "langgraph"


def test_single_invocation_no_pause_no_resume() -> None:
    trace = _fixture("trace.json")
    expected = _fixture("expected.json")

    assert len(trace["invocations"]) == 1
    (invocation,) = trace["invocations"]
    assert invocation["paused"] is False
    assert invocation["pausedAtNodeId"] is None

    assert expected["paused"] is False
    assert expected["distinctInvocationRunIds"] == ["invocation-1"]
    assert "__interrupt__" not in json.dumps(trace)


def test_retry_attempt_stays_within_one_invocation_and_one_step_occurrence() -> None:
    # The fact this fixture exists to prove: a node's Nth *attempt*
    # (attemptNumber) is a different counter than its Nth *step*
    # (nodeOccurrence) -- one real step that required two attempts is one
    # occurrence, not two.
    trace = _fixture("trace.json")
    expected = _fixture("expected.json")

    attempt_events = [
        e for e in trace["events"] if e["eventType"].startswith("attempt.")
    ]
    step_events = [e for e in trace["events"] if e["eventType"].startswith("step.")]

    assert [e["metadata"]["attemptNumber"] for e in attempt_events] == [1, 2]
    assert [e["eventType"] for e in attempt_events] == [
        "attempt.failed",
        "attempt.passed",
    ]
    assert {e["nodeId"] for e in attempt_events} == {"flaky_step"}

    assert [e["nodeOccurrence"] for e in step_events] == [1]
    assert {e["nodeId"] for e in step_events} == {"flaky_step"}

    assert expected["retryAttemptsObserved"] == 1
    assert expected["repeatedWithinSingleInvocation"] is True
    assert expected["stepOccurrencesByNode"] == {"flaky_step": [1]}
    assert expected["attemptOccurrencesByNode"] == {"flaky_step": [1, 2]}


def test_static_call_site_logical_run_occurrence_and_invocation_stay_distinct() -> None:
    # Mirrors tests/test_git_agent_human_approval_capture.py's identically
    # named assertion (#191): the same four fields stay independently
    # addressable here, just with the retry axis varying instead of the
    # invocation axis.
    trace = _fixture("trace.json")
    run_ids = {event["runId"] for event in trace["events"]}
    invocation_run_ids = {event["invocationRunId"] for event in trace["events"]}
    node_ids = {event["nodeId"] for event in trace["events"]}

    assert run_ids == {"capture-thread-repeat-attempt-1"}
    assert invocation_run_ids == {"invocation-1"}
    assert node_ids == {"flaky_step"}


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


def test_offline_replay_needs_only_the_standard_library() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(CAPTURE / "replay_repeat_attempt.py"),
            "--check",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Retry attempts observed: 1" in result.stdout
    assert "Acceptance assertions: PASS" in result.stdout
