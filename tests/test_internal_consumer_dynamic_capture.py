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
    "fixtures/interrupt-resume/expected.json": (
        "732f9d8cefbbc7bffee83a058e679f067eac8a650dbb42d4d031e225abe77705"
    ),
    "fixtures/interrupt-resume/trace.json": (
        "08de54ace84c3f17c137172a36e72f5c89d44dfe95eeed3c697c08a316fd000a"
    ),
    "fixtures/repeated-attempt/expected.json": (
        "bad52bea3208381f54afa95c81c2d1c076e6c8d8d7c6eb607e28254cddbc5685"
    ),
    "fixtures/repeated-attempt/trace.json": (
        "249bf3cc808f0466fa8887d876ad9e0a04fd7891dd65ad35e37033c9b0ffa934"
    ),
}


def _fixture(relative: str) -> dict:
    return json.loads((CAPTURE / relative).read_text(encoding="utf-8"))


def test_fixtures_are_pinned_to_the_documented_main_commit() -> None:
    for relative in (
        "fixtures/interrupt-resume/trace.json",
        "fixtures/repeated-attempt/trace.json",
    ):
        trace = _fixture(relative)
        assert trace["provenance"]["consumer"]["commit"] == (
            "876f6a8a4ba863424e1f85bc92f18dce59147957"
        )
        assert trace["provenance"]["consumer"]["ref"] == "main"


def test_fixture_hashes_match_the_recorded_generation() -> None:
    for relative, expected_digest in EXPECTED_HASHES.items():
        digest = hashlib.sha256((CAPTURE / relative).read_bytes()).hexdigest()
        assert digest == expected_digest, f"{relative} drifted from its recorded hash"


def test_interrupt_resume_pauses_once_and_resumes_without_a_second_pause() -> None:
    trace = _fixture("fixtures/interrupt-resume/trace.json")
    expected = _fixture("fixtures/interrupt-resume/expected.json")

    first, second = trace["invocations"]
    assert first["paused"] is True
    assert first["pausedAtNodeId"] == "approve"
    assert second["paused"] is False

    assert expected["firstInvocationPaused"] is True
    assert expected["secondInvocationPaused"] is False
    assert expected["pausedAtNodeId"] == "approve"


def test_interrupt_resume_replays_the_node_body_before_the_interrupt() -> None:
    # The pre-interrupt observer call fires on both the pausing invocation and
    # the resumed one, because LangGraph re-runs a node's body from its start
    # on resume -- a real, surprising effect worth evidencing rather than
    # assuming away (ADR 0002: interrupts raised inside a node body do not
    # appear in static node metadata).
    expected = _fixture("fixtures/interrupt-resume/expected.json")
    assert expected["nodeReExecutedOnResume"] is True
    assert expected["eventTypesByInvocation"]["invocation-1"] == [
        "run.observed",
        "step.awaiting_approval",
    ]
    assert expected["eventTypesByInvocation"]["invocation-2"] == [
        "run.observed",
        "step.awaiting_approval",
        "step.passed",
    ]


def test_interrupt_resume_events_share_one_logical_run_across_two_invocations() -> None:
    trace = _fixture("fixtures/interrupt-resume/trace.json")
    run_ids = {event["runId"] for event in trace["events"]}
    invocation_run_ids = {event["invocationRunId"] for event in trace["events"]}
    assert run_ids == {"logical-run"}
    assert invocation_run_ids == {"invocation-1", "invocation-2"}


def test_repeated_attempt_is_distinguishable_from_interrupt_resume() -> None:
    # Same-node retry happens inside one invocation, with no pause and no
    # Command(resume=...) -- structurally distinct from the interrupt/resume
    # capture, not a variant of it.
    trace = _fixture("fixtures/repeated-attempt/trace.json")
    expected = _fixture("fixtures/repeated-attempt/expected.json")

    assert trace["invocations"] == [
        {
            "label": "invocation-1 (single invoke(); node retries in-process)",
            "run_id": "invocation-1",
            "paused": False,
            "pausedAtNodeId": None,
        }
    ]
    assert expected["distinctInvocationRunIds"] == ["invocation-1"]
    assert expected["repeatedWithinSingleInvocation"] is True
    assert "__interrupt__" not in json.dumps(trace)


def test_repeated_attempt_numbers_are_retained_and_ordered() -> None:
    trace = _fixture("fixtures/repeated-attempt/trace.json")
    attempt_events = [
        e for e in trace["events"] if e["eventType"].startswith("attempt.")
    ]
    assert [e["metadata"]["attemptNumber"] for e in attempt_events] == [1, 2]
    assert [e["eventType"] for e in attempt_events] == [
        "attempt.failed",
        "attempt.passed",
    ]
    assert {e["nodeId"] for e in attempt_events} == {"act"}


def test_no_real_identifiers_credentials_or_payloads_entered_the_fixtures() -> None:
    for relative in (
        "fixtures/interrupt-resume/trace.json",
        "fixtures/repeated-attempt/trace.json",
    ):
        trace = _fixture(relative)
        serialized = json.dumps(
            {"events": trace["events"], "invocations": trace["invocations"]}
        )
        for forbidden in ("credential", "secret", "password", "prompt"):
            assert forbidden not in serialized.casefold()


def test_offline_replay_needs_only_the_standard_library() -> None:
    checks = (
        ("interrupt-resume", "Node body re-executed on resume: True"),
        ("repeated-attempt", "Repeated within a single invocation: True"),
    )
    for scenario, expect_line in checks:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                str(CAPTURE / "replay_dynamic.py"),
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
        assert expect_line in result.stdout
        assert "Acceptance assertions: PASS" in result.stdout
