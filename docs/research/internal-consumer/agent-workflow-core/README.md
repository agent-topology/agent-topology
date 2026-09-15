# agent-workflow-core

[Repository](https://github.com/milocosmopolitan/agent-workflow-core) ·
[Snapshot](snapshot.json) · [Cross-consumer findings](../README.md)

## Version and role

Baseline: latest published prerelease `v0.1.0.beta.3`, commit
`94cd31f58d8e94d55ea2d952c6db5508539ea53f`, published 2026-09-15.
Also inspected main `876f6a8a4ba863424e1f85bc92f18dce59147957` because campaign
pins that newer commit while git-agent pins the release. Both report package
version `0.1.0b3`; package version alone cannot identify the consumer's code.

This is a runtime-neutral contract library with an optional LangGraph adapter,
not a standalone compiled workflow. Its relevant role is an integration boundary
for producers and trace consumers. [Package metadata](https://github.com/milocosmopolitan/agent-workflow-core/blob/876f6a8a4ba863424e1f85bc92f18dce59147957/pyproject.toml) and
[lockfile](https://github.com/milocosmopolitan/agent-workflow-core/blob/876f6a8a4ba863424e1f85bc92f18dce59147957/uv.lock) show the optional broad LangGraph requirement and locked
`1.2.11`, respectively.

## Source-backed findings

| Finding | Evidence | Support gap and next boundary |
| --- | --- | --- |
| IC-04: observer identity is independently supplied | [Release bridge](https://github.com/milocosmopolitan/agent-workflow-core/blob/94cd31f58d8e94d55ea2d952c6db5508539ea53f/src/agent_workflow_core/adapters/langgraph/observer.py#L30-L66) obtains graph ID from context and run/thread IDs from runtime. | `describe(..., graph_id=...)` must receive an agreed document address. A compile display name or run ID is not a substitute. Build a consumer mapping fixture; no source evidence here proves end-to-end correlation. |
| IC-04: resume identity changed after the release | [Main bridge](https://github.com/milocosmopolitan/agent-workflow-core/blob/876f6a8a4ba863424e1f85bc92f18dce59147957/src/agent_workflow_core/adapters/langgraph/observer.py#L42-L72) prefers optional `event_run_id` over runtime run ID. | Campaign's main-based integration and git's release-based integration need separately pinned replay evidence. Do not assume identical event identity semantics from matching package versions. |
| IC-02/06: model wrappers are ordinary callables | [Model wrapper](https://github.com/milocosmopolitan/agent-workflow-core/blob/94cd31f58d8e94d55ea2d952c6db5508539ea53f/src/agent_workflow_core/adapters/langgraph/model.py#L39-L64) delegates to a runtime-free step; this file is unchanged between tag and main. | A wrapper is not evidence of a nested compiled graph. Topology cannot expose model-attempt internals merely by increasing depth. |
| IC-06: step execution is a separate contract | [execute_node](https://github.com/milocosmopolitan/agent-workflow-core/blob/94cd31f58d8e94d55ea2d952c6db5508539ea53f/src/agent_workflow_core/execution/contracts.py#L333-L372) validates projected state/writes and emits step outcomes; this span is unchanged on main. | State channels, validation, profile policy and execution outcomes are not topology edges. Preserve the separation through runtime events or consumer-owned extensions. |

The tag-to-main diff adds events and notifications and changes the observer bridge;
those additions are not part of the selected release baseline. See the
[immutable comparison](https://github.com/milocosmopolitan/agent-workflow-core/compare/94cd31f58d8e94d55ea2d952c6db5508539ea53f...876f6a8a4ba863424e1f85bc92f18dce59147957).

## Smallest useful follow-up

A consumer adapter fixture should map one graph and two nodes to sanitized core
step events, then check one resumed invocation with a stable logical event run ID.
Record both core commits separately. This tests identity and resume semantics;
real model gateways, notifications, credentials and a full domain workflow are
unnecessary inputs. Evidence remains `source-verified`; this probe has not run.
