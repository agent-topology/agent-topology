import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from agent_topology.langgraph import _cli
from agent_topology.spec import canonical_json, validate_document


def _write_graph(path: Path, *, incomplete: bool = False) -> None:
    conditional = """
def route(state: dict) -> str:
    return "step"

builder.add_conditional_edges("router", route)
"""
    linear = """
builder.add_edge("router", "step")
"""
    path.write_text(
        """from langgraph.graph import END, START, StateGraph

builder = StateGraph(dict)
builder.add_node("router", lambda state: state)
builder.add_node("step", lambda state: state)
builder.add_edge(START, "router")
"""
        + (conditional if incomplete else linear)
        + """builder.add_edge("step", END)
graph = builder.compile()
""",
        encoding="utf-8",
    )


def test_documented_quickstart_and_consumer_run_end_to_end(tmp_path: Path) -> None:
    docs = Path(__file__).resolve().parents[4] / "docs"
    quickstart = (docs / "getting-started/python.md").read_text(encoding="utf-8")
    source = re.findall(r"```python\n(.*?)\n```", quickstart, re.DOTALL)[0]
    target = tmp_path / "graph.py"
    target.write_text(source, encoding="utf-8")
    api = subprocess.run(
        [sys.executable, str(target)], capture_output=True, text=True, check=True
    )
    api_document = json.loads(api.stdout)
    output = tmp_path / "topology.json"
    assert (
        _cli.main(["describe", f"{target}:graph", "--out", str(output), "--strict"])
        == 0
    )
    document = json.loads(output.read_text(encoding="utf-8"))
    assert validate_document(document) == []
    assert document["structureHash"] == api_document["structureHash"]
    assert {node["id"] for node in document["graphs"][0]["structure"]["nodes"]} == {
        "__start__",
        "greet",
        "__end__",
    }
    consumer = (docs / "guides/consuming-documents.md").read_text(encoding="utf-8")
    source = re.findall(r"```python\n(.*?)\n```", consumer, re.DOTALL)[0]
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "main 3 nodes" in result.stdout
    assert "Completeness: complete" in result.stdout
    assert "Limitation: dynamic-interrupts" in result.stdout


def test_package_publishes_agt_from_the_langgraph_distribution() -> None:
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert project["project"]["scripts"] == {
        "agt": "agent_topology.langgraph._cli:main"
    }


def test_describe_writes_canonical_document(tmp_path: Path) -> None:
    target = tmp_path / "graph.py"
    output = tmp_path / "topology.json"
    _write_graph(target)

    result = _cli.main(["describe", f"{target}:graph", "--out", str(output)])

    document = json.loads(output.read_text(encoding="utf-8"))
    assert result == _cli.ExitCode.SUCCESS
    assert output.read_text(encoding="utf-8") == canonical_json(document) + "\n"
    assert document["completeness"]["status"] == "complete"


def test_strict_incomplete_writes_document_and_returns_documented_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "graph.py"
    output = tmp_path / "topology.json"
    _write_graph(target, incomplete=True)

    result = _cli.main(
        ["describe", f"{target}:graph", "--out", str(output), "--strict"]
    )

    document = json.loads(output.read_text(encoding="utf-8"))
    assert result == _cli.ExitCode.INCOMPLETE
    assert document["completeness"]["status"] == "incomplete"
    assert "1 graph-specific gap" in capsys.readouterr().err


@pytest.mark.parametrize("target", ["graph.py", "graph:graph", "graph.py:not.dotted"])
def test_invalid_target_syntax_is_actionable(
    target: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _cli.main(["describe", target, "--out", str(tmp_path / "out.json")])

    assert result == _cli.ExitCode.USAGE
    assert "expected PATH.py:OBJECT" in capsys.readouterr().err


def test_import_failure_is_distinct_and_does_not_echo_exception_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "broken.py"
    target.write_text(
        "raise RuntimeError('do-not-print-this-value')\n", encoding="utf-8"
    )

    result = _cli.main(
        ["describe", f"{target}:graph", "--out", str(tmp_path / "out.json")]
    )

    error = capsys.readouterr().err
    assert result == _cli.ExitCode.IMPORT
    assert "import error" in error
    assert "RuntimeError" in error
    assert "do-not-print-this-value" not in error


def test_missing_object_is_a_target_resolution_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "graph.py"
    target.write_text("different = object()\n", encoding="utf-8")

    result = _cli.main(
        ["describe", f"{target}:graph", "--out", str(tmp_path / "out.json")]
    )

    assert result == _cli.ExitCode.TARGET_RESOLUTION
    assert "has no object 'graph'" in capsys.readouterr().err


def test_uncompiled_object_is_a_target_resolution_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "graph.py"
    target.write_text("graph = object()\n", encoding="utf-8")

    result = _cli.main(
        ["describe", f"{target}:graph", "--out", str(tmp_path / "out.json")]
    )

    assert result == _cli.ExitCode.TARGET_RESOLUTION
    assert "not a supported compiled graph" in capsys.readouterr().err


def test_unsupported_version_has_its_own_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "graph.py"
    target.write_text("graph = object()\n", encoding="utf-8")

    def unsupported(_graph: object, *, strict: bool) -> dict[str, object]:
        raise _cli.UnsupportedLangGraphVersionError(
            installed_version="1.2.12",
            supported_specifier=">=1.2.10,<=1.2.11",
            tested_versions=("1.2.10", "1.2.11"),
        )

    monkeypatch.setattr(_cli, "describe", unsupported)
    result = _cli.main(
        ["describe", f"{target}:graph", "--out", str(tmp_path / "out.json")]
    )

    assert result == _cli.ExitCode.UNSUPPORTED_VERSION
    assert "unsupported version" in capsys.readouterr().err


def test_unwritable_output_has_its_own_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "graph.py"
    _write_graph(target)

    result = _cli.main(["describe", f"{target}:graph", "--out", str(tmp_path)])

    assert result == _cli.ExitCode.OUTPUT_WRITE
    assert "output write error" in capsys.readouterr().err
