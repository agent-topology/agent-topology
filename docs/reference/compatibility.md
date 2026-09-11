# Installation and compatibility

[Documentation home](../README.md)

Choose the package for the language of the compiled graph, or install just a
specification package when consuming JSON. These commands select the initial
public preview, not unreleased fixes in the repository.

| Task | Install |
| --- | --- |
| Read documents in Python | `python -m pip install "agent-topology-spec==0.1.0b1"` |
| Extract Python LangGraph graphs or use `agt` | `python -m pip install "agent-topology-langgraph==0.1.0b1"` |
| Read documents in Node.js | `npm install @agent-topology/spec@0.1.0-beta.1` |
| Extract LangGraph.js graphs | `npm install @agent-topology/spec@0.1.0-beta.1 @agent-topology/langgraph@0.1.0-beta.1` |

The Python producer installs its specification dependency. The TypeScript producer
declares it as a peer; install both explicitly. For application code that imports
LangGraph.js directly, also declare `@langchain/langgraph@1.4.14` as a dependency.

| Package | Runtime | Tested framework releases |
| --- | --- | --- |
| `agent-topology-spec` | Python 3.11–3.14 | No framework dependency |
| `agent-topology-langgraph` | Python 3.11–3.14 | LangGraph 1.2.10, 1.2.11 |
| `@agent-topology/spec` | Node.js 20+; CI covers 20 and 22 | No framework dependency |
| `@agent-topology/langgraph` | Node.js 20+; CI covers 20 and 22 | LangGraph.js 1.4.14 |

Both producers reject framework versions without conformance evidence before graph
inspection. A newer installed framework is not automatically supported. Check the
version in the same environment that runs your application:

```bash
python -m pip show agent-topology-langgraph agent-topology-spec langgraph
npm ls @agent-topology/spec @agent-topology/langgraph @langchain/langgraph
```

Python imports use underscores: `agent_topology.spec` and
`agent_topology.langgraph`. The npm packages publish ESM imports and TypeScript
declarations, not a CommonJS `require` entry point or a browser bundle. `agt` is
provided only by the Python producer.

See [release notes](../releases/v0.1.0-beta.1.md) for published artifact identities,
the [contract](../0.1-contract.md#supported-versions) for links to the authoritative
compatibility manifests, and [local development](../maintainers/development.md)
to test unreleased source.
