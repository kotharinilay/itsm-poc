# 0001. RagCore owns orchestration and execution; the .NET modular monolith owns read

- **Status:** Accepted — **amended in part by [0007](0007-integration-service-boundary.md)**
- **Date:** 2026-09-15 | **Amended:** 2026-09-18
- **Deciders:** Platform architecture owner
- **Supersedes:** nothing
- **Related:** [0002 — Approval API placement and graph resume path](0002-approval-api-placement-and-graph-resume.md)

> **Read this notice before the decision below.** [ADR-0007](0007-integration-service-boundary.md)
> **partially withdraws this record's Divergence #1 and #2.** There are now **three** application
> deployables, not two: `Tool Execution`, `Integration — ServiceNow` and `Integration — Microsoft
> Graph` deploy together as the **Integrations Service**, parallel to RagCore.
>
> What this record still decides, unchanged: RagCore owns orchestration and every state change to
> platform data; the .NET monolith is read-only; the two have no application-level dependency in
> either direction and meet only at PostgreSQL and asynchronous messaging; the schema is the contract
> between them and views are versioned, never altered in place.
>
> What ADR-0007 changed: RagCore no longer performs the external-effect leg and no longer holds
> connector credentials, and a one-directional dependency `RagCore → Integrations` now exists.
> **Where this record and ADR-0007 disagree, ADR-0007 is the later record and governs.**

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

**Option 3.** Ownership is split across two application deployables — **three since ADR-0007**:

| Deployable | Stack | Owns |
|---|---|---|
| **RagCore** | Python 3.12, LangGraph | Conversational orchestration, agent decisions, interruption and resume, execution orchestration, verification, and all state-changing operations *(external effects moved to the Integrations Service by ADR-0007)* |
| **Platform application** | .NET 10 modular monolith | Query, read, listing, dashboard and reporting capabilities. Read-only |
| **Integrations Service** *(added by ADR-0007)* | Python 3.12, FastAPI | The tool catalogue, the connector registry, and all traffic to external systems |

**There is no application-level dependency between RagCore and the monolith in either direction.**
Neither calls the other as an application API, references the other as a library, or requires the
other to be deployed in order to serve its own requests. They communicate only through shared durable
state in PostgreSQL and through asynchronous messaging.

*Scoped 2026-09-18.* That zero-dependency property describes **RagCore ↔ monolith**, not the system.
ADR-0007 introduces one directed edge, `RagCore → Integrations`, with results returning
asynchronously so the graph stays acyclic. Citing this paragraph as a system-wide property is a
misreading of it.

The §13.4 rule is re-scoped, not relaxed: calls **between deployables** traverse the edge and the
Gateway; in-process calls between modules of the monolith are not service-to-service calls and are
not described as such. Module boundaries inside the monolith are enforced by architecture tests.

### Divergences from the platform specification

Recorded rather than silently absorbed, per constitution Principle X.

| # | Specification | This decision | Status |
|---|---|---|---|
| 1 | §14.1 — eleven independently addressable bounded contexts | Two application deployables; the contexts become modules of the monolith or components of RagCore | **Narrowed by ADR-0007.** Three of the eleven — `Tool Execution`, `Integration — ServiceNow`, `Integration — Microsoft Graph` — are now independently deployed as the Integrations Service, which is what §14.1 described. Eight remain RagCore packages |
| 2 | §31.4 — synchronous chain `Session → RagCore → Retrieval → Governance → Tool Execution` | RagCore owns that whole chain internally; no gateway hops between its stages | **Narrowed by ADR-0007.** RagCore owns the chain **as far as Tool Execution**; that leg now crosses a deployment boundary, and the gateway hops it avoided return to it |
| 3 | §13.4 — every service-to-service application call traverses edge and Gateway | Holds between the two deployables. In-process module calls inside the monolith are out of its scope | Holds between **all three**. The `RagCore → Integrations` path is its newest and most load-bearing instance |
| 4 | §37.1 — the customer web portal is deferred beyond Alpha | Included in the monorepo as a scaffolded Angular application, under constitution Principle IX (scaffold, not product) | Unchanged |

**Divergences 1 and 2 shrank rather than grew.** ADR-0007 returns three contexts to the
independently deployed shape §14.1 always described, so the realization now departs from the
specification in *fewer* places than this record originally established.

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

- Nothing outstanding for this decision. Items arising from the 2026-09-18 amendment are recorded in
  [ADR-0007](0007-integration-service-boundary.md) §Unresolved, not here.

## More Information

- Constitution **v3.2.0** Principle V and Principle X. *(This record originally cited v2.0.0's
  Principle V title, "RagCore Orchestrates, the Monolith Reads", which no longer exists; Principle V
  is now "Modular Boundaries Are Mandatory" and its realization paragraph names three deployables.)*
- `Synthia-Platform-Specification.md` §13.4, §14.1, §21.6, §31.4, §34.2, §37.1.
- [ADR-0007](0007-integration-service-boundary.md) — the amendment to this record.
