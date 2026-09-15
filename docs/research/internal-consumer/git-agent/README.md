# git-agent

[Repository](https://github.com/milocosmopolitan/git-agent) ·
[Snapshot](snapshot.json) · [Cross-consumer findings](../README.md)

## Version and implemented boundary

No tags or GitHub releases were found. Baseline and inspected remote main:
`d85d53fa0b24b198e9863c6027806f2440f38bd9`.
[Metadata](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/pyproject.toml) selects core tag `v0.1.0.beta.3`;
[lockfile](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/uv.lock) resolves it to
`94cd31f58d8e94d55ea2d952c6db5508539ea53f` and LangGraph `1.2.11`.

The implemented `issue_resolution` graph has explicit conditional destinations,
model retry loops, approval and effect nodes. The
[factory](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/src/git_agent/graphs/issue_resolution/graph.py#L114-L256)
validates the graph ID and policy and compiles without runtime resource access.
Its nodes are wrappers/callables; no compiled child is added in this factory.
Subgraph depth is therefore not the immediate blocker for this inspected graph.

## Current gaps

| Finding | Source evidence | Consequence and ownership |
| --- | --- | --- |
| IC-03: approval pause is dynamic | [human_approval](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/src/git_agent/graphs/issue_resolution/nodes.py#L1003-L1088) invokes `interrupt()` and validates approval binding. | Runtime evidence must identify pauses. A complete topology cannot prove approved effect execution or valid resume. Consumer/host correlation work. |
| IC-05: a factory is not a CLI object target | [Development adapter](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/dev/issue_resolution.py#L73-L76) exposes `create_dev_graph()`; the production factory requires policy. | `agt` cannot call the factory automatically. An import-safe export module can construct a compiled object; evaluate this small integration recipe before requesting a generic factory loader. |
| IC-04: compile name and topology address differ | [compile call](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/src/git_agent/graphs/issue_resolution/graph.py#L256) sets a display name. | Supply the agreed graph ID to `describe` and map observer events explicitly. The producer default remains `main`. |
| IC-06: same node can represent multiple attempts/effects | [Routing declarations](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/src/git_agent/graphs/issue_resolution/graph.py#L193-L254) include model retries and repeated relation notifications. | Static edges do not identify invocation attempts, successful pushes, PR creation or effect receipts. Event correlation must retain repeated occurrences. |
| IC-06: structural identity is not approval identity | [Approval validation](https://github.com/milocosmopolitan/git-agent/blob/d85d53fa0b24b198e9863c6027806f2440f38bd9/src/git_agent/graphs/issue_resolution/nodes.py#L1028-L1068) binds plan, HEAD, policy and authorization hashes. | Do not substitute topology's structure hash for any of these values. Authorization and idempotency remain git/core/host responsibilities. |

## Smallest useful follow-up

Prove extraction from an import-safe factory export and graph-ID matching using
one two-node graph first. Then use a separate fake approval node with one
pause/resume and a same-node retry event pair to test trace occurrence identity.
No repository mutation, model call, push or GitHub effect is needed to measure
those contracts. This review did not execute the workflow or establish a passing
runtime integration. External fixture/adapter changes belong in git-agent issues;
producer and CLI changes belong in agent-topology.
