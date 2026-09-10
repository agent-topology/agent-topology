from pathlib import Path

import agent_topology.spec


def test_spec_owns_only_its_namespace_portion() -> None:
    package_dir = Path(agent_topology.spec.__file__).parent

    assert agent_topology.spec.__all__ == []
    assert not (package_dir.parent / "__init__.py").exists()
