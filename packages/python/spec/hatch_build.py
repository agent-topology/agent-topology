"""Build hooks for packaging the repository's canonical schema."""

from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Include the canonical schema without maintaining a checked-in copy."""

    def initialize(self, version: str, build_data: dict) -> None:
        package_schema = (
            Path(self.root)
            / "src"
            / "agent_topology"
            / "spec"
            / "agent-topology.schema.json"
        )
        candidates = [
            parent / "spec" / "agent-topology.schema.json"
            for parent in Path(self.root).parents
        ]
        candidates.append(package_schema)
        schema = next(
            (candidate for candidate in candidates if candidate.is_file()), None
        )
        if schema is None:
            raise RuntimeError("canonical agent-topology schema was not found")

        target = "agent_topology/spec/agent-topology.schema.json"
        if self.target_name == "sdist":
            target = f"src/{target}"
        build_data.setdefault("force_include", {})[str(schema)] = target
