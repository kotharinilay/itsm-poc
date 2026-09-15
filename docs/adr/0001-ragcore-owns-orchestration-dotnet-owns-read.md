# 0001. RagCore owns orchestration and execution; the .NET modular monolith owns read

- **Status:** Accepted
- **Date:** 2026-09-15
- **Deciders:** Platform architecture owner
- **Supersedes:** nothing
- **Related:** [0002 — Approval API placement and graph resume path](0002-approval-api-placement-and-graph-resume.md)

## Context and Problem Statement

`Synthia-Platform-Specification.md` §14.1 defines eleven bounded contexts, and §13.4 requires every
application call between them — including service-to-service — to traverse the public edge and the
Gateway. §31.4 shows the grounded-response path as a synchronous chain of those contexts:
`Session → RagCore → Retrieval → Governance → Tool Execution → adapter`.

That decomposition puts an edge-and-Gateway round trip on every internal hop of the hot path, which
the specification itself names as a material cost against the latency objective (§34.2). It also
distributes orchestration across several independently deployed services, so the agent's control
logic, its interruption and resume behaviour, and its execution sequencing are split across
deployment boundaries that change at different rates.

We need a runtime decomposition that keeps the specification's trust and authority rules intact
while collapsing the hop count and giving the agent loop a single owner.

## Decision Drivers

- Orchestration and read models have opposite change rates, runtime profiles and failure modes.
- Every internal gateway hop is latency the grounded-response path cannot spend.
- LangGraph interruption, checkpointing and resume are cohesive; splitting them across services
  makes the authority checks on resume harder to prove.
- Read, listing and dashboard workloads scale and fail independently of the agent loop.
- No architectural rule from the specification's identity, tenancy or governance model may be
  weakened to get any of the above.

## Considered Options

1. **Eleven independently deployed contexts, as written in §14.1.**
2. **One monolith containing everything, including the agent loop.**
3. **Two deployables: RagCore for orchestration and execution, a .NET modular monolith for read.**

## Decision Outcome

**Option 3.** Ownership is split across exactly two application deployables:

| Deployable | Stack | Owns |
|---|---|---|
| **RagCore** | Python 3.12, LangGraph | Conversational orchestration, agent decisions, interruption and resume, execution orchestration, verification, and all state-changing operations |
| **Platform application** | .NET 10 modular monolith | Query, read, listing, dashboard and reporting capabilities. Read-only |

**There is no application-level dependency between them in either direction.** Neither calls the
other as an application API, references the other as a library, or requires the other to be deployed
in order to serve its own requests. They communicate only through shared durable state in PostgreSQL
and through asynchronous messaging.

The §13.4 rule is re-scoped, not relaxed: calls **between deployables** traverse the edge and the
Gateway; in-process calls between modules of the monolith are not service-to-service calls and are
not described as such. Module boundaries inside the monolith are enforced by architecture tests.

### Divergences from the platform specification

Recorded rather than silently absorbed, per constitution Principle X.

| # | Specification | This decision |
|---|---|---|
| 1 | §14.1 — eleven independently addressable bounded contexts | Two application deployables; the contexts become modules of the monolith or components of RagCore |
| 2 | §31.4 — synchronous chain `Session → RagCore → Retrieval → Governance → Tool Execution` | RagCore owns that whole chain internally; no gateway hops between its stages |
| 3 | §13.4 — every service-to-service application call traverses edge and Gateway | Holds between the two deployables. In-process module calls inside the monolith are out of its scope |
| 4 | §37.1 — the customer web portal is deferred beyond Alpha | Included in the monorepo as a scaffolded Angular application, under constitution Principle IX (scaffold, not product) |

Everything the specification states about identity derivation, the closed Gateway header contract,
tenant isolation, deterministic governance, the immutability of work-item authority fields, the
Workload execution principal, audit, and the trigger contract is **unchanged** by this decision.

## Consequences

**Positive.** The grounded-response path loses its internal gateway hops, which changes the
hop-count baseline that §34.2 requires before the latency objective can be committed. The agent loop
has one owner, so interruption, checkpoint and resume are provable in one place. Read workloads scale
and fail independently of orchestration.

**Negative / accepted.**

- **The database schema becomes the contract between the two deployables.** This is the real coupling
  point, and no architecture test catches it. Mitigation: RagCore owns the migrations for every table
  it writes, and the monolith reads only through **explicitly versioned views** it does not own.

  A view is never changed in place. RagCore adds `vw_<name>_v2` alongside `vw_<name>_v1`; the monolith
  migrates on its own schedule; `v1` is dropped in a later release once nothing references it. This is
  expand/contract (ADR-0003) applied to the read contract, and it means a view change needs no
  sign-off gate and blocks neither team — the version number carries the coordination. A CI check
  asserts that no view is altered in place and that a dropped view is unreferenced.
- **The Staff Portal talks to both deployables** — the .NET monolith for the approval queue listing
  and dashboards, RagCore for submitting a verdict. Both through APIM. Because PostgreSQL is the
  single durable store (constitution Principle IV), the read side sees the write immediately; there
  is no eventual-consistency window to design around.
- Two language toolchains, two CI pipelines, two sets of standards to enforce.
- The specification's own §14.1 and §31.4 no longer describe the runtime. Downstream artefacts must
  read this ADR alongside the specification.

## Resolved since acceptance

**Non-consequential writes stay in RagCore.** §32.1 places feedback in the Session context alongside
create-session and send-message, and exposes "submit feedback" on the Customer API. Every write in
that context is therefore a RagCore write, and the monolith's read-only rule stands with **no
exception**. The monolith serves the read side of Session: list sessions, read history, dashboards.

**View contract coordination is by version, not by sign-off** — see the schema-contract consequence
above. No named per-view owner on the monolith side is required, which removes the cross-team review
gate that the original open item assumed.

## Unresolved

- Nothing outstanding for this decision.

## More Information

- Constitution v2.0.0 Principle V (RagCore Orchestrates, the Monolith Reads) and Principle X.
- `Synthia-Platform-Specification.md` §13.4, §14.1, §31.4, §34.2, §37.1.
