from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CAPTURE = (
    ROOT / "docs" / "research" / "internal-consumer" / "campaign-agent" / "capture"
)
FIXTURE = CAPTURE / "fixtures" / "await-decision-interrupt-resume"

EXPECTED_HASHES = {
    "trace.json": ("58a2a55e798a919993433b8c08640b8161420e8454263e5cd76decf335327b07"),
    "expected.json": (
        "7f136fa4f3acb31b3c3438c95b886f227d6ff0a844a9b04da67cc56e616b1ec4"
    ),
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def test_fixture_is_pinned_to_the_documented_commit() -> None:
    trace = _fixture("trace.json")
    assert trace["provenance"]["consumer"]["commit"] == (
        "a1532d5eed2d356792d5c3ee460d2bb8fb23db1e"
    )
    assert trace["provenance"]["consumer"]["ref"] == "main"
    assert trace["provenance"]["consumer"]["repository"] == (
        "https://github.com/milocosmopolitan/campaign-agent"
    )


def test_fixture_hashes_match_the_recorded_generation() -> None:
    for name, expected_digest in EXPECTED_HASHES.items():
        digest = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        assert digest == expected_digest, f"{name} drifted from its recorded hash"


def test_real_await_decision_node_pauses_once_and_resumes_without_a_second_pause() -> (
    None
):
    trace = _fixture("trace.json")
    expected = _fixture("expected.json")

    first, second = trace["invocations"]
    assert first["paused"] is True
    assert first["pausedAtNodeId"] == "await_decision"
    assert second["paused"] is False

    assert expected["firstInvocationPaused"] is True
    assert expected["secondInvocationPaused"] is False
    assert expected["pausedAtNodeId"] == "await_decision"


def test_await_decision_node_body_re_executes_on_resume_as_two_task_occurrences() -> (
    None
):
    # A real, surprising effect worth evidencing rather than assumed (ADR
    # 0002: interrupts raised inside a node body do not appear in static node
    # metadata) -- and, per #181, for campaign-agent's actual gate, not a
    # stand-in.
    expected = _fixture("expected.json")
    assert expected["nodeReExecutedOnResume"] is True
    assert expected["awaitDecisionTaskOccurrences"] == [1, 2]
    assert expected["taskOccurrencesByNode"]["await_decision"] == [1, 2]


def test_await_decision_reuses_one_real_task_id_across_invocations() -> None:
    # Distinct from git-agent's #191 capture: campaign_contract's own code
    # never calls RunObserver for await_decision, so this capture reads
    # LangGraph's own stream_mode="debug" task events instead. Those events
    # reveal that the *same* real LangGraph task id is scheduled again on
    # resume -- "which task" and "which invocation" are independently
    # addressable identities, not one and the same.
    trace = _fixture("trace.json")
    expected = _fixture("expected.json")
    assert expected["awaitDecisionTaskIdStableAcrossInvocations"] is True
    await_decision_task_ids = {
        e["taskId"]
        for e in trace["events"]
        if e["nodeId"] == "await_decision" and e["eventType"].startswith("task.")
    }
    assert len(await_decision_task_ids) == 1


def test_static_call_site_logical_run_occurrence_and_invocation_stay_distinct() -> None:
    trace = _fixture("trace.json")
    run_ids = {event["runId"] for event in trace["events"]}
    invocation_run_ids = {event["invocationRunId"] for event in trace["events"]}
    node_ids = {event["nodeId"] for event in trace["events"]}

    assert run_ids == {"capture-thread-await-decision-1"}
    assert invocation_run_ids == {"invocation-1", "invocation-2"}
    assert "await_decision" in node_ids

    # every node other than await_decision occurs exactly once as a task;
    # await_decision alone occurs twice, once per invocation.
    for event in trace["events"]:
        if not event["eventType"].startswith("task."):
            continue
        if event["nodeId"] == "await_decision":
            assert event["nodeOccurrence"] in (1, 2)
        else:
            assert event["nodeOccurrence"] == 1


def test_observer_and_debug_stream_occurrence_counts_agree_for_model_nodes() -> None:
    # campaign_contract only wires RunObserver to its two model nodes
    # (draft_rules/draft_concept); this checks that mechanism against the
    # debug-stream mechanism that covers every node, including
    # await_decision, which RunObserver never sees at all here.
    expected = _fixture("expected.json")
    assert expected["observerAndTaskOccurrencesAgreeForModelNodes"] is True
    assert expected["observerStepOccurrencesByNode"] == {
        "draft_rules": [1],
        "draft_concept": [1],
    }
    assert expected["taskOccurrencesByNode"]["draft_rules"] == [1]
    assert expected["taskOccurrencesByNode"]["draft_concept"] == [1]


def test_retry_attempts_are_kept_separate_from_this_minimal_resume_case() -> None:
    expected = _fixture("expected.json")
    assert expected["retryAttemptsObserved"] == 0
    assert expected["observerAttemptOccurrencesByNode"] == {
        "draft_rules": [1],
        "draft_concept": [1],
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
    assert trace["finalOutcome"] == "approved"
    sanitization = " ".join(trace["provenance"]["sanitization"])
    assert "no write port at all" in sanitization


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
