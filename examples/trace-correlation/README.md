# Topology-to-trace correlation example

This example is the first proven consumer of an `agent-topology` document. It
correlates sanitized evidence from a real LangGraph execution with two canonical
topology graphs without importing LangGraph or producer internals during replay.

It reports evidence, not execution coverage. A topology element marked
`unobserved` has no matching event in this fixture; that does not prove it did not
execute. Ambiguous events, graph-specific gaps, and producer-wide limitations stay
visible in the machine result.

## Offline replay and acceptance check

From the repository root, run:

```bash
python3 examples/trace-correlation/correlate.py --check
```

This standard-library-only command needs no network access, secrets, LangGraph, or
installed `agent-topology` package. It prints a human-readable summary and compares
the computed result byte-for-byte in meaning with `fixtures/expected.json`. Add
`--format json` to print the machine-readable result.

The fixture demonstrates:

- a qualified node event matched confidently;
- a runtime-only nested operation with no topology-node match;
- a node event that is ambiguous because its graph identity is absent;
- a graph event with insufficient node identity;
- topology nodes with no matching observation; and
- an element-local routing gap and producer limitation preserved in output.

## Fixture generation and refresh

Fixture refresh is intentionally separate from replay. It compiles two local,
deterministic graphs under the pinned supported LangGraph 1.2.11 release, executes the
approval graph, describes both graphs with the repository producer, sanitizes run
identifiers, timestamps, and application payloads, validates the combined canonical
document, and writes all three fixtures:

```bash
uv run --project packages/python/langgraph --group test \
  python examples/trace-correlation/generate_fixtures.py
```

Review all fixture diffs after refreshing. The checked-in trace provenance records
the framework version, generator, scenario, and sanitization applied. Replay never
runs this command and therefore never executes LangGraph.

This is a repository example, not a published consumer package or stable correlation
API. It does not render the graph, issue policy verdicts, or calculate path coverage.
