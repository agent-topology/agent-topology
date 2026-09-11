from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
RELEASE_NOTES = ROOT / "docs/releases/v0.1.0-beta.2.md"
PUBLISHED_PYTHON_VERSION = "0.1.0b1"
PUBLISHED_NPM_VERSION = "0.1.0-beta.1"
PUBLIC_DOCS = (
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "ARCHITECTURE.md",
    ROOT / "CONVENTIONS.md",
    ROOT / "spec/README.md",
    ROOT / "conformance/README.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    *sorted((ROOT / "packages").glob("*/*/README.md")),
    *sorted((ROOT / "examples").glob("*/README.md")),
)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


def test_distribution_license_notices_match_repository_license() -> None:
    expected = (ROOT / "LICENSE").read_bytes()
    for ecosystem in ("python", "typescript"):
        for package in ("spec", "langgraph"):
            assert (
                ROOT / "packages" / ecosystem / package / "LICENSE"
            ).read_bytes() == expected


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
        assert linked.exists(), f"{document}: missing link target: {target}"
        if fragment:
            assert linked.is_file(), f"{document}: fragment on directory: {target}"
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
        f'python -m pip install "{python_spec["name"]}=={PUBLISHED_PYTHON_VERSION}"'
        in readme
    )
    assert (
        f'python -m pip install "{python_producer["name"]}'
        f'=={PUBLISHED_PYTHON_VERSION}"' in readme
    )
    assert f"npm install {typescript_spec['name']}@{PUBLISHED_NPM_VERSION}" in readme
    assert f"{typescript_producer['name']}@{PUBLISHED_NPM_VERSION}" in readme

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


@pytest.mark.parametrize(
    "path", [RELEASE_NOTES, ROOT / "docs/guides/upgrading-beta.2.md"]
)
def test_public_preview_release_notes_match_package_metadata(path: Path) -> None:
    release_notes = path.read_text(encoding="utf-8")
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

    for package in (
        python_spec,
        python_producer,
        typescript_spec,
        typescript_producer,
    ):
        assert package["name"] in release_notes
        assert package["version"] in release_notes

    assert "v0.1.0-beta.2" in release_notes
    assert "Python 3.11–3.14" in release_notes
    assert "LangGraph 1.2.10–1.2.11" in release_notes
    assert "Node.js 20+" in release_notes
    assert "LangGraph.js 1.4.14" in release_notes
    if path == RELEASE_NOTES:
        assert "`agt describe`" in release_notes
        assert "Python `agent-topology-langgraph` distribution" in release_notes
    assert "not published" in release_notes
    assert (
        f"@agent-topology/spec@{typescript_producer['peerDependencies']['@agent-topology/spec']}"
        in release_notes
    )
    assert (
        next(
            dep
            for dep in python_producer["dependencies"]
            if dep.startswith("agent-topology-spec")
        )
        in release_notes
    )


@pytest.mark.parametrize("name", ["python", "typescript"])
def test_quickstarts_keep_published_install_selections(name: str) -> None:
    document = (ROOT / f"docs/getting-started/{name}.md").read_text()
    install = re.findall(r"```bash\n(.*?)\n```", document, re.DOTALL)[0]
    expected = PUBLISHED_PYTHON_VERSION if name == "python" else PUBLISHED_NPM_VERSION
    assert expected in install
    assert "0.1.0b2" not in install
    assert "0.1.0-beta.2" not in install


@pytest.mark.parametrize(
    "name",
    [
        "releases/v0.1.0-beta.2.md",
        "getting-started/python.md",
        "getting-started/typescript.md",
        "guides/troubleshooting.md",
        "reference/api.md",
        "README.md",
    ],
)
def test_migration_guide_is_discoverable(name: str) -> None:
    assert "guides/upgrading-beta.2.md" in (ROOT / "docs" / name).read_text()
