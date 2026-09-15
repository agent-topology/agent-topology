"""Command-line entry point owned by the LangGraph producer package."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Sequence
from enum import IntEnum
from pathlib import Path
from types import ModuleType

from agent_topology.spec import canonical_json

from ._describe import describe
from ._exceptions import IncompleteTopologyError, UnsupportedLangGraphVersionError


class ExitCode(IntEnum):
    """Stable process results documented for ``agt describe``."""

    SUCCESS = 0
    USAGE = 2
    IMPORT = 3
    TARGET_RESOLUTION = 4
    UNSUPPORTED_VERSION = 5
    INCOMPLETE = 6
    OUTPUT_WRITE = 7
    EXTRACTION = 8


class _TargetSyntaxError(ValueError):
    """Raised when a target does not use the documented file/object syntax."""


class _TargetImportError(RuntimeError):
    """Raised when the target module cannot be imported."""

    def __init__(self, path: Path, cause: BaseException) -> None:
        self.path = path
        self.cause = cause
        super().__init__(str(path))


class _TargetResolutionError(RuntimeError):
    """Raised when an imported module does not expose the requested object."""


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"invalid depth {value!r}; expected a non-negative integer"
        ) from error
    if parsed < 0:
        raise argparse.ArgumentTypeError(
            f"invalid depth {value!r}; expected a non-negative integer"
        )
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agt",
        description="Derive agent-topology documents from compiled graph targets.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    describe_parser = subparsers.add_parser(
        "describe", help="describe a compiled LangGraph graph"
    )
    describe_parser.add_argument(
        "target", metavar="PATH.py:OBJECT", help="Python file and object to describe"
    )
    describe_parser.add_argument(
        "--out", required=True, type=Path, help="path for the canonical JSON document"
    )
    describe_parser.add_argument(
        "--graph-id",
        default="main",
        help="document-local graph identifier (default: main)",
    )
    describe_parser.add_argument(
        "--depth",
        type=_nonnegative_int,
        default=0,
        metavar="N",
        help="nested graph levels to expand as non-negative integer (default: 0)",
    )
    describe_parser.add_argument(
        "--strict",
        action="store_true",
        help="return 6 when graph-specific completeness gaps are present",
    )
    return parser


def _split_target(target: str) -> tuple[Path, str]:
    file_value, separator, object_name = target.rpartition(":")
    if (
        not separator
        or not file_value
        or not object_name
        or Path(file_value).suffix != ".py"
        or not object_name.isidentifier()
    ):
        raise _TargetSyntaxError(f"invalid target {target!r}; expected PATH.py:OBJECT")
    return Path(file_value), object_name


def _import_module(path: Path) -> ModuleType:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise _TargetImportError(resolved, FileNotFoundError(resolved))

    module_name = f"_agent_topology_target_{abs(hash(resolved))}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            raise ImportError("Python could not create a module loader")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        sys.path.insert(0, str(resolved.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
    except Exception as error:
        sys.modules.pop(module_name, None)
        raise _TargetImportError(resolved, error) from error
    return module


def _load_target(target: str) -> tuple[object, Path, str]:
    path, object_name = _split_target(target)
    module = _import_module(path)
    try:
        value = getattr(module, object_name)
    except AttributeError as error:
        raise _TargetResolutionError(
            f"module loaded from {str(path)!r} but has no object {object_name!r}"
        ) from error
    return value, path, object_name


def _write_document(document: dict[str, object], output: Path) -> None:
    output.write_text(canonical_json(document) + "\n", encoding="utf-8")


def _describe_command(
    target: str, output: Path, *, graph_id: str, depth: int, strict: bool
) -> ExitCode:
    try:
        graph, target_path, object_name = _load_target(target)
    except _TargetSyntaxError as error:
        print(f"agt: target syntax error: {error}", file=sys.stderr)
        return ExitCode.USAGE
    except _TargetImportError as error:
        print(
            f"agt: import error: could not import {str(error.path)!r} "
            f"({type(error.cause).__name__}). Run that file with Python to inspect "
            "the underlying import failure.",
            file=sys.stderr,
        )
        return ExitCode.IMPORT
    except _TargetResolutionError as error:
        print(f"agt: target resolution error: {error}.", file=sys.stderr)
        return ExitCode.TARGET_RESOLUTION

    result = ExitCode.SUCCESS
    try:
        document = describe(graph, graph_id=graph_id, depth=depth, strict=strict)
    except IncompleteTopologyError as error:
        document = error.document
        result = ExitCode.INCOMPLETE
    except UnsupportedLangGraphVersionError as error:
        print(f"agt: unsupported version: {error}", file=sys.stderr)
        return ExitCode.UNSUPPORTED_VERSION
    except TypeError as error:
        print(
            f"agt: target resolution error: {str(target_path)!r}:{object_name} "
            f"is not a supported compiled graph ({error}).",
            file=sys.stderr,
        )
        return ExitCode.TARGET_RESOLUTION
    except Exception as error:
        print(
            f"agt: extraction error: describing {str(target_path)!r}:{object_name} "
            f"failed ({type(error).__name__}).",
            file=sys.stderr,
        )
        return ExitCode.EXTRACTION

    try:
        _write_document(document, output)
    except (OSError, TypeError, ValueError) as error:
        print(
            f"agt: output write error: could not write {str(output)!r} "
            f"({type(error).__name__}). Check the destination path and permissions.",
            file=sys.stderr,
        )
        return ExitCode.OUTPUT_WRITE

    if result is ExitCode.INCOMPLETE:
        gap_count = len(document["completeness"]["gaps"])  # type: ignore[index]
        print(
            f"agt: incomplete topology: wrote {gap_count} graph-specific "
            f"{'gap' if gap_count == 1 else 'gaps'} to {str(output)!r}.",
            file=sys.stderr,
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``agt`` command and return its process exit status."""
    arguments = _parser().parse_args(argv)
    if arguments.command == "describe":
        return _describe_command(
            arguments.target,
            arguments.out,
            graph_id=arguments.graph_id,
            depth=arguments.depth,
            strict=arguments.strict,
        )
    raise AssertionError(f"unhandled command: {arguments.command}")
