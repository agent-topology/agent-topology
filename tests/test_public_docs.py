from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = (
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "docs/releasing.md",
)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


def _heading_anchors(document: Path) -> set[str]:
    anchors: set[str] = set()
    for line in document.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            continue
        heading = line.lstrip("#").strip().lower()
        anchor = re.sub(r"[^\w\- ]", "", heading)
        anchors.add(re.sub(r"[ _]+", "-", anchor))
    return anchors


@pytest.mark.parametrize("document", PUBLIC_DOCS, ids=lambda path: path.name)
def test_public_document_links_resolve_from_checkout(document: Path) -> None:
    for target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
        if target.startswith(("https://", "http://", "mailto:")):
            continue
        path_text, _, fragment = target.partition("#")
        linked = document if not path_text else document.parent / unquote(path_text)
        linked = linked.resolve()
        assert linked.is_relative_to(ROOT), (
            f"{document}: link escapes checkout: {target}"
        )
        assert linked.is_file(), f"{document}: missing link target: {target}"
        if fragment:
            assert fragment in _heading_anchors(linked), (
                f"{document}: missing heading in {linked}: #{fragment}"
            )


def test_readme_installation_and_compatibility_match_package_metadata() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    with (ROOT / "packages/python/spec/pyproject.toml").open("rb") as source:
        python_spec = tomllib.load(source)["project"]
    with (ROOT / "packages/python/langgraph/pyproject.toml").open("rb") as source:
        python_producer = tomllib.load(source)["project"]
    typescript_spec = json.loads(
        (ROOT / "packages/typescript/spec/package.json").read_text(encoding="utf-8")
    )
    typescript_producer = json.loads(
        (ROOT / "packages/typescript/langgraph/package.json").read_text(
            encoding="utf-8"
        )
    )

    assert (
        f'python -m pip install "{python_spec["name"]}=={python_spec["version"]}"'
        in readme
    )
    assert (
        f'python -m pip install "{python_producer["name"]}'
        f'=={python_producer["version"]}"' in readme
    )
    assert (
        f"npm install {typescript_spec['name']}@{typescript_spec['version']}" in readme
    )
    assert f"{typescript_producer['name']}@{typescript_producer['version']}" in readme

    assert "agent_topology.spec" in readme
    assert "agent_topology.langgraph" in readme
    assert python_producer["scripts"] == {"agt": "agent_topology.langgraph._cli:main"}
    assert "bin" not in typescript_spec
    assert "bin" not in typescript_producer

    assert python_spec["requires-python"] == ">=3.11,<3.15"
    assert python_producer["requires-python"] == ">=3.11,<3.15"
    assert "langgraph>=1.2.10,<=1.2.11" in python_producer["dependencies"]
    assert typescript_spec["engines"]["node"] == ">=20"
    assert typescript_producer["engines"]["node"] == ">=20"
    assert typescript_producer["dependencies"]["@langchain/langgraph"] == "1.4.14"
