from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import agent_topology.spec

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "trace-correlation"


def _module():
    spec = importlib.util.spec_from_file_location(
        "trace_correlation", EXAMPLE / "correlate.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(name: str) -> dict:
    return json.loads((EXAMPLE / "fixtures" / name).read_text(encoding="utf-8"))


def test_checked_in_result_covers_every_evidence_class() -> None:
    topology = _fixture("topology.json")
    trace = _fixture("trace.json")
    result = _module().correlate(topology, trace)

    assert agent_topology.spec.validate_document(topology) == []
    assert trace["provenance"]["framework"] == {
        "name": "langgraph",
        "version": "1.2.11",
    }
    assert trace["provenance"]["kind"] == "sanitized-langgraph-execution"
    assert result == _fixture("expected.json")
    assert result["summary"] == {
        "ambiguous": 1,
        "insufficient": 1,
        "matched": 1,
        "unmatched": 1,
        "unobservedTopologyElements": 8,
    }
    assert result["topologyEvidence"]["completeness"]["status"] == "incomplete"
    assert result["topologyEvidence"]["producerLimitations"]


def test_offline_command_needs_only_the_standard_library() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(EXAMPLE / "correlate.py"), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "1 matched, 1 unmatched, 1 ambiguous, 1 insufficient" in result.stdout
    assert "Acceptance assertions: PASS" in result.stdout
