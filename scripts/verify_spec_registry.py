#!/usr/bin/env python3
"""Registry preflight for the protected Python producer publication path.

Before the ``publish`` job uploads any artifact, confirm the producer's spec
dependency is actually installable from the public registry: spec is pinned
and installed first, then the qualified producer wheel, then its public
smoke path. The registry install is retried with backoff, because a
"version not found" result right after publishing the spec can mean the
index has not caught up yet rather than that the version was rejected; a
result that persists across every attempt is reported as a registry
failure, exactly as it was last seen.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

try:
    from .check_release_source import resolve_producer_spec_version
except ImportError:  # Direct script execution adds this directory to sys.path.
    from check_release_source import resolve_producer_spec_version

ROOT = Path(__file__).resolve().parents[1]
DISTRIBUTION = "agent-topology-spec"

Runner = Callable[[list[str]], subprocess.CompletedProcess]


class RegistryPreflightError(RuntimeError):
    """Raised when the public registry cannot back the producer's spec dependency."""


def _default_runner(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True)


def install_pinned_spec(
    python: str,
    version: str,
    *,
    runner: Runner = _default_runner,
    attempts: int = 3,
    backoff_seconds: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Install exactly ``version`` of the spec distribution from the public registry.

    No ``--find-links``, workspace, or editable source is used, so this can
    only succeed against a real published release. Every failure is retried
    with backoff up to ``attempts`` times, since a fresh spec publication can
    take a moment to appear in the public index; the final attempt's error is
    what gets reported.
    """
    pin = f"{DISTRIBUTION}=={version}"
    command = ["uv", "pip", "install", "--python", python, "--no-deps", pin]
    last_output = ""
    for attempt in range(1, attempts + 1):
        result = runner(command)
        if result.returncode == 0:
            return
        last_output = (result.stderr or result.stdout).strip()
        if attempt < attempts:
            sleep(backoff_seconds * attempt)
    raise RegistryPreflightError(
        f"public registry install of {pin} failed after {attempts} attempts: "
        f"{last_output}"
    )


def verify_installed_spec_version(
    python: str, version: str, *, runner: Runner = _default_runner
) -> None:
    result = runner(
        [
            python,
            "-c",
            "import importlib.metadata as m; print(m.version('agent-topology-spec'))",
        ]
    )
    installed = result.stdout.strip()
    if result.returncode != 0 or installed != version:
        raise RegistryPreflightError(
            f"registry install reported incompatible metadata: expected {version!r}, "
            f"got {installed!r} ({(result.stderr or '').strip()})"
        )


def install_producer_wheel(
    python: str, wheel: Path, *, runner: Runner = _default_runner
) -> None:
    result = runner(["uv", "pip", "install", "--python", python, str(wheel)])
    if result.returncode != 0:
        raise RegistryPreflightError(
            "registry-verified producer install failed: "
            f"{(result.stderr or result.stdout).strip()}"
        )


def run_public_smoke(python: str, *, runner: Runner = _default_runner) -> None:
    result = runner([python, str(ROOT / "scripts/smoke_langgraph_installation.py")])
    if result.returncode != 0:
        raise RegistryPreflightError(
            f"public smoke path failed: {(result.stderr or result.stdout).strip()}"
        )


def run_preflight(
    python: str, wheel: Path, *, runner: Runner = _default_runner
) -> None:
    """Spec-first ordering: resolve and install spec before ever touching the
    producer wheel, so a producer install can never mask a missing or
    incompatible spec release."""
    version = resolve_producer_spec_version("langgraph")
    install_pinned_spec(python, version, runner=runner)
    verify_installed_spec_version(python, version, runner=runner)
    install_producer_wheel(python, wheel, runner=runner)
    run_public_smoke(python, runner=runner)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, help="isolated interpreter path")
    parser.add_argument("--wheel", required=True, type=Path)
    args = parser.parse_args()
    try:
        run_preflight(args.python, args.wheel)
    except (RegistryPreflightError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
