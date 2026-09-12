# Producer-generated consumer regression

This is the integrated acceptance evidence for [#103](https://github.com/agent-topology/agent-topology/issues/103),
under [ADR 0008](../../docs/decisions/0008-experimental-consumer-interpretation.md).
It tests current source after #97–#102, based on integration commit
`23eea4276ba3d196b09cb7dd0878ad588073271c`. It does not qualify or publish beta.3.
Package metadata still says beta.2; that is not evidence that released beta.2
emits the experimental extension. The immutable
[beta.2 reproduction](../../docs/research/f1-f6-reproduction/README.md) remains historical evidence.

## Input and measurement

[recipes.json](recipes.json) contains nine minimal native graph recipes, separate
from the independently authored [expected.json](expected.json) interpretation oracle.
Names identify test cases only: neither generator reads expected values or inserts
extension facts. [generate.py](generate.py) and the
[TypeScript generator](../../packages/typescript/langgraph/tests/consumer-fixtures.mjs)
compile each recipe in forward and reversed declaration order, then call public
`describe`. All node and router bodies fail if extraction executes them.

The one/list routers have different return bodies but identical declared targets.
The child/ordinary pair has one outer node with the same ID; only the child case
contains a compiled one-node child. The join/independent pair has two sources and
one target; the source IDs U+E000 and U+10000 expose UTF-16 versus Unicode code point
ordering errors without increasing graph size. The sentinel-name case has three
ordinary nodes named `start`, `end`, and `__start__-user`. Other inputs have at most
three authored root nodes; every graph also has framework-owned sentinels.

[The integration tests](../../tests/test_consumer_regression.py) compare each
producer independently with the oracle before comparing their complete extension
records. Only evidence `source` locators are excluded from semantic parity;
states, values, reasons, evidence kinds, node identities and observed roots must
match. Python uses structural locators such as `compiled.nodes.bound`, while
TypeScript uses its corresponding compiled runtime surfaces; the
[branch](../branch-evidence.md), [child](../subgraph-evidence.md),
[sentinel](../sentinel-evidence.md), and [entry](../entry-evidence.md) evidence
records own the version-pinned truth of those locators. Provenance remains intact.
Only `generatedAt` is normalized when comparing opposite declaration orders.

Both specification implementations consume the identical wire documents through
public validation, canonical serialization, structure hash and join-helper APIs.
The [TypeScript consumer](../../packages/typescript/spec/tests/consumer-fixtures.mjs)
imports no framework or producer. Repository-only ADR validators independently
check the extension; they are not public package APIs. Canonical bytes, hashes,
extension validation results and derived join connections must agree across languages.

Explicit consumer mutations are kept separate from captured producer output:
extension removal/restoration, an unsupported revision and a dangling extension
node reference. Core validation and hashes remain unchanged; opt-in interpretation
reports absent, unsupported or invalid and trusts no sentinel-hiding facts. Source
structure, entries/exits, joins, gaps, limitations and `x-langgraph` data survive.
The original npm beta.2 captures also pass both consumers with absent interpretation.
Legacy arrays remain candidates, and absence never establishes a negative fact.

## Finding disposition

These findings refer to the fixed [testbed revision ce6e960](https://github.com/agent-topology/agent-topology-testbed/tree/ce6e96014ace35fed7ddeb047dcbe244f22fbd26/findings).
This record updates their disposition in current upstream source, not the testbed's
status or released beta.2 history.

| Finding | Evidence in this gate | Disposition and remaining limits |
| --- | --- | --- |
| F1: fan-out meaning | `direct`, `single`, `list`; independent branch oracle, equal one/list hashes, extension parity | **Improved; selection remains unknown.** Unconditional declarations establish `all-declared`; both routers stay `selection-not-observable`. No exclusive/concurrent, scheduling, execution or coverage claim. |
| F2: root versus entry | `orphan`; START and target remain observed roots, only START confirmed, routing gap stays on router | **Improved.** Consumer can distinguish a confirmed entry from an uncertain candidate. Actual destination/causality remains **unknown**; no inferred router-target edge or target gap. END supplies a real known negative entry case. |
| F3: opaque child | `child` versus `ordinary`; equal core hashes but different interpretation | **Improved.** A compiled child is discoverable as `opaque-child` without `subgraphId` or invented graph references. Ordinary callable identity remains **unknown**, not `not-child`. Expanded child metadata remains limited; depth 1/2 and wrapper cases remain in both producer suites. |
| F4: join connectivity | `join` versus `independent`; exact helper endpoints, joinId provenance, Unicode ordering, fresh results, distinct hashes | **Fixed consumer affordance.** Both public helpers expose derived connections while preserving the authoritative join. An edges-only reader can still omit joins; helpers do not establish upstream selection or scheduling. |
| F5: sentinels | `sentinel-names` and all cases; known start/end versus positive ordinary roles, invalid/absent/unsupported fallbacks | **Improved.** A consumer can select trusted sentinel roles without matching IDs or reading `x-langgraph`; storage remains unchanged, with original connections and gaps. Two LangGraph implementations do not prove vendor neutrality. |
| F6: ESM consumption | Existing Node 20/22 clean-installation CI and documented snippet tests from #102; current wire consumer runs as `.mjs` | **Fixed guidance; module boundary retained.** Supported ESM and awaited CommonJS `import()` work. Synchronous `require()` remains unsupported; no CommonJS bundle. The previously withdrawn claims about absent docs and zero runtime dependencies stay withdrawn. |

## Reproduce and retain evidence

From the repository root, with Node 20+ and uv, after inspecting the small recipes:

```bash
rtk npm ci --prefix packages/typescript/spec
rtk npm --prefix packages/typescript/spec run check
rtk npm ci --prefix packages/typescript/langgraph
rtk npm --prefix packages/typescript/langgraph run check
rtk uv run --project packages/python/spec --group test python -m pytest tests/test_consumer_regression.py
rtk uv run --project packages/python/langgraph --group test pytest packages/python/langgraph/tests
rtk uv run --project packages/python/spec --group test python -m pytest packages/python/spec/tests spec/tests tests/test_public_docs.py
```

The integration test retains raw forward/reversed Python and TypeScript documents
under pytest's `producer-captures*` temporary directory. CI runs it in the Node
20/22 producer jobs and uploads that directory plus the consumer mutation bundle
as `consumer-regression-node-<version>`. Captures include exact framework and
producer versions and original timestamps; the CI run supplies the source SHA.
No generated duplicate is checked in as another contract authority.

The integration gate uses the pinned Python LangGraph environment (1.2.11) and
LangGraph.js 1.4.14. Existing producer CI separately exercises Python 1.2.10/1.2.11
boundaries. The shared producer suites, spec/helper tests, public documentation
checks and existing clean package installation tests remain required. No renderer,
Airflow installation, graph execution, schema change or hash revision is involved.

## Local verification

2026-09-12, the integration base above plus this change; Python 3.12.14,
Node 22.16.0, uv 0.12.10. All of these checks passed:

| Check | Result |
| --- | --- |
| Python spec, shared schema/interpretation, release tools, public docs and consumer integration | 169 tests, including 11 new integration tests |
| Python producer suite on LangGraph 1.2.11 | 176 tests |
| TypeScript spec `npm run check` | 34 tests, build, formatting and type checks |
| TypeScript producer `npm run check` on LangGraph.js 1.4.14 | 154 tests, compatibility, build, formatting and type checks |
| `node --test tests/typescript-release-tools.test.mjs` | 10 tests |
| Ruff format/check on `packages/python scripts tests conformance/consumer/generate.py` | Passed |
| Independent Python builds | Both wheels and source distributions built |
| Independent npm packs and `scripts/smoke_typescript_installation.mjs` with both local tarballs | Spec alone, producer with peer, coexistence, documented ESM/CommonJS dynamic import and exports rejection passed |

Node 20 runs in the existing CI matrix; this local record claims Node 22 only.
The original beta.2 captured documents are consumed, not regenerated or relabeled.
