# 0007. LangGraph owns the Foundation CLI

- Status: Accepted
- Date: 2026-09-10

## Context

ADR 0006 reserves `agt` as the short command name but does not decide which
Python distribution publishes it. Foundation needs one command:

```bash
agt describe path/to/graph.py:graph --out topology.json
```

That command imports a Python target and asks the LangGraph producer to describe
the compiled object. The specification and producer remain independently
installable, and the dependency direction established by ADRs 0005 and 0006 is
from a producer to the specification, never from the specification to a
producer.

Three ownership models are available.

**The specification distribution could publish `agt`.** This would put the
short command in the most general package, but `describe` would then need to
import an optional producer in the reverse of the architectural dependency
direction. Avoiding that import would require producer discovery or a registry.
A specification-only installation would also expose a command whose only
Foundation operation could not run.

**The LangGraph distribution could publish `agt`.** `describe` can call its
producer directly through an ordinary intra-package import, while the producer
continues to depend on the specification. Installing only the specification
does not install LangGraph or expose a non-functional producer command. This is
the smallest model that serves the one producer and one command in Foundation.
Its cost is that another producer cannot safely publish the same executable.

**A dedicated CLI distribution could publish `agt`.** This gives the command a
producer-neutral home and is the likely shape if one executable must eventually
coordinate several producers or document-only commands. Today it would add a
third independently released package plus a selection or discovery contract
for a producer that does not yet exist. Entry-point discovery, plugins, and
automatic type-based dispatch are all extension mechanisms whose requirements
cannot be learned from the current single-producer workflow.

Python installers do not coordinate two distributions that declare the same
console-script name. Allowing several producer packages to publish `agt` would
therefore make the selected command depend on installation order and is not a
coexistence mechanism.

## Decision

For Foundation, `agent-topology-langgraph` is the sole owner of the `agt`
executable. It exposes `agt describe` and dispatches that subcommand directly to
code in `agent_topology.langgraph`; no producer registry, Python entry-point
discovery, plugin API, or dynamic producer selection is introduced.

The supported installation states are explicit:

- `agent-topology-spec` alone provides the document contract and utilities but
  does not provide `agt`;
- installing `agent-topology-langgraph` installs its specification dependency,
  its supported LangGraph dependency, and the `agt` executable;
- the two distributions remain independently versioned and the specification
  never imports the producer.

Future producer distributions may coexist in the `agent_topology` namespace and
expose their producer APIs, but they must not declare an `agt` console script.
They do not require a common CLI or plugin contract merely to be installable
together. A future producer may use a framework-specific executable if it needs
a CLI before evidence supports a unified one.

If a real workflow later requires one `agt` installation to dispatch across
multiple producers, create a dedicated CLI distribution and supersede this
decision with a concrete selection contract. Ownership must migrate in a
coordinated release: the LangGraph distribution stops publishing `agt` before
the dedicated distribution begins publishing it. Two distributions never own
the command concurrently.

`agt diff` is classified as a producer-neutral document-consumer command. Its
comparison semantics may depend on specification document utilities, but its
command dispatch does not belong in the LangGraph producer. It is outside the
Foundation milestone. Implementing it would be evidence for a dedicated CLI or
consumer distribution and requires the ownership migration above, not a plugin
framework inside the LangGraph package.

## Consequences

- The `agt describe` Feature can put its console-script declaration and command
  implementation in `agent-topology-langgraph` without another ownership
  decision.
- An optional producer is represented by whether its distribution is installed,
  not by a half-functional command in the specification package. Missing
  LangGraph support is resolved by installing `agent-topology-langgraph`.
- Foundation has one command owner, so installation order cannot select between
  colliding `agt` declarations.
- A future producer can be installed beside the LangGraph producer without a
  shared registry. It is not automatically available through `agt`.
- The first real multi-producer or producer-neutral CLI use case supplies the
  evidence needed to design selection and discovery. Until then there is no
  extension API to maintain.
- Adding `agt diff` is not a subcommand-only change to the LangGraph package; it
  remains deferred and carries the cost of moving command ownership.

## Revisiting

Revisit this decision when a second producer needs to participate in the same
command invocation, or when a producer-neutral command such as `agt diff` is
scheduled. A second producer existing only as an importable API is not enough:
the concrete CLI workflow must establish whether explicit selection, target
type dispatch, discovery, or separate executables is appropriate.

Related decisions: ADR 0001 defines the Foundation scope and first intended
consumer, ADR 0005 keeps the core provisional across producers, and ADR 0006
defines package independence, dependency direction, and the `agt` name.
