# 0002. Approval API placement and the graph resume path

- **Status:** Accepted
- **Date:** 2026-09-15
- **Deciders:** Platform architecture owner
- **Related:** [0001 — RagCore owns orchestration and execution](0001-ragcore-owns-orchestration-dotnet-owns-read.md)

## Context and Problem Statement

ADR-0001 leaves the two deployables with no application-level dependency between them. Constitution
Principle III requires that approval and consent decisions enter only through authenticated APIs and
that SignalR never authorize a consequential action. Constitution v2.0.0 Principle X recorded the
resulting open question:

> With no application-level dependency between the .NET monolith and RagCore, the path by which an
> approval verdict recorded through an authenticated API resumes a suspended RagCore graph is
> undefined.

Two things had to be settled: **which deployable hosts the approval write API**, and **what causes a
suspended LangGraph thread to resume** once a verdict exists.

A client-driven resume was proposed: approval received → SignalR to client → client calls a RagCore
API → RagCore reads Postgres → execution continues. It is rejected below.

## Decision Drivers

- The .NET monolith is read-only (ADR-0001). Approval is a write.
- Approved work must survive the client. §41: *"Approved work continues under the Workload identity
  even if the original user later loses access."* §26.4: *"Closing an idle connection ends presence,
  not work."*
- The fifteen-minute post-approval execution window (§17.7, §34.1) is a correctness constraint, not
  a performance target.
- The staff member who approves and the end user whose session is suspended are different principals
  on different surfaces.
- Delivery is at-least-once and duplicates are expected (§27.3).
- The verdict-to-execution boundary should stay a **seam**. Even though both sides currently live in
  the RagCore deployable, a durable queue between them means the resume worker — or a further
  decomposition of RagCore — can be split into its own deployable later without redesigning the
  approval path.

## Considered Options

1. **Client-driven resume.** SignalR notifies the client; the client calls RagCore to resume.
2. **.NET hosts the approval API and calls RagCore.** Rejected immediately — it is exactly the
   application dependency ADR-0001 forbids.
3. **RagCore hosts the approval API; a durable trigger drives resume server-side.**

### Why option 1 is rejected

- **Approved work would die with the client.** If the desktop app is closed, backgrounded or offline
  when the verdict lands, nothing calls RagCore and the fifteen-minute window expires on work a human
  already approved. This inverts §26.4 and breaks the §41 guarantee.
- **Wrong principal.** For `STAFF_APPROVAL` the approver is staff in Mission Control, but the
  notification goes to the end user's session — so an end user's desktop would drive execution of a
  staff-approved action.
- **It makes the client load-bearing on the execution path**, contrary to constitution Principle VII,
  and makes the realtime channel a link in a consequential transition rather than a leaf, contrary to
  Principle III and specification constraint 12 / §26.2.
- **It has none of the reliability model of §27.3** — no at-least-once retry, no message expiry, no
  dead-lettering.

## Decision Outcome

**Option 3.**

**RagCore hosts the approval API.** It likewise hosts every other consequential write — consent,
session take-over, and cancellation — all of which §26.2 places under the same rule. The .NET
monolith stays read-only and hosts the approval *queue listing* and dashboards; it never accepts a
verdict.

The resume path is server-side and durable:

```text
Staff approves via authenticated RagCore API (fresh staff token, through Front Door + APIM)
  → authorize by role-set intersection; validate tenant from the immutable work item
  → first valid verdict wins; persist approved_by, approved_at, expires_at = approved_at + 15 min
  → publish trigger to Service Bus: opaque work identifier + correlation ONLY
  → API returns; the approving request does not drive execution
  → RagCore resume worker consumes the trigger
  → load work item from PostgreSQL; verify approved, active, not cancelled, not expired
  → atomic claim on the work item
  → resume the suspended graph from its PostgreSQL checkpoint
  → execute as Workload (app-only) with an idempotency key to the external system
  → record outcome; verify real state
  → SignalR notifies the client of progress and result
```

SignalR is a **leaf**, never a link. It tells a client that something happened; it never causes it.

**Resolved details:**

- **Transport:** Azure Service Bus. The trigger carries only an opaque work identifier and
  correlation context, and no tenant, requester, role, action, target or approval state (§27.2). A
  consumer that reads authority from the message is defective.
- **Consumer:** a resume worker hosted inside the RagCore deployable. The deployable count stays at
  two.
- **Workload principal:** runs inside the orchestrator runtime for Alpha, per §18.2, as an accepted
  and documented risk rather than a silent one.
- **Two idempotency boundaries, both required** (§27.3): the atomic claim protects the platform from
  duplicate delivery; the idempotency key protects the external system from duplicate invocation.
- **Expiry:** a sweeper in the same worker marks work expired once the window passes with no
  successful claim. Messages carry the same fifteen-minute bound and an expired message dead-letters
  rather than executing.
- **Dead letter:** dead-lettered work is not automatically replayed. It surfaces for operational
  handling (§27.3).

## Consequences

**Positive.** Approval survives client disconnection, app closure and user sign-out. The two
deployables stay decoupled — .NET publishes nothing to RagCore and RagCore calls nothing in .NET;
Service Bus and PostgreSQL carry everything. The at-least-once model, the claim and the idempotency
key are all preserved exactly as specified. Because the queue sits between the verdict and the
execution rather than inside a function call, splitting the resume worker into its own deployable
later is a deployment change, not an application redesign.

**Negative / accepted.**

- Resume is asynchronous, so the approving staff member's request returns before execution completes.
  Progress and outcome reach the relevant surfaces over SignalR.
- Service Bus is on the critical path for approved work. Its latency counts against the fifteen-minute
  window, which makes messaging latency a correctness concern, not only a performance one (§34.1).
- The resume worker is a second process in the RagCore deployable with its own scaling and health
  characteristics.

## Resolved since acceptance

### Retry: there is almost nothing to tune, and that is deliberate

§29.3 already constrains this more tightly than the original open item assumed. Side-effecting
operations are **not** automatically retried by the platform, and failed authorized work does **not**
re-fire. Retry therefore applies only **before the claim**:

| Stage | Policy |
|---|---|
| Trigger delivery | At-least-once by Service Bus; duplicates absorbed by the atomic claim |
| Pre-claim transient failure (database unreachable, message undeserializable) | Bounded exponential backoff with jitter, inside the remaining execution window. Exhausted attempts dead-letter |
| Post-claim execution failure | **No retry.** Record the outcome, escalate, leave the work item non-executable |
| Read operations inside adapters and tools | Retried with backoff in the adapter, per §29.3 |

### A failed authorized action requires fresh authorization

This answers specification **OQ-07**, which the specification left open with this as its recommended
decision. A failed side-effecting action MUST NOT re-fire under an attempt sub-key or any other
mechanism. It requires a new human authorization, because re-firing a failed consequential operation
without a human seeing the failure is the wrong default. The rejected alternative — auto-retry for an
adapter-classified "transient" subset — was declined because that classification would become
security-relevant the moment it existed.

### Dead-lettered approved work raises an alert and surfaces in Mission Control

Work that a human approved but that never executed is a governance failure, not just an operational
one, so it is visible in the product and not only in the ops channel:

- An operational alert fires to the on-call queue.
- The item appears in Mission Control as **approved, not executed**, with its work identifier,
  approver, approval time and expiry.
- Recovery is **fresh authorization**, never replay — consistent with OQ-07 above and with §27.3's
  rule that dead-lettered work is not automatically replayed.

### Desktop script execution is a distinct execution leg on the same machinery

§18.6 settles this. The trigger, claim and resume mechanism is reused unchanged; the **execution leg**
differs:

| | Workload path | Desktop path (§18.6) |
|---|---|---|
| Executor | Workload, app-only | The end user |
| Instruction delivery | N/A — the Workload acts directly | Client **fetches** it from the Customer API, authenticated, bound to the work item. Never over the realtime channel, never inferred from conversation |
| User presence | Not required. Work executes even if the user is gone (§18.7) | **Required.** If the user does not return within the fifteen-minute window the operation expires and needs fresh authorization |
| Failure | Recorded; escalates | Stops the run, records on the case, escalates. No blind retry |
| `executed_by` | Workload, `on_behalf_of` the requester | The end user; audit also records catalogue id, script version, parameters, exit status |

So consent resumes the graph through the same Service Bus trigger; the graph then makes the authorized
instruction available and SignalR notifies the client that it is ready to fetch. SignalR remains a
leaf on this path too.

## Unresolved

- Script distribution and integrity on the endpoint, script elevation, and result attestation remain
  specification open items **OQ-03**, **OQ-04** and **OQ-05**. Each has a recommended decision in §40
  and each is security-critical; they are out of scope for this ADR but block the desktop execution
  path being built.
- Interrupt and resume payload contracts for the three suspension points, and reconciliation between
  a trigger and an unexpected checkpoint position, remain inherited open items under **OQ-08**.

## More Information

- Constitution v2.0.0 Principles III, IV, V, VII and X.
- `Synthia-Platform-Specification.md` §17.7, §18.2, §26.2, §26.4, §27.2, §27.3, §31.5, §34.1, §41.
