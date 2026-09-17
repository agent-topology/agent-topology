from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CAPTURE = (
    ROOT
    / "docs"
    / "research"
    / "internal-consumer"
    / "campaign-agent"
    / "capture-declared-child"
)
FIXTURE = CAPTURE / "fixtures" / "prepare-brief-declared-child"

EXPECTED_HASHES = {
    "trace.json": ("8e0c2968b85d81b83f8742941b31dc33e02b5df2ec353e959e2e601b4cd8603a"),
    "expected.json": (
        "07ceb22777cce74a9b31ed8ca425d18a21c87a5dfb86ccb94f54761b5eb275b3"
    ),
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def test_fixture_is_pinned_to_the_documented_commits() -> None:
    trace = _fixture("trace.json")
    assert trace["provenance"]["consumer"]["commit"] == (
        "a1532d5eed2d356792d5c3ee460d2bb8fb23db1e"
    )
    assert trace["provenance"]["consumer"]["ref"] == "main"
    assert trace["provenance"]["consumer"]["repository"] == (
        "https://github.com/milocosmopolitan/campaign-agent"
    )
    assert trace["provenance"]["core"]["repository"] == (
        "https://github.com/agent-topology/agent-topology"
    )
    assert trace["provenance"]["core"]["commit"]


def test_fixture_hashes_match_the_recorded_generation() -> None:
    for name, expected_digest in EXPECTED_HASHES.items():
        digest = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        assert digest == expected_digest, f"{name} drifted from its recorded hash"


def test_static_evidence_is_a_known_declared_child_call_matching_standalone() -> None:
    # The accepted identity mapping from #180 / _describe.py:301-359, computed
    # by this repository's own describe() on the exact compiled object this
    # fixture goes on to execute -- not a separately recompiled instance.
    trace = _fixture("trace.json")
    static = trace["staticEvidence"]
    assert static["parent"] == "channel_concept"
    assert static["nodeId"] == "prepare_brief"
    assert static["declaredChildGraph"] == "copy_brief_prepare"
    assert static["depth0Evidence"]["kind"] == "declared-child-call"
    assert static["depth0Evidence"]["source"] == "compiled.__agent_topology_children__"
    assert static["materializedSubgraphId"] == "channel_concept:prepare_brief"
    assert static["matchesStandaloneFactory"] is True


def test_declared_child_invoked_at_runtime_is_confirmed_by_identity_not_name() -> None:
    # Issue #193's own instruction: "Assert correlation via identity, not
    # display names." The invoke spy checks `self is declared[node_id]`
    # directly (see capture.py's _install_invoke_spy), never a string
    # comparison between "prepare_brief" and "copy_brief_prepare".
    trace = _fixture("trace.json")
    identity_events = [
        e for e in trace["events"] if e["eventType"] == "invoke.declared-child-call"
    ]
    assert identity_events, "no declared-child invoke was observed"
    by_node = {e["nodeId"]: e for e in identity_events}
    assert by_node["prepare_brief"]["declaredChildIdentityConfirmed"] is True
    assert (
        by_node["prepare_brief"]["declaredChildGraphName"]
        == "channel_concept.copy_brief_prepare"
    )
    # draft_copy/review_copy are the same graph's other two declared children,
    # incidentally exercised by the same run; recorded honestly rather than
    # filtered out, but this issue's demonstrated relationship is prepare_brief.
    assert set(by_node) == {"prepare_brief", "draft_copy", "review_copy"}
    assert all(e["declaredChildIdentityConfirmed"] is True for e in identity_events)


def test_declared_childs_own_node_identity_is_observed_nested_under_the_parent() -> (
    None
):
    # The RunObserver instance is threaded into the declared child's own
    # RuntimeContext (see channel_concept/graph.py's _prepare_brief), so the
    # child's own node id (select_evidence, owned by copy_brief_prepare) is
    # observable at all -- tagged nestedUnderNodeId from the invoke spy's own
    # bookkeeping, a real containment fact, not inferred from node naming.
    trace = _fixture("trace.json")
    nested = [
        e
        for e in trace["events"]
        if e["eventType"].startswith("observer.") and e["nestedUnderNodeId"]
    ]
    by_parent = {}
    for event in nested:
        by_parent.setdefault(event["nestedUnderNodeId"], set()).add(event["nodeId"])
    assert by_parent["prepare_brief"] == {"select_evidence"}


def test_task_level_events_are_never_nested_under_a_declared_child() -> None:
    # A real boundary this capture documents rather than assumes: a nested
    # child.invoke() call runs entirely inside one parent LangGraph task, so
    # the parent's own stream_mode="debug" channel never sees the child's
    # internal nodes as separate top-level tasks.
    trace = _fixture("trace.json")
    task_events = [e for e in trace["events"] if e["eventType"].startswith("task.")]
    assert task_events
    assert all(e["nestedUnderNodeId"] is None for e in task_events)


def test_static_call_site_logical_run_occurrence_and_invocation_stay_distinct() -> None:
    trace = _fixture("trace.json")
    run_ids = {event["runId"] for event in trace["events"]}
    invocation_run_ids = {event["invocationRunId"] for event in trace["events"]}
    assert run_ids == {"capture-thread-declared-child-1"}
    assert invocation_run_ids == {"invocation-1", "invocation-2"}

    # every node occurs exactly once as a task, except await_decision, which
    # is scheduled once per invocation (pause, then resume).
    task_events = [e for e in trace["events"] if e["eventType"].startswith("task.")]
    for event in task_events:
        if event["nodeId"] == "await_decision":
            assert event["nodeOccurrence"] in (1, 2)
        else:
            assert event["nodeOccurrence"] == 1


def test_real_await_decision_pauses_once_and_resumes_without_a_second_pause() -> None:
    trace = _fixture("trace.json")
    first, second = trace["invocations"]
    assert first["paused"] is True
    assert first["pausedAtNodeId"] == "await_decision"
    assert second["paused"] is False
    assert trace["finalOutcome"] == "approved"


def test_no_missing_or_ambiguous_evidence_was_guessed() -> None:
    trace = _fixture("trace.json")
    expected = _fixture("expected.json")
    assert trace["provenance"]["unresolvedEvidence"] == []
    assert expected["unresolvedEvidence"] == []


def test_retry_attempts_are_kept_separate_from_this_minimal_scenario() -> None:
    expected = _fixture("expected.json")
    assert expected["retryAttemptsObserved"] == 0


def test_no_real_identifiers_credentials_or_payloads_entered_the_fixture() -> None:
    trace = _fixture("trace.json")
    serialized = json.dumps({"events": trace["events"]})
    for forbidden in ("credential", "secret", "password", "prompt"):
        assert forbidden not in serialized.casefold()


def test_offline_replay_needs_only_the_standard_library() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(CAPTURE / "replay.py"), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (
        "Declared-child-call correlation confirmed for "
        "prepare_brief -> copy_brief_prepare: True" in result.stdout
    )
    assert "Acceptance assertions: PASS" in result.stdout
