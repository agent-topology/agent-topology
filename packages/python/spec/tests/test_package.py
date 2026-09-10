import subprocess
import sys
from pathlib import Path

import agent_topology.spec


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


def test_canonical_utilities_are_public() -> None:
    assert agent_topology.spec.__all__ == [
        "STRUCTURE_HASH_ALGORITHM",
        "STRUCTURE_HASH_ALGORITHM_VERSION",
        "canonical_json",
        "canonicalize_document",
        "compute_structure_hash",
        "finalize_document",
    ]
