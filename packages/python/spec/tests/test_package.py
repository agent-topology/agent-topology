import subprocess
import sys
from importlib.metadata import requires
from pathlib import Path

import agent_topology.spec


def _minimal_document() -> dict:
    return {
        "topologyVersion": "0.1",
        "provenance": {
            "generatedAt": "2026-09-10T19:00:00Z",
            "producer": {"name": "test", "version": "1.0"},
            "framework": {"name": "test", "version": "1.0"},
        },
        "producerLimitations": [],
        "structureHash": {
            "algorithm": "sha256",
            "algorithmVersion": "1",
            "value": "0" * 64,
        },
        "graphs": [
            {
                "id": "main",
                "structure": {
                    "nodes": [{"id": "node"}],
                    "edges": [],
                    "joins": [],
                    "entryNodeIds": ["node"],
                    "exitNodeIds": ["node"],
                },
            }
        ],
        "completeness": {"status": "complete", "gaps": []},
    }


def test_spec_owns_only_its_namespace_portion() -> None:
    package_dir = Path(agent_topology.spec.__file__).parent

    assert not (package_dir.parent / "__init__.py").exists()


def test_importing_spec_does_not_import_langgraph() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import agent_topology.spec; "
            "assert not any(name == 'langgraph' or name.startswith('langgraph.') "
            "for name in sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_spec_distribution_does_not_depend_on_langgraph() -> None:
    dependencies = requires("agent-topology-spec") or []

    assert not any("langgraph" in dependency.lower() for dependency in dependencies)


def test_packaged_schema_validates_a_document() -> None:
    assert agent_topology.spec.load_schema()["$schema"].endswith("2020-12/schema")
    assert agent_topology.spec.validate_document(_minimal_document()) == []


def test_canonical_utilities_are_public() -> None:
    assert agent_topology.spec.__all__ == [
        "STRUCTURE_HASH_ALGORITHM",
        "STRUCTURE_HASH_ALGORITHM_VERSION",
        "canonical_json",
        "canonicalize_document",
        "compute_structure_hash",
        "derived_join_edges",
        "finalize_document",
        "load_schema",
        "validate_document",
    ]
