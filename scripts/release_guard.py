#!/usr/bin/env python3
"""Create and verify the release receipt required by the publish job."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

try:
    from .verify_python_artifacts import PACKAGES, inspect_artifacts
except ImportError:  # Direct script execution adds this directory to sys.path.
    from verify_python_artifacts import PACKAGES, inspect_artifacts


COMMON_CHECKS = {
    "artifact-inspection",
    "clean-installation",
    "namespace-coexistence",
    "package-tests",
    "python-quality",
}


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def verify_worktree(commit: str, *, allowed_untracked_root: Path | None = None) -> None:
    """Refuse a different commit or any tracked/untracked working-tree change."""
    head = _git("rev-parse", "HEAD")
    if head != commit:
        raise ValueError(f"checked-out commit is {head}, expected {commit}")
    changes = _git("status", "--porcelain", "--untracked-files=all").splitlines()
    if allowed_untracked_root is not None:
        if allowed_untracked_root.is_absolute() or ".." in allowed_untracked_root.parts:
            raise ValueError("allowed untracked root must be a safe relative path")
        prefix = allowed_untracked_root.as_posix().rstrip("/") + "/"
        changes = [
            change
            for change in changes
            if not (change.startswith("?? ") and change[3:].startswith(prefix))
        ]
    if changes:
        raise ValueError("refusing release from a dirty working tree")


def required_checks(package: str) -> set[str]:
    checks = set(COMMON_CHECKS)
    if package == "langgraph":
        checks.add("supported-langgraph-conformance")
    return checks


def create_receipt(
    *,
    package: str,
    version: str,
    dist_dir: Path,
    commit: str,
    checks: Sequence[str],
) -> dict[str, Any]:
    verify_worktree(commit)
    supplied = set(checks)
    required = required_checks(package)
    missing = required - supplied
    if missing:
        raise ValueError(f"release is missing required checks: {sorted(missing)}")
    unexpected = supplied - required
    if unexpected:
        raise ValueError(f"release has unknown checks: {sorted(unexpected)}")
    inspected = inspect_artifacts(package, version, dist_dir)
    return {
        "artifacts": inspected["artifacts"],
        "checks": sorted(supplied),
        "commit": commit,
        "distribution": inspected["distribution"],
        "package": package,
        "receiptVersion": 1,
        "version": version,
    }


def check_receipt(
    receipt: dict[str, Any],
    *,
    package: str,
    version: str,
    dist_dir: Path,
    commit: str,
    allowed_untracked_root: Path | None = None,
) -> None:
    verify_worktree(commit, allowed_untracked_root=allowed_untracked_root)
    inspected = inspect_artifacts(package, version, dist_dir)
    expected = {
        "artifacts": inspected["artifacts"],
        "checks": sorted(required_checks(package)),
        "commit": commit,
        "distribution": inspected["distribution"],
        "package": package,
        "receiptVersion": 1,
        "version": version,
    }
    if receipt != expected:
        raise ValueError(
            "release receipt does not match the selected artifacts and commit"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "check"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--package", choices=sorted(PACKAGES), required=True)
        subparser.add_argument("--version", required=True)
        subparser.add_argument("--dist-dir", type=Path, required=True)
        subparser.add_argument("--commit", required=True)
        subparser.add_argument("--receipt", type=Path, required=True)
        if command == "create":
            subparser.add_argument("--check", action="append", default=[])
        else:
            subparser.add_argument("--allow-untracked-root", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "create":
        receipt = create_receipt(
            package=args.package,
            version=args.version,
            dist_dir=args.dist_dir,
            commit=args.commit,
            checks=args.check,
        )
        args.receipt.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    else:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        check_receipt(
            receipt,
            package=args.package,
            version=args.version,
            dist_dir=args.dist_dir,
            commit=args.commit,
            allowed_untracked_root=args.allow_untracked_root,
        )


if __name__ == "__main__":
    main()
