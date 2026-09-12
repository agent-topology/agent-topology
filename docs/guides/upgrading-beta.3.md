# Upgrade from beta.2 to beta.3

[Documentation home](../README.md) · [Release notes](../releases/v0.1.0-beta.3.md)

Status: **Prepared in source; not published.** The installation commands in
this repository's README, package READMEs, and quickstarts still select the
published beta.2 versions. This guide describes what changes for a beta.2
consumer once beta.3 passes registry verification; do not install these
candidate versions from a public registry before then.

## Select the packages

| Package | beta.2 → beta.3 candidate | Runtime | Framework |
| --- | --- | --- | --- |
| `agent-topology-spec` | `0.1.0b2` → `0.1.0b3` | Python 3.11–3.14 | None |
| `agent-topology-langgraph` | `0.1.0b2` → `0.1.0b3` | Python 3.11–3.14 | LangGraph 1.2.10–1.2.11 |
| `@agent-topology/spec` | `0.1.0-beta.2` → `0.1.0-beta.3` | Node.js 20+ | None |
| `@agent-topology/langgraph` | `0.1.0-beta.2` → `0.1.0-beta.3` | Node.js 20+ | LangGraph.js 1.4.14 |

Python uses PEP 440 `0.1.0b3`; npm uses SemVer `0.1.0-beta.3`. Package versions
remain independent of the document format (`0.1`) and structure-hash algorithm
(`1`), neither of which changes in this candidate. The Python producer will
require `agent-topology-spec>=0.1.0b3,<0.2.0`; the npm producer's peer will be
the exact `@agent-topology/spec@0.1.0-beta.3`. LangGraph and LangGraph.js
compatibility ranges are unchanged from beta.2.

## No core stability claim

Nothing below changes `topologyVersion`, `structureHash.algorithm`, or
`structureHash.algorithmVersion`. Every change is either additive
(experimental `x-*` extensions and a new opt-in helper) or a documentation
correction. This candidate does not claim vendor neutrality, a stable v1
contract, or backward compatibility across a future format or hash-algorithm
transition. See the [0.1 contract's known limitations](../0.1-contract.md#known-limitations-and-excluded-consumers).

## Review numeric extension canonical bytes

If a document you produce or compare carries a JSON number inside any `x-*`
extension, its full-document canonical bytes can change between beta.2 and
beta.3. Both specification packages now spell numbers using the same byte
oracle ([ADR 0009](../decisions/0009-numeric-canonical-form.md)) instead of
each runtime's own float formatting — for example, Python's `canonical_json`
no longer emits `0.0` for a value that should read `0`. `structureHash` is
unaffected because no core field is numeric; this is a full-document byte
change only, for documents that use numeric extensions.

1. Identify any producer- or framework-owned extension in your documents that
   carries a JSON number (core fields are all string-typed and never affected).
2. Re-canonicalize affected documents with beta.3 specification utilities and
   compare full-document bytes, not just `structureHash`, before treating a
   byte diff as a regression.
3. Do not assume full-document byte parity between beta.2 and beta.3 for any
   document containing a numeric extension value; equal `structureHash` values
   across beta.2 and beta.3 do not imply equal full-document bytes, and equal
   full-document bytes are not required by the contract.

## Treat new experimental extensions as additive, not authoritative

Both LangGraph producers add three experimental revision 1 extensions in this
candidate: `entry` (confirmed vs. observed execution entry points), sentinel
roles (framework-owned identity), and branch interpretation (inspected
fan-out declarations). Each is additive: existing nodes, edges, joins,
`entryNodeIds`/`exitNodeIds`, completeness gaps, and `structureHash` are
unchanged, and a document produced by a beta.2-era consumer that ignores
unknown fields keeps working. Equal `structureHash` values do not establish
equal extension content — do not infer extension equality from a hash match.
See the [consumer guide](consuming-documents.md#experimental-entry-interpretation),
[sentinel roles](consuming-documents.md#experimental-sentinel-roles), and
[branch interpretation](consuming-documents.md#experimental-branch-interpretation)
sections for what each extension does and does not claim.

## Do not infer an OR-convergence policy

This candidate documents, but does not implement, the boundary between
ordinary-edge connectivity and first-trigger/once-only/reset firing policy at
a target with multiple incoming connections. None of the experimental
extensions above adds a convergence firing-policy fact. A declared
multi-source join keeps its existing all-source-required (AND) meaning,
unchanged. Do not infer either a per-trigger or a first-trigger-with-latch
policy from ordinary edges alone; a stronger OR representation remains future
work requiring its own evidence and contract decision. See the
[consumer guide's OR convergence section](consuming-documents.md#or-convergence-and-first-trigger-firing).

## Try the new join-consumption helper (unreleased)

Current source adds `derived_join_edges` (Python) and `derivedJoinEdges`
(TypeScript) for already-validated structures; the published beta.2 packages
do not export them. They derive one `{joinId, source, target}` record per join
source without adding document fields or changing structure-hash algorithm 1.
Continue reading both `structure.edges` and `structure.joins` directly today;
adopt the helper once beta.3 is published. See the
[join connections section](consuming-documents.md#join-connections) for the
full example and ordering guarantees.

## ESM installation guidance is unchanged

Both npm packages remain ESM-only on Node.js 20+ with no behavior change in
this candidate. See [troubleshooting](troubleshooting.md#esm-installation-errors)
if `require()` fails with `ERR_PACKAGE_PATH_NOT_EXPORTED`.
