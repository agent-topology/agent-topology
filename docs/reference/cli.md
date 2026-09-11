# CLI reference

[Documentation home](../README.md) · [Python quickstart](../getting-started/python.md)

Installing `agent-topology-langgraph` provides `agt` in that Python environment.

```bash
agt describe path/to/graph.py:graph --out topology.json
agt describe path/to/graph.py:graph --out topology.json --strict
agt describe --help
```

`PATH.py:OBJECT` refers to one module-level Python identifier. It does not support
module dotted paths, attribute chains, or factory calls. Define and compile the
graph in the file before naming it as the target.

`--out` is required. The command writes UTF-8 canonical JSON followed by a newline
and replaces an existing destination file. Its parent directory must already
exist. Use a distinct output path, not a source filename.

`--strict` returns status `6` when graph-specific gaps are present. The incomplete
document is still written, so automation can retain it as an artifact and present
its findings. Producer-wide limitations alone do not fail strict extraction.

There is no CLI `--depth` option in 0.1; use the Python API to expand child graphs.
There is no `agt diff`, producer discovery, or TypeScript CLI.

## Exit statuses

| Status | Meaning | Next action |
| --- | --- | --- |
| 0 | Document written | Read completeness and limitations |
| 2 | Invalid command or target syntax | Use `PATH.py:OBJECT` and `--out` |
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
