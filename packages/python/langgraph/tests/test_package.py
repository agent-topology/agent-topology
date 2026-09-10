from pathlib import Path

import agent_topology.langgraph


def test_langgraph_owns_only_its_namespace_portion() -> None:
    package_dir = Path(agent_topology.langgraph.__file__).parent

    assert agent_topology.langgraph.__all__ == []
    assert not (package_dir.parent / "__init__.py").exists()
