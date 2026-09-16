from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote

import pytest

from scripts import check_release_docs

ROOT = Path(__file__).resolve().parents[1]
RELEASE_STATE = check_release_docs.load_state()
PUBLISHED_RELEASE = RELEASE_STATE["coordinatedPublished"]
PUBLISHED_VERSIONS = {
    package["name"]: package["version"] for package in PUBLISHED_RELEASE["packages"]
}
RELEASE_NOTES = ROOT / PUBLISHED_RELEASE["releaseNotes"]
PUBLISHED_PYTHON_SPEC_VERSION = PUBLISHED_VERSIONS["agent-topology-spec"]
PUBLISHED_PYTHON_PRODUCER_VERSION = PUBLISHED_VERSIONS["agent-topology-langgraph"]
PUBLISHED_NPM_SPEC_VERSION = PUBLISHED_VERSIONS["@agent-topology/spec"]
PUBLISHED_NPM_PRODUCER_VERSION = PUBLISHED_VERSIONS["@agent-topology/langgraph"]
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
        repository_prefix = (
            "https://github.com/agent-topology/agent-topology/blob/main/"
        )
        if target.startswith(repository_prefix):
            target = target.removeprefix(repository_prefix)
            base = ROOT
        else:
            base = document.parent
        if target.startswith(("https://", "http://", "mailto:")):
            continue
        path_text, _, fragment = target.partition("#")
        linked = document if not path_text else base / unquote(path_text)
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

    python_spec_install = (
        f'python -m pip install "{python_spec["name"]}'
        f'=={PUBLISHED_PYTHON_SPEC_VERSION}"'
    )
    assert python_spec_install in readme
    assert (
        f'python -m pip install "{python_producer["name"]}'
        f'=={PUBLISHED_PYTHON_PRODUCER_VERSION}"' in readme
    )
    assert (
        f"npm install {typescript_spec['name']}@{PUBLISHED_NPM_SPEC_VERSION}" in readme
    )
    assert f"{typescript_producer['name']}@{PUBLISHED_NPM_PRODUCER_VERSION}" in readme

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
    "path", [RELEASE_NOTES, ROOT / "docs/guides/upgrading-beta.4.md"]
)
def test_public_preview_release_notes_match_package_metadata(path: Path) -> None:
    # The beta.4 release record and migration guide describe the coordinated
    # package set selected by the published release state.
    release_notes = path.read_text(encoding="utf-8")
    with (ROOT / "packages/python/spec/pyproject.toml").open("rb") as source:
        python_spec_name = tomllib.load(source)["project"]["name"]
    with (ROOT / "packages/python/langgraph/pyproject.toml").open("rb") as source:
        python_producer_name = tomllib.load(source)["project"]["name"]
    typescript_spec_name = json.loads(
        (ROOT / "packages/typescript/spec/package.json").read_text(encoding="utf-8")
    )["name"]
    typescript_producer_name = json.loads(
        (ROOT / "packages/typescript/langgraph/package.json").read_text(
            encoding="utf-8"
        )
    )["name"]

    for name in (
        python_spec_name,
        python_producer_name,
        typescript_spec_name,
        typescript_producer_name,
    ):
        assert name in release_notes
    assert PUBLISHED_PYTHON_SPEC_VERSION in release_notes
    assert PUBLISHED_PYTHON_PRODUCER_VERSION in release_notes
    assert PUBLISHED_NPM_SPEC_VERSION in release_notes
    assert PUBLISHED_NPM_PRODUCER_VERSION in release_notes

    assert "v0.1.0-beta.4" in release_notes
    assert "Python 3.11–3.14" in release_notes
    assert "LangGraph 1.2.10–1.2.11" in release_notes
    assert "Node.js 20+" in release_notes
    assert "LangGraph.js 1.4.14" in release_notes
    if path == RELEASE_NOTES:
        assert "`agt describe`" in release_notes
        assert "Python `agent-topology-langgraph` distribution" in release_notes
    assert "published and verified" in release_notes.lower()
    assert f"@agent-topology/spec@{PUBLISHED_NPM_SPEC_VERSION}" in release_notes
    assert "agent-topology-spec>=0.1.0b4,<0.2.0" in release_notes


@pytest.mark.parametrize("name", ["python", "typescript"])
def test_quickstarts_keep_published_install_selections(name: str) -> None:
    document = (ROOT / f"docs/getting-started/{name}.md").read_text()
    install = re.findall(r"```bash\n(.*?)\n```", document, re.DOTALL)[0]
    expected = (
        (PUBLISHED_PYTHON_PRODUCER_VERSION,)
        if name == "python"
        else (PUBLISHED_NPM_SPEC_VERSION, PUBLISHED_NPM_PRODUCER_VERSION)
    )
    assert all(version in install for version in expected)
    assert "0.1.0b1" not in install
    assert "0.1.0-beta.1" not in install


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


@pytest.mark.parametrize(
    "name",
    [
        "releases/v0.1.0-beta.3.md",
        "getting-started/python.md",
        "getting-started/typescript.md",
        "guides/troubleshooting.md",
        "reference/api.md",
        "README.md",
    ],
)
def test_beta3_migration_guide_is_discoverable(name: str) -> None:
    assert "guides/upgrading-beta.3.md" in (ROOT / "docs" / name).read_text()


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "docs/releases/v0.1.0-beta.3.md",
        ROOT / "docs/guides/upgrading-beta.3.md",
    ],
)
def test_beta3_published_notes_match_release_state(path: Path) -> None:
    # Beta.3 is no longer the live coordinatedPublished record (beta.4
    # superseded it), so this locks its own historical package set directly
    # rather than reading the now-unrelated live release state.
    release_text = path.read_text(encoding="utf-8")
    beta3_packages = (
        ("agent-topology-spec", "0.1.0b3"),
        ("agent-topology-langgraph", "0.1.0b3"),
        ("@agent-topology/spec", "0.1.0-beta.3"),
        ("@agent-topology/langgraph", "0.1.0-beta.3"),
    )
    for name, version in beta3_packages:
        assert name in release_text
        assert version in release_text

    assert "published and verified" in release_text.lower()


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "docs/releases/v0.1.0-beta.4.md",
        ROOT / "docs/guides/upgrading-beta.4.md",
    ],
)
def test_beta4_published_notes_match_release_state(path: Path) -> None:
    release_text = path.read_text(encoding="utf-8")
    beta4 = RELEASE_STATE["coordinatedPublished"]
    for package in beta4["packages"]:
        assert package["name"] in release_text
        assert package["version"] in release_text

    assert "published and verified" in release_text.lower()


def test_beta4_published_release_owns_live_coordinated_install_selections() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    with (ROOT / "packages/python/spec/pyproject.toml").open("rb") as source:
        python_spec = tomllib.load(source)["project"]
    typescript_spec = json.loads(
        (ROOT / "packages/typescript/spec/package.json").read_text(encoding="utf-8")
    )

    python_spec_install = (
        f'python -m pip install "{python_spec["name"]}'
        f'=={PUBLISHED_PYTHON_SPEC_VERSION}"'
    )
    assert python_spec_install in readme
    assert (
        f"npm install {typescript_spec['name']}@{PUBLISHED_NPM_SPEC_VERSION}" in readme
    )
    assert python_spec["version"] == PUBLISHED_PYTHON_SPEC_VERSION
    assert typescript_spec["version"] == PUBLISHED_NPM_SPEC_VERSION


@pytest.mark.parametrize(
    "name",
    [
        "releases/v0.1.0-beta.4.md",
        "getting-started/python.md",
        "getting-started/typescript.md",
        "guides/troubleshooting.md",
        "reference/api.md",
        "README.md",
    ],
)
def test_beta4_migration_guide_is_discoverable(name: str) -> None:
    assert "guides/upgrading-beta.4.md" in (ROOT / "docs" / name).read_text()


def test_release_state_and_public_docs_are_in_published_phase() -> None:
    # check_published also asserts package READMEs select the published
    # version, which a prepared candidate deliberately moves ahead of; that
    # invariant intentionally pauses while a candidate is active and resumes
    # once its closeout PR clears it back to null.
    if RELEASE_STATE.get("candidate") is not None:
        pytest.skip("an active candidate pauses full published-phase coherence")
    check_release_docs.check_phase("published")
