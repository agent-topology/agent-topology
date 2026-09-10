#!/usr/bin/env python3
"""Validate agent-topology documents against the canonical contract."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

PACKAGE_SOURCE = Path(__file__).parents[1] / "packages" / "python" / "spec" / "src"
sys.path.insert(0, str(PACKAGE_SOURCE))
validate_document = import_module("agent_topology.spec").validate_document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False

    for document_path in args.documents:
        try:
            document: Any = json.loads(document_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"{document_path}: {error}")
            failed = True
            continue

        for error in validate_document(document):
            print(f"{document_path}: {error}")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
