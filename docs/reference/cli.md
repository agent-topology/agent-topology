# CLI reference

[Documentation home](../README.md) · [Python quickstart](../getting-started/python.md)

Installing `agent-topology-langgraph` provides `agt` in that Python environment.

```bash
agt describe path/to/graph.py:graph --out topology.json
agt describe path/to/graph.py:graph --out topology.json --graph-id invoice-intake
agt describe path/to/graph.py:graph --out topology.json --depth 1
agt describe path/to/graph.py:graph --out topology.json --strict
agt describe --help
```

`PATH.py:OBJECT` refers to one module-level Python identifier. It does not support
module dotted paths, attribute chains, or factory calls. Define and compile the
graph, including every nested child graph you want `--depth` to expand, in the
file before naming it as the target. The CLI only imports and describes the
named object; it never invokes the graph or calls a factory to build one.

`--out` is required. The command writes UTF-8 canonical JSON followed by a newline
and replaces an existing destination file. Its parent directory must already
exist. Use a distinct output path, not a source filename.

`--graph-id` selects the non-empty document-local graph address and defaults to
`main`. Supply distinct stable ids when outputs will later be composed.

`--depth` selects how many nested graph levels to materialize as their own
addressable `graphs[]` entries and defaults to `0`, which keeps child graphs
opaque. It accepts only non-negative integers; a missing, negative, or
non-integer value is a usage error (status `2`). This is the same traversal
depth accepted by the Python `describe` API's `depth` keyword, and
`agt describe` output is equivalent to calling that API directly at the same
depth. A node holding a confirmed compiled child keeps its own id at every
depth; within the requested budget it also gains a core `subgraphId`
addressing the materialized child — see
[ADR 0012](../decisions/0012-nested-graph-identity-traversal-and-compatibility.md).
See `--strict` below for how any remaining graph-specific gaps are reported.

`--strict` returns status `6` when graph-specific gaps are present. The incomplete
document is still written, so automation can retain it as an artifact and present
its findings. Producer-wide limitations alone do not fail strict extraction.

There is no `agt diff`, producer discovery, or TypeScript CLI.

## Exit statuses

| Status | Meaning | Next action |
| --- | --- | --- |
| 0 | Document written | Read completeness and limitations |
| 2 | Invalid command, target syntax, or `--depth` value | Use `PATH.py:OBJECT`, `--out`, and a non-negative `--depth` |
| 3 | Target could not be imported | Check file path, dependencies, and module initialization |
| 4 | Object missing or not a supported compiled graph | Export the result of `StateGraph.compile()` |
| 5 | Unsupported LangGraph version | Install an evidence-backed release |
| 6 | Strict extraction found gaps | Retain the output and inspect affected elements |
| 7 | Output could not be written | Check parent directory and write permissions |
| 8 | Other extraction failure | Reproduce with the Python API for the underlying exception |

Diagnostics go to stderr. The manifest is written to the specified file, not stdout.
If writing the incomplete document fails, status `7` takes precedence over `6`.

## Import behavior

The CLI imports the target and temporarily places its directory on Python's import
path, so sibling modules can be imported. Package-relative imports may need a small
wrapper file that imports the graph from your installed application package.

Importing executes module-level Python statements with your process's permissions.
The CLI does not sandbox them, invoke the compiled graph, or hide side effects in
application initialization. Keep graph execution in a separate entry point and
only use trusted targets. See [troubleshooting](../guides/troubleshooting.md).
