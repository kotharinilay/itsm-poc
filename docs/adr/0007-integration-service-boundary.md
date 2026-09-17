# 0007. The Integrations Service boundary

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** Platform architecture owner
- **Supersedes:** nothing
- **Amends:** [0001 — RagCore owns orchestration and execution](0001-ragcore-owns-orchestration-dotnet-owns-read.md) (Divergence #1, partially withdrawn)
- **Related:** [0002](0002-approval-api-placement-and-graph-resume.md), [0003](0003-database-migrations-and-rollback.md), [0005](0005-third-party-target-systems.md)

> **Numbering note.** This record was requested as `0006`. That number is held by
> [0006 — The desktop renderer origin](0006-desktop-renderer-origin-and-csp-nonce.md), which is
> Accepted, and the index rule in `README.md` is that a number is never reused. Issued as `0007`.

## Context and Problem Statement

`Synthia-Platform-Specification.md` §14.1 names eleven bounded contexts, three of which concern
external systems: `Tool Execution`, `Integration — ServiceNow` and `Integration — Microsoft Graph`.
§32.7–§32.9 give each one a full boundary definition, and §9.2 drew all three as separate components
reached from the Gateway and from nothing else.

**ADR-0001 collapsed them into RagCore**, recorded as its own Divergence #1: *"eleven independently
addressable bounded contexts → two application deployables; the contexts become modules of the
monolith or components of RagCore."* That was the right call for the orchestration chain, whose hop
count the specification itself names as a material cost (§34.2). It had a consequence that was
accepted at the time and has since become the binding one:

**The RagCore runtime resolves per-organisation credentials for every customer system and holds the
only egress path to them.** §18.2 and §35.2 record this as an accepted security risk with a named
target structure (OQ-02). A compromise of the orchestrator — the component that processes untrusted
model output, retrieved content and chat text — yields ServiceNow, Microsoft Graph, OneLogin and Duo
credentials for every onboarded organisation.

We need the integration boundary to be a runtime boundary, without weakening any identity, tenancy,
governance or audit rule, and without reopening the hop-count cost on the reasoning path.

## Decision Drivers

- The blast radius of an orchestrator compromise currently includes every customer system credential.
- Reasoning and external egress have opposite trust profiles: one consumes untrusted input by design,
  the other holds the platform's most valuable secrets. Co-locating them is the wrong seam.
- §14.1's contexts already describe this boundary; the divergence was the deployment, not the design.
- Constitution Principle V permits a context to become a separately deployed service **only** by an
  explicit ADR, and warns that premature distributed decomposition is a defect.
- Execution and conversation scale and fail differently. An external system's outage should not be a
  conversational outage.
- No rule from the identity, tenancy, governance or audit model may be weakened to obtain any of this.

## Considered Options

1. **Keep integrations inside RagCore.** Status quo. Rejected: leaves OQ-02's most damaging component
   unaddressed, and leaves the specification's §14.1 and §9.2 describing a structure that does not exist.
2. **Split RagCore into user-facing and execution runtimes**, as §18.2 recommends for OQ-02. Separates
   the *platform* credential classes but not the *connector* credentials, which remain in whichever
   runtime holds the adapters. Addresses the smaller half of the problem.
3. **Promote the three integration contexts to one separately deployed Integrations Service.** Accepted.
4. **Promote each of the three to its own service.** Rejected: three deployables where one suffices,
   with no boundary between them that anything enforces. Exactly the premature decomposition
   Principle V names as a defect.

## Decision Outcome

**Option 3.** `Tool Execution`, `Integration — ServiceNow` and `Integration — Microsoft Graph` deploy
together as the **Integrations Service**, parallel to RagCore. Their responsibilities are unchanged;
their runtime placement is not.

**There are now three application deployables**: RagCore, the Integrations Service, and the read-only
.NET monolith.

### Service boundary

**Owns** — tool catalogue · connector registry · tenant tool configuration · access checks · policy
checks at execution · operation execution · MCP client · MCP connector and server integration ·
external API calls · credential lookup · result normalization · external idempotency · execution
records · integration telemetry, audit and trace.

**Does not own** — user conversation · LangGraph reasoning · **tool-selection reasoning** · approval
waiting and its UI · graph interrupt and resume · **execution-treatment assignment** · **role-set
intersection** · final issue verification and the conclusion drawn from it · the ticket-close decision
· **the atomic claim** (idempotency boundary 1, which stays with the authority record).

**The service executes; it never decides.** It repeats every authority *fact* so that a mistaken or
compromised caller cannot cause an unauthorized effect — and it originates no authorization, because
a second policy authority is one that can disagree with the first.

### Communication patterns

Three paths. No other path exists, and no direct route between the deployables may exist.

| # | Path | Transport |
|---|---|---|
| 1 | Tool catalogue: RagCore → Front Door + WAF → APIM → Integrations | Synchronous HTTPS, workload audience, app-only, distinct app role |
| 2 | Synchronous system-of-record operations: RagCore → APIM → Integrations → ServiceNow | As above |
| 3 | Tool execution: RagCore → Service Bus → Integrations, and Integrations → Service Bus → RagCore | Asynchronous, a dedicated queue in each direction |

**The durable job record is the mechanism.** RagCore selects the capability and its parameters and
writes them to an `integration_job` row in the same transaction as the state change. The message
carries `jobId`, `correlationId` and `kind` — nothing else. Integrations reads the instruction from
the row, never from the message.

```text
The message causes work to happen.
The durable job record provides the instruction, the authority and the tenant context.
```

This is the pattern §18.5 already mandates for execution triggers, applied to a second seam. It is
why **the trigger contract's payload rule survives unamended**: the envelope keeps three fields, and
only the closed kind set extends, by `integration.execute`, `integration.completed` and
`integration.failed`.

### Security implications

**Improved.**

- **Connector credentials leave the orchestrator.** The Integrations Service holds the Key Vault role
  for per-organisation connector secrets; RagCore's managed identity does not. An orchestrator
  compromise no longer yields customer-system credentials. This discharges the most damaging half of
  OQ-02; the narrower question of separating RagCore's own delegated and Workload credential classes
  remains open.
- **The egress path is singular and enforceable.** One component can reach ServiceNow, Graph and MCP
  servers, which makes `FR-EXT-011` a deployment property rather than a convention.
- **Authorization is re-established at a real boundary.** Every authority fact is re-verified against
  durable state at the point of effect, not inherited from a caller.

**Unchanged, and re-proved rather than re-argued.**

APIM remains the sole trust boundary and the only place identity is derived. The Integrations Service
MUST NOT parse a token, MUST NOT trust an identity header a caller supplied, and MUST NOT be reachable
by any path that bypasses the Gateway. Managed identity throughout; Key Vault as the sole secret
source. Tenant never from a client field, a message payload, a token `tid`, model output or tool
output. Correlation by W3C Trace Context on every hop. One audit store. Both idempotency boundaries.
Tenant isolation at every layer; least privilege; no global toolset.

**New, and load-bearing.**

**The Integrations Service must not be able to modify the instruction it was given.** It may update
the result fields of a job row, addressed by identifier, and nothing else. `catalogue_id`, `version`,
`parameters`, `tenant_id` and the job's authority fields are not writable by it. A service that could
rewrite its own instruction could execute an operation other than the one governance authorized — a
Principle VIII hard failure. **Enforced at the database permission boundary**, in the manner of
`0017_work_item_immutability` and `0019_database_principals`, never in application code.

### Data ownership

| Record | Owner | Where |
|---|---|---|
| Operation catalogue entry — treatment, accepted roles, risk tier, commands, content hash | **Governance, unchanged** | `platform` |
| Connector binding — connector, endpoint, signing profile, idempotency policy | **Tool Execution** (new; exists nowhere today) | `integration` |
| Tenant tool entitlement | **Tenant & Configuration, unchanged**; read by Integrations through a published view | `platform` |
| Credential reference | Tenant & Configuration; **material in Key Vault, resolved only by Integrations** | `platform` / Key Vault |
| Integration job | **RagCore.** Integrations reads it and writes **only** its result fields | `platform` |
| Execution record — what was attempted externally | **Tool Execution** | `integration` |
| `operation` — what the platform concluded | **RagCore, unchanged** | `platform` |
| Audit event | **Audit, unchanged — one store** | `platform` |

**Execution treatment does not move.** It is deterministic governance's decision under Principle III,
and placing it behind a service boundary from the authority that owns it would be the one change here
that weakens the governance model.

**One database, two schemas, one Alembic project.** Integrations reads platform state through
published `vw_*` views only, holds no write grant on any platform base table, and owns the
`integration` schema outright.

### Divergences from the platform specification

None outstanding. This ADR **restores** §14.1, §32.7–§32.9 and §9.2 to describing the runtime, by
withdrawing ADR-0001's Divergence #1 for three of the eleven contexts. The specification was amended
in the same change (§9.1, §9.2, §9.3, §13.4, §14.1, §18.2, §21.3, §21.4, §21.6, §22.1, §23.1, §27,
§29.2, §31.4, §31.5, §31.7, §32.7–§32.9, §33, §35.2).

ADR-0001's remaining divergences stand: two of the eleven contexts still deploy as modules rather
than services, and the monolith remains read-only with no application dependency in either direction.

## Consequences

**Positive.**

- Customer-system credentials are outside the runtime that processes untrusted input.
- §14.1 and §9.2 describe the runtime again; downstream artefacts no longer need ADR-0001 as an
  erratum for the integration path.
- Execution scales and fails independently of conversation. An external outage degrades to guidance
  and escalation rather than stopping the session.
- Authority is re-checked at the point of effect, which is where it matters and where it was
  previously only in-process.

**Negative / accepted.**

- **Gateway hops return to the tool path.** ADR-0001 removed them; this restores two for the
  synchronous paths. §34.2's hop-count baseline moves again, and **OQ-06 cannot be closed until it is
  re-measured**. No performance figure is an acceptance criterion in the interim.
- **An execution is now two asynchronous hops rather than an in-process call**, inside the same
  fifteen-minute window. The budget is tighter in real terms even though the rule is unchanged.
- **A third deployable**: another pipeline, another image, another identity, another set of contract
  documents, another database principal.
- **A directed application dependency now exists** — RagCore → Integrations. ADR-0001's
  zero-dependency property survives only between RagCore and the monolith and must be re-scoped
  rather than cited as written. Results return over Service Bus rather than as a call, which is what
  keeps the graph acyclic; **a callback from Integrations to RagCore would turn two services into a
  distributed monolith** and is the single edge most worth refusing in review.
- **Two policy evaluation points.** Mitigated by the fact/decision split, but it is real: a fact
  re-verified in two places can be read differently in two places, and the check sets must not drift.

## Migration impact

**No application code changes under this record.** It is an architecture decision; the plan and task
artefacts are updated separately.

| Area | Impact |
|---|---|
| **Moves substantially unchanged** | The ServiceNow, Graph, OneLogin and Duo adapters; the MCP client; the typed HTTP layer; boundary validation; credential resolution; the derived idempotency key; availability reporting. They are already ports-and-adapters, and the target stack is Python on the existing baseline, so these relocate rather than being rewritten |
| **Refactored** | The execution leg splits — invocation and verification move, the conclusion stays. The tool, case, directory and discovery ports become remote on the RagCore side. The graph's execution node becomes dispatch-and-suspend. ServiceNow writes in the application layer route through the new service |
| **Redesigned** | The gate outcome cannot cross a process boundary as an asserted value and must be re-derived. The connector registry is new. Queue-and-replay on system-of-record outage moves with its durability story |
| **Schema** | New `integration_job` table and its column-scoped grants — **the first migration, and the one to review as DDL rather than prose**. New `integration` schema. A new published view exposing the operation instruction |
| **Infrastructure** | New Container App, Dockerfile, managed identity and APIM backend under `/api/workload/v1/integrations/`; two new Service Bus queues; RagCore's Key Vault role for connector secrets **removed**, not duplicated |
| **Contracts** | A sixth emitted OpenAPI document, under the same five CI gates |
| **Tests** | Contract, authorization, architecture dependency, tenant isolation, idempotency, concurrency, governance, adapter, configuration, integration, security and end-to-end are all owed. **The direct-path refusal proof (`FR-DEMO-004a`, `SC-DEMO-003a`, `SC-DEMO-003b`) is the most important to extend**, because the new RagCore → Integrations edge is exactly the shape a bypass takes |

## Unresolved

- **The exact synchronous route list**, and specifically which ServiceNow operations are synchronous.
  §22.3 lists six write classes and classifies all of them `AUTO`; §22.5 makes only case creation
  clearly blocking. Met before the contract is frozen.
- **The result-column set on the job row and the `GRANT` expressing its column scope.** Follows from
  the decision above but must be written and reviewed as DDL.
- **OQ-02's remainder** — separating RagCore's delegated and Workload platform credential classes.
- **OQ-06** — the latency re-baseline, which this change defers again.

## More Information

- `Synthia-Platform-Specification.md` §21.6 (the Integrations Service), §13.4, §14.1, §18.2, §27.2,
  §29.4, §32.7–§32.9, §33, §35.2, §40.
- Constitution Principles I, III, IV, V, VI, VIII and X.
- `docs/architecture/integrations-service-delta.md` — the reconciliation and the decision record
  behind this ADR.
