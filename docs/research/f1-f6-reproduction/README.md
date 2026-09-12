# F1–F6 reproduction and disposition

Evidence for [Task #95](https://github.com/agent-topology/agent-topology/issues/95),
recorded 2026-09-11. This is a historical evidence record, not a new contract or
a product fix. Accepted ADRs [0001](../../decisions/0001-scope-topology-extraction-and-trace-correlation.md),
[0002](../../decisions/0002-record-what-could-not-be-observed.md),
[0003](../../decisions/0003-canonical-ordering-and-versioned-structure-hash.md),
[0004](../../decisions/0004-rendering-is-not-part-of-the-core-document.md),
[0005](../../decisions/0005-vendor-neutrality-is-provisional-at-v0.md), and
[0006](../../decisions/0006-repository-layout-and-language-boundaries.md) remain authoritative.

## Pinned evidence boundary

| Input | Exact identity |
| --- | --- |
| Original consumer findings | [testbed ce6e96014ace35fed7ddeb047dcbe244f22fbd26](https://github.com/agent-topology/agent-topology-testbed/tree/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/findings) |
| Published npm packages | `@agent-topology/spec@0.1.0-beta.2`, `@agent-topology/langgraph@0.1.0-beta.2`, installed from npm |
| Published source | [cbd2f404a36834fb9ba318500b7832f03ba610da](https://github.com/agent-topology/agent-topology/tree/cbd2f404a36834fb9ba318500b7832f03ba610da); artifact identities remain in the [beta.2 release record](../../releases/v0.1.0-beta.2.md) |
| Current main at investigation | [668bf46c88c37f3c14a4e143eb60c8695df74c6f](https://github.com/agent-topology/agent-topology/tree/668bf46c88c37f3c14a4e143eb60c8695df74c6f); built and packed locally, not substituted with npm packages of the same version |
| Runtime | Node.js `22.16.0`, npm `11.4.1`, LangGraph.js `1.4.14` |
| Airflow source audit | `2.10.5`, [b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf](https://github.com/apache/airflow/tree/b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf) |

[probe.mjs](probe.mjs) is the complete inspected input. It compiles tiny graphs,
extracts documents, validates them and checks their hashes; it never invokes a
graph, router, model, renderer, or Airflow installation. The probe's assertions
describe observed behavior, not desired future fixes. Hand-edited documents are
explicit consumer/validation trials, not producer output or new conformance fixtures.

[beta.2.json](results/beta.2.json) and [main.json](results/main.json) retain every
document and observation. They are byte-identical after replacing only
`provenance.generatedAt` with a fixed timestamp. This agreement applies to these
inputs, not to every possible graph. The published consumer report used the npm
specification; these rechecks also exercise the real JavaScript producer.
They do not claim a separate Python beta.2 behavioral reproduction.
[provenance.json](results/provenance.json) records source digests and locally
built artifact hashes; the [environment lock](environment/package-lock.json)
records exact runtime dependencies, registry URLs and integrity values.
The [verification record](results/checks.md) lists repository checks and retains
the initial command error separately from product observations.

## Disposition table

“Expected” below means the consumer's requested interpretation, not an already
accepted schema requirement. Observations apply to both pinned package sets.

| Finding | Smallest measured input | Expected by consumer | Observed on beta.2 and main | Disposition |
| --- | --- | --- | --- | --- |
| F1: fan-out meaning | Router plus two targets; identical declared destinations, callbacks returning one target versus a list of two. Two sentinels are framework-added. | Distinguish one-of from several selected targets. | Identical extracted graphs and structure hashes. An injected `x-topology-branch` validates and leaves hash v1 unchanged. | Reproduced representational ambiguity. Consumer trial remains a trial. A producer mode contract and a core/hash remedy are unresolved. |
| F2: entry versus orphan | Router plus one undeclared target, with start/router and target/end edges. | Entry identifies the declared start independently of missing routing evidence. | `entryNodeIds` is `["__start__", "target"]`; the `unknown-routing-targets` gap attaches to `router`, not `target`. | Reproduced. Whether to change entry semantics or add local evidence needs a contract decision; this Task does neither. |
| F3: opaque child | One outer node containing a one-node compiled child, compared with an ordinary outer node of the same ID, both at depth 0. | Detect that expansion may reveal a child. | Both core node objects are `{ "id": "nested" }`. A trial dangling `subgraphId` fails validation. | Reproduced missing core marker. “Nothing of any kind” is too broad: framework name metadata can differ, but it is not a documented child-presence contract. Marker design and hash policy remain unresolved. |
| F4: join connectivity | Two sources and one join target. | An edges-only reader finds all connections. | `joins` contains both sources and the target; ordinary incoming edges to `joined` are absent. | Reproduced consumer trap, not a producer defect. ADR 0003 deliberately distinguishes a multi-source join. Guidance/helper proposals remain open; do not duplicate joins into authoritative `edges`. |
| F5: sentinels | One task plus framework start/end nodes. | Hide framework scaffolding without framework-specific rules. | Sentinels have `x-langgraph.sentinel: true`, but no neutral core sentinel type. | Reproduced known provisional boundary. ID matching and extension reading both require framework knowledge. No claim of proven vendor neutrality. |
| F6: package consumption | One ESM import and one CommonJS `require`; package metadata. | Successful import or an error explaining the module format. | ESM succeeds; `require` throws `ERR_PACKAGE_PATH_NOT_EXPORTED`. Root exports contain `types` and `import` only. Runtime dependencies are Ajv `8.20.0` and ajv-formats `3.0.1`. | Module-format failure reproduced on Node 22.16.0. ESM-documentation absence and zero-runtime-dependency claims withdrawn. CommonJS distribution is not authorized by this evidence. |

The probes preserve uncertainty: F1 does not prove runtime concurrency, F2 does
not invent a router-to-target edge, and F3 does not claim that child expansion is
complete. The original gallery's “same shape” comparison is qualitative; its
linear fixture has two ordinary nodes, while its opaque fixture has one. Our F3
comparison uses equal node IDs and cardinality to isolate the missing marker.

## Original evidence and corrections

### F1: consumer injection is not extraction

The pinned [trial source](https://github.com/agent-topology/agent-topology-testbed/blob/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/instrument/src/experiment.ts#L25-L47)
chooses `exclusive`, `concurrent`, or `unknown` by fixture name, then injects
`structure["x-topology-branch"]`. Its
[finding](https://github.com/agent-topology/agent-topology-testbed/blob/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/findings/F1-fan-out-semantics/README.md)
already acknowledges this distinction. Preserve its four reported trials:

| Fixture | Asserted mode | Original reported validation / unchanged hash |
| --- | --- | --- |
| conditional-routing | exclusive | true / true |
| loop | unknown | true / true |
| multi-source-join | concurrent | true / true |
| parallel-fanout | concurrent | true / true |

Those rows are the original report, not four newly executed renderer trials.
Our one minimal injection independently confirms only extension acceptance and
hash exclusion. Neither result establishes correct producer inference, approves
a core field, or proves that deployment or qualification receipts remain valid
after changing producer code. A join declaration alone also does not establish
the selection policy of its upstream divergence.

### Airflow: source-verified corrections, no infrastructure replay

The original [probe](https://github.com/agent-topology/agent-topology-testbed/blob/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/probes/airflow/airflow_probe.py)
labels every `BranchPythonOperator` as exclusive and every other multi-target
operator as concurrent. Its [input](https://github.com/agent-topology/agent-topology-testbed/blob/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/probes/airflow/airflow_dag.py)
happens to return one task ID. Its [transcript](https://github.com/agent-topology/agent-topology-testbed/blob/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/probes/airflow/OUTPUT.txt)
records that classifier's output, not an observed scheduler selection.

Airflow 2.10.5's [BranchPythonOperator](https://github.com/apache/airflow/blob/b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf/airflow/operators/python.py#L259-L274)
accepts single IDs and lists of task/group IDs. The implementation of
[SkipMixin](https://github.com/apache/airflow/blob/b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf/airflow/models/skipmixin.py#L197-L231)
handles a string, an iterable, and `None` separately. Thus a class label cannot
establish exactly-one selection. Non-branch class identity also cannot guarantee
all descendants run or run simultaneously; the same source includes
`ShortCircuitOperator`, and trigger rules and scheduling affect execution.
The versioned [control-flow guide](https://airflow.apache.org/docs/apache-airflow/2.10.5/core-concepts/dags.html#control-flow)
documents those additional conditions. The broad operator-label inference is
withdrawn; runtime selection of the original DAG was not re-executed.

F3's [Airflow analogy](https://github.com/agent-topology/agent-topology-testbed/blob/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/findings/F3-opaque-subgraph/README.md)
supports discoverable grouping only. [TaskGroup source](https://github.com/apache/airflow/blob/b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf/airflow/utils/task_group.py#L69-L90)
describes a task collection and applies relationships to members. Its presence
does not establish a separately compiled child graph, opaque execution boundary,
or equivalence to `subgraphId`. That equivalence remains unproven and cannot be
used as second-producer conformance evidence.

To repeat this bounded source audit, download only these three files and inspect
the linked ranges (digests are recorded in provenance.json):

```bash
rtk proxy gh api 'repos/apache/airflow/contents/airflow/operators/python.py?ref=b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf' -H 'Accept: application/vnd.github.raw+json'
rtk proxy gh api 'repos/apache/airflow/contents/airflow/models/skipmixin.py?ref=b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf' -H 'Accept: application/vnd.github.raw+json'
rtk proxy gh api 'repos/apache/airflow/contents/airflow/utils/task_group.py?ref=b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf' -H 'Accept: application/vnd.github.raw+json'
```

### F2, F4, F5 and F6: retain the narrow claims

The pinned [inline findings](https://github.com/agent-topology/agent-topology-testbed/blob/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/findings/README.md)
remain the original claims. Current producer source independently explains
[entry calculation](https://github.com/agent-topology/agent-topology/blob/668bf46c88c37f3c14a4e143eb60c8695df74c6f/packages/typescript/langgraph/src/internal.ts#L296-L319)
and [sentinel metadata](https://github.com/agent-topology/agent-topology/blob/668bf46c88c37f3c14a4e143eb60c8695df74c6f/packages/typescript/langgraph/src/internal.ts#L239-L262).
The pinned [consuming guide](https://github.com/agent-topology/agent-topology/blob/668bf46c88c37f3c14a4e143eb60c8695df74c6f/docs/guides/consuming-documents.md)
does not give F4's join-to-drawing derivation rule. This is a targeted guide gap,
not proof that joins are undocumented throughout the repository.

The ESM notice exists in the quickstart at both the
[released source](https://github.com/agent-topology/agent-topology/blob/cbd2f404a36834fb9ba318500b7832f03ba610da/docs/getting-started/typescript.md#L7-L10)
and [pinned main](https://github.com/agent-topology/agent-topology/blob/668bf46c88c37f3c14a4e143eb60c8695df74c6f/docs/getting-started/typescript.md#L7-L10).
Whether it should be more prominent is a usability question, not evidence of
absence. The [package manifest](https://github.com/agent-topology/agent-topology/blob/668bf46c88c37f3c14a4e143eb60c8695df74c6f/packages/typescript/spec/package.json)
and installed metadata agree on two direct runtime dependencies. Framework-free
consumption remains supported; it does not mean dependency-free consumption.
The separate [spec-only probe](spec-only.mjs) validates one saved document with
LangGraph absent; its [result](results/spec-only.json) retains the import outcome.

## Repeat the document probes

Run from this repository root after reading probe.mjs. These commands create
temporary environments and a detached checkout of the exact main revision.
Build scripts are the inspected package scripts; the input never grows beyond
three authored nodes per graph (plus the one-node child for F3).

```bash
evidence="$PWD/docs/research/f1-f6-reproduction"
scratch=$(mktemp -d)
rtk proxy mkdir -p "$scratch/beta" "$scratch/main"
rtk proxy cp "$evidence/environment/package.json" "$evidence/environment/package-lock.json" "$scratch/beta/"
rtk proxy cp "$evidence/probe.mjs" "$scratch/beta/"
rtk npm ci --prefix "$scratch/beta"
rtk proxy node "$scratch/beta/probe.mjs" > "$scratch/beta.json"

rtk git worktree add --detach "$scratch/source" 668bf46c88c37f3c14a4e143eb60c8695df74c6f
rtk npm ci --prefix "$scratch/source/packages/typescript/spec"
rtk npm run build --prefix "$scratch/source/packages/typescript/spec"
rtk npm ci --prefix "$scratch/source/packages/typescript/langgraph"
rtk npm run build --prefix "$scratch/source/packages/typescript/langgraph"
rtk npm pack "$scratch/source/packages/typescript/spec" --pack-destination "$scratch/main" --ignore-scripts
rtk npm pack "$scratch/source/packages/typescript/langgraph" --pack-destination "$scratch/main" --ignore-scripts
rtk proxy cp "$evidence/environment/package.json" "$evidence/environment/package-lock.json" "$scratch/main/"
rtk npm ci --prefix "$scratch/main"
rtk npm install --prefix "$scratch/main" "$scratch/main/agent-topology-spec-0.1.0-beta.2.tgz" "$scratch/main/agent-topology-langgraph-0.1.0-beta.2.tgz"
rtk proxy cp "$evidence/probe.mjs" "$scratch/main/"
rtk proxy node "$scratch/main/probe.mjs" > "$scratch/main.json"
rtk proxy diff -u "$scratch/beta.json" "$scratch/main.json"
rtk proxy diff -u "$evidence/results/beta.2.json" "$scratch/beta.json"

rtk proxy mkdir -p "$scratch/spec-only"
rtk npm install --prefix "$scratch/spec-only" --save-exact @agent-topology/spec@0.1.0-beta.2
rtk proxy cp "$evidence/spec-only.mjs" "$scratch/spec-only/"
rtk proxy node "$scratch/spec-only/spec-only.mjs" "$scratch/beta.json"
```

Every assertion and both diffs pass with the recorded Node version. Another Node
version changes the recorded `node` field; compare that separately rather than
silently normalizing it. Keep the scratch checkout until the results are reviewed.
This is reproduction evidence, not release qualification or a supported-runtime
matrix. No beta.2 release history, package version, schema, or hash algorithm was
changed. Contract-gated implementation remains dependent on an accepted ADR and
refined acceptance criteria under parent #94.
