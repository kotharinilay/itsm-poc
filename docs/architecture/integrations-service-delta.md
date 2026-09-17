# Architecture Delta — Integrations as a Separate Deployable

- **Status:** Proposed — reconciliation only. **No implementation may begin from this document.**
- **Date:** 2026-09-17
- **Change:** Promote the integration boundary out of RagCore into an independently deployed
  **Integrations Service**, parallel to RagCore.
- **Source material reconciled:** `Synthia-Platform-Specification.md`, `.specify/memory/constitution.md`
  v3.1.0, ADR-0001 through ADR-0006, `specs/001-platform-scaffold/{spec,plan,tasks,data-model}.md`,
  `specs/001-platform-scaffold/contracts/*`, `build/infra/*`, `build/policy/*`, and the RagCore
  integration implementation under `ragcore/src/ragcore/{integrations,execution,governance}/`.

---

## 0. The finding that governs everything below

**The platform specification already describes this change. The implementation artefacts do not.**

`Synthia-Platform-Specification.md` §14.1 names `Tool Execution`, `Integration — ServiceNow` and
`Integration — Microsoft Graph` as three of eleven bounded contexts. §32.7–§32.9 give each one
inputs, outputs, owned data, an authorization boundary and a synchronous/asynchronous nature. §9.2
draws `TOOL`, `SNAD` and `GRAD` as separate components, each reached from `GW` (APIM) and from
nothing else. §13.4 already forbids a direct service-to-service path between them.

What collapsed them into RagCore was **ADR-0001**, recorded as its own Divergence #1: *"eleven
independently addressable bounded contexts → two application deployables; the contexts become
modules of the monolith or components of RagCore."*

So this is **not a specification change**. It is a **partial withdrawal of ADR-0001's divergence for
three contexts**, moving the realization back toward what the specification always said. That framing
matters because it determines the governance route: constitution Principle V states that *"a boundary
MUST NOT become a separately deployed service without an explicit architectural decision recorded as
an ADR"*, and Principle X requires that a change of this size be recorded rather than encoded in
implementation.

**A new ADR — ADR-0007 — is a precondition for any code change.** It must supersede ADR-0001 in part,
not silently contradict it.

One consequence is worth stating up front because it is a benefit rather than a cost: specification
§18.2 and §35.2 record the co-location of two credential classes in the RagCore runtime as an
**accepted security risk** with a named target structure (OQ-02). Moving external credential
resolution and external egress into a separate runtime is a direct step toward closing OQ-02. The
ADR should claim that credit explicitly, because it is the strongest justification the change has
against Principle V's counter-rule that *"premature distributed decomposition is a defect."*

---

## 1. Architecture delta

### 1.1 What changes

| Aspect | Current (ADR-0001) | Target |
|---|---|---|
| Application deployables | 2 — RagCore (write/orchestration), .NET monolith (read) | **3** — RagCore, Integrations Service, .NET monolith |
| Contexts inside RagCore | Session·Work·Governance·Approval·Agent·Retrieval·**Tool Execution**·**Integration—ServiceNow**·**Integration—Graph**·Tenant&Config·Audit·Ingestion (write sides) | The same **minus** the three integration contexts |
| External egress (ServiceNow, Graph, MCP, OneLogin, Duo) | RagCore, in-process via `integrations/` | **Integrations Service only** |
| Per-tenant external credential resolution | RagCore runtime, via `integrations/credentials.py` | **Integrations Service only.** RagCore's managed identity loses the Key Vault role for connector secrets |
| Tool invocation | In-process call `ExecutionLeg → ToolExecutionPort` | **Service Bus command → Integrations; result → Service Bus back to RagCore** |
| Tool catalogue read | In-process `governance/catalogue.py` | **Synchronous HTTPS, RagCore → APIM → Integrations** |
| Synchronous ServiceNow operations | In-process adapter call | **RagCore → APIM → Integrations → ServiceNow** |
| Access + policy check | Once, in RagCore's gate, before invoking | **Twice** — RagCore's gate at proposal, Integrations' re-check at execution |
| Application dependency count | Zero between deployables | **One directed edge: RagCore → Integrations.** The zero-dependency property of ADR-0001 no longer describes the system as a whole |

### 1.2 What does not change

Every one of these is preserved verbatim and must be re-proved, not re-argued:

- APIM is the trust boundary; identity derived exactly once; no service parses a token (Principle I).
- No direct service-to-service network path (§13.4). The RagCore → Integrations edge traverses
  Front Door + WAF + APIM like every other call.
- Managed identity everywhere the resource supports it; Key Vault as the sole secret source.
- Tenant derived from trusted identity or from durable state — never from a client field, a message
  payload, model output or tool output.
- W3C Trace Context correlation propagation on every hop, log, span, trigger and audit record.
- Durable audit for every consequential action, carrying the full actor chain (§28.2).
- Both idempotency boundaries (§29.4) — neither substitutes for the other.
- Tenant isolation at every layer; least privilege; no global toolset.
- OpenAPI generated from running services, one document per audience per deployable, never merged.
- RFC 9457 errors, `/health/live` · `/health/ready`, the resilience and observability standards.
- **The model proposes; deterministic governance authorizes** (Principle III). The split does not
  move any decision into the model's reach — it adds a second deterministic check, it does not
  relocate the first.

### 1.3 The responsibility line, restated against the existing contexts

| Capability | Current owner | Target owner | Basis |
|---|---|---|---|
| Tool catalogue (what a capability *is*) | Governance | **Integrations** (see D-04) | Requested change; conflicts with §33 |
| Execution **treatment** (`AUTO`/`END_USER_APPROVAL`/…) | Governance | **Governance, unchanged** | Principle III — treatment is a governance decision, not an integration one |
| Connector registry | *does not exist as a durable concept* | **Integrations** | New |
| Tenant tool configuration / entitlement | Tenant & Configuration (§33) | **Integrations** (see D-04) | Requested change; conflicts with §33 |
| Access check at execution | Tool Execution, in RagCore | **Integrations** | §32.7 |
| Policy check at execution | Governance gate, in RagCore | **Both** — RagCore at proposal, Integrations at execution | Requested change |
| Operation execution | `execution/executor.py` in RagCore | **Integrations** | §32.7 |
| MCP client and MCP server integration | `integrations/mcp/` in RagCore | **Integrations** | §21.2, ADR-0005 |
| External API calls (ServiceNow, Graph, OneLogin, Duo) | `integrations/*/` in RagCore | **Integrations** | §21.3, FR-EXT-011 |
| Credential lookup | `integrations/credentials.py` in RagCore | **Integrations** | §21.4 |
| Result normalization / boundary validation | `integrations/validation.py` in RagCore | **Integrations** | FR-EXT-021 |
| Idempotency — external key (boundary 2) | RagCore | **Integrations** | §29.4 |
| Idempotency — atomic claim (boundary 1) | Work, in RagCore | **RagCore, unchanged** | §29.4, §32.2 — the claim is the platform's boundary and belongs with the authority record |
| Execution record | `operation` row, RagCore | **Split** — see D-05 | Conflict |
| Integration telemetry / audit / trace | RagCore | **Integrations emits; Audit remains one store** | §28.1, Principle VIII |
| User conversation, LangGraph reasoning, tool-selection reasoning | RagCore | **RagCore, unchanged** | §32.5 |
| Approval waiting, interrupt/resume | RagCore + Approval | **Unchanged** | ADR-0002 |
| Final verification, ticket-close decision | RagCore | **RagCore, unchanged** | FR-AGENT-008, ADR-0004 |

**The verification split is subtle and must not be lost.** `execution/executor.py` today performs
execution *and* verification in one place, deliberately: verification is a separate call to a
separate tool named by the catalogue, so that "the thing that acted" cannot attest to itself. Under
the split, the *verification call* is an external call and therefore belongs to Integrations, but the
*conclusion* — whether the platform may tell a user the issue is resolved — is RagCore's
(`may_report_resolution`). Integrations returns `server_confirmed | client_attested | contradicted`
as a fact about what it observed; RagCore decides what to say. Collapsing those two would let an
executing service declare its own success, which is exactly what `client_attested` exists to prevent.

---

## 2. Impacted documents

### 2.1 Architecture authority

| Document | Sections | Nature |
|---|---|---|
| `Synthia-Platform-Specification.md` | §9.1 (zone table), §9.2 (runtime diagram), §9.3 (deployment profile) | Add the third deployable; `TOOL`/`SNAD`/`GRAD` become one named service |
| | §13.4 | No change to the rule; add the new edge to the worked example |
| | §14.1, §14.3 | The three contexts acquire a deployment, not a new responsibility |
| | §18.2 | **Directly affected.** The Workload execution leg is no longer wholly inside RagCore |
| | §21.3, §21.4, §21.5 | Adapters, credential resolution and egress acquire a single owning runtime |
| | §27.1, §27.4 | New queues and two new event kinds |
| | §31.4, §31.5, §31.7 | The canonical workflows gain a hop and change shape |
| | §32.7, §32.8, §32.9 | "Exposes" changes from *Internal* to a published API + message contract |
| | §33 | **Conflict.** Ownership rows for catalogue, binding, entitlement and credential reference |
| | §35.2, §40 (OQ-02) | Partially discharged — record the improvement rather than leaving the risk as written |

### 2.2 Engineering governance

| Document | Sections | Nature |
|---|---|---|
| `.specify/memory/constitution.md` | Principle V, realization paragraph | **Obsolete as written.** "RagCore owns orchestration, execution and all state-changing operations; the .NET modular monolith is read-only" no longer describes the system |
| | Principle V, schema-contract paragraph | "RagCore owns every migration" — must be amended or scoped |
| | §Engineering Standards → Resilience | "RagCore calls MCP servers, the system of record, Graph and the realtime service" — **factually obsolete** |
| | §Idempotency and messaging | "the monolith is read-only and publishes nothing" is still true; the sentence's framing of *two* deployables is not |
| | §.NET baseline / §Python baseline | Only if Integrations introduces a stack choice (see D-11) |
| | Version | At minimum MINOR; MAJOR if Principle V's realization is read as a redefinition |

### 2.3 Decision records

| ADR | Action |
|---|---|
| **ADR-0007 (new)** | *Integrations as a separately deployed service.* Required by Principle V. Must record the conflict with ADR-0001, the justification against "premature distributed decomposition is a defect", the latency cost against §34.2, and the OQ-02 credit |
| ADR-0001 | **Amend.** Divergence #1 is partially withdrawn; the "no application-level dependency between them" consequence is scoped to RagCore ↔ monolith |
| ADR-0002 | **Review, likely unchanged.** Approval writes and the resume path stay in RagCore; only the leg *after* resume becomes remote |
| ADR-0003 | **Amend or extend.** "Alembic owns every migration" now has a second schema owner |
| ADR-0005 | **Amend.** OneLogin and Duo adapters relocate; the decision itself stands |
| `docs/adr/README.md` | Index update in the same change |

### 2.4 Feature artefacts

| Document | Nature |
|---|---|
| `specs/001-platform-scaffold/spec.md` | `FR-EXT-011` (single owning integration boundary) is now satisfied by a *service*; `FR-DEMO-004a`/`SC-DEMO-003a`/`SC-DEMO-003b` (the direct-path refusal proof) must extend to the third deployable |
| `plan.md` | §Project Structure, §Dependency direction, §Where each bounded context lives, §OpenAPI contract emission (five documents → seven), Stage list |
| `tasks.md` | Phase 9 (T128–T138) is retro-scoped; a new phase is required; `[X]` tasks whose files move need an explicit disposition |
| `data-model.md` | New entities; ownership column changes; schema-boundary statement |
| `contracts/README.md` | Routing table gains rows; **rule 4 needs its synchronous form re-examined** (see D-01/D-03) |
| `contracts/workload-api.md` | Either extended or joined by a sibling |
| `contracts/triggers.md` | **Envelope and kind set change** — a closed set is being opened |
| `contracts/read-views.md` | A new published view is required (see D-06) |
| `contracts/integrations-api.md` | **New** |
| `quickstart.md`, `research.md`, `contract-freeze.md`, `implementation-freeze.md`, `checklists/*` | Consequential updates |

### 2.5 Build and infrastructure

| Artefact | Nature |
|---|---|
| `build/infra/apim/apis.json` | New backend `integrations`; new API entry; routing comment |
| `build/infra/apim/workload.v1.xml` (or a new policy) | Per D-02 |
| `build/infra/identity/managed-identities.json` | New identity for Integrations; **RagCore's Key Vault and external-egress roles are removed**, not merely duplicated |
| `build/policy/azure-identity.json` | The registry scan must cover the new files |
| `build/policy/edge-trust.json` | The third hop gains a third backend |
| `build/docker/integrations.Dockerfile`, `build/docker/containerapps/integrations.yaml` | New |
| `build/contracts/integrations/` | New emitted contract directory |
| `build/scripts/check-boundaries.sh`, `check-edge-path.sh`, `verify-*-guard.sh` | Boundary and edge guards must know about three deployables |
| `.github/workflows/contracts.yml` and the per-stack pipelines | A third pipeline; the five contract gates run over more documents |

---

## 3. Impacted components

### 3.1 Moves substantially unchanged

These are already written as adapters behind ports, with the external contract, retry, backoff,
idempotency and dead-lettering inside them. They change import paths and composition root, not
design.

| Path | Notes |
|---|---|
| `integrations/servicenow/adapter.py` | |
| `integrations/graph/adapter.py` | |
| `integrations/onelogin/adapter.py`, `integrations/duo/adapter.py` | |
| `integrations/mcp/client.py` | The `discover`/`invoke` type separation must survive the move intact — it is the enforcement mechanism for "discovery is not entitlement" |
| `integrations/http.py` | Typed clients, pooled lifetime, explicit timeout on every call |
| `integrations/validation.py` | Boundary contract validation, FR-EXT-021 |
| `integrations/credentials.py` | Moves **with its port declaration**; Principle V puts the port with the consumer, and the consumer is now inside Integrations |
| `execution/idempotency.py` | `derive_key` is deterministic over `(tenant, work_item_id, operation_id)` — this is what makes the remote boundary safe |
| `execution/availability.py` | "Entitled but unreachable" reporting, FR-EXT-022 |

### 3.2 Refactored

| Path | Change |
|---|---|
| `execution/executor.py` | **Splits.** `ExecutionLeg.run` (invoke + verify) moves to Integrations. The `GateOutcome`-is-`PROCEED` precondition cannot travel as an in-process object; it becomes an Integrations-side re-derivation from durable state. `ExecutionReport.may_report_resolution` **stays in RagCore** |
| `application/ports.py` | `ToolExecutionPort`, `CaseSystemPort`, `DirectoryPort`, `CapabilityDiscoveryPort`, `IdempotencyStorePort` change from in-process ports to **remote** ports on the RagCore side (Service Bus command / HTTPS client) and become *implemented* ports on the Integrations side |
| `graph/nodes/execution.py` | Becomes dispatch-and-suspend rather than call-and-return. The execution node no longer holds the result; a second resume completes it |
| `application/cases.py`, `application/escalation.py` | ServiceNow writes route through Integrations. Under the target, **RagCore must not call ServiceNow directly**, and these are RagCore's direct callers today |
| `messaging/publisher.py`, `messaging/outbox.py`, `workers/resume_worker.py` | New queues, new envelope kinds, a result-consuming path that does not exist |
| `config/composition.py`, `config/settings.py` | Integration settings and secret references leave RagCore |
| `observability/*` | Duplicated, not shared — Principle VI forbids forcing unrelated boundaries into a shared abstraction. Duplication across the boundary is the cheaper error |

### 3.3 Must be redesigned

| Area | Why |
|---|---|
| `governance/catalogue.py`, `governance/policy.py`, `governance/conditions.py` | The requirement that *"Integrations must repeat access/policy checks at execution time"* means a **second evaluator over the same catalogue data**. That collides with Principle IV ("a second durable source of truth MUST NOT be introduced where the specification already names an authority") unless one side is unambiguously the reader. See **D-04** and **D-12** |
| `governance/gate.py` | `GateOutcome` is currently an in-process value carrying the whole evaluation. Across a process boundary it either becomes a serialized claim that Integrations must not trust, or it is re-derived. **It must be re-derived** — a serialized `PROCEED` is a model-free but still *asserted* authority, and Principle I forbids asserted authority |
| `integrations/servicenow/queue.py` | Queue-and-replay on ServiceNow outage currently sits inside RagCore's process alongside the caller. It moves, and its durability story changes with it |
| Trigger envelope and kind set | `contracts/triggers.md` declares a **closed set** of five kinds and a payload of exactly `workItemId`, `correlationId`, `kind`. Tool-execution commands and results do not fit it. See **D-07**, **D-09** |
| Execution record | See **D-05** |

### 3.4 Explicitly stays in RagCore

`graph/` (all of it) · `governance/gate.py` decision routing and interrupt selection ·
`execution/claim.py` (idempotency boundary 1) · `integrations/model/*` (AI Gateway, model egress,
content safety — this is reasoning, not integration, and the requested scope does not include it) ·
`retrieval/` · `notifications/` · `application/audit.py` · `ingestion/` · all approval, consent and
resume logic.

---

## 4. Decisions derivable from existing architecture

These are answered by artefacts already in force. They are recorded, not decided.

### A-01 — Service Bus message content *(Q7)*

**Fully determined and non-negotiable.** Specification §27.2 and `contracts/triggers.md`: a message
carries an opaque work identifier and correlation identifiers, and *"explicitly forbidden in a
trigger: tenant, requester, roles, action, target, approval state, expiry, command content,
credentials, or any other authority-bearing value."*

An Integrations execution command therefore **MUST NOT** carry tenant, actor, roles, the action, the
target, parameters, treatment, approval state or a credential reference. The only open question is
whether an opaque `operationId` may be added — **D-07**.

### A-02 — Idempotency boundaries *(Q10)*

Derived from §29.4 and the existing `execution/idempotency.derive_key`:

```text
Boundary 1 — platform:  atomic claim on the work item.        Owner: RagCore (Work).   Unchanged.
Boundary 2 — external:  derived idempotency key.              Owner: Integrations.     Moves.
```

The key is derived from `(tenant, work_item_id, operation_id)` and is **never random**, so a
redelivered Service Bus command produces the same key and therefore the same external effect exactly
once. Integrations derives it *after* recovering the tenant from durable state, never from the
message. Integrations **must not claim** — the claim is the authority record's concurrency boundary
and belongs with the authority record (§32.2).

What remains open is whether the `idempotency_record` table moves — **D-05**.

### A-03 — Correlation of the execution record to the work item *(Q6)*

Derived from Principle VIII and the existing key derivation. Three joins already exist and none is
new mechanism:

1. **W3C Trace Context** propagates across the APIM hop and across Service Bus
   (`messaging/tracecontext.py` already does this), so one correlation id spans the whole journey.
2. The **opaque `workItemId`** is on the command, on the result, and on every audit record.
3. The **derived idempotency key** is a deterministic function of `(tenant, work_item_id,
   operation_id)` and is therefore a stable join key that both sides can compute independently.

No new correlation mechanism is required. A custom propagation header **MUST NOT** be introduced
(Principle VIII).

### A-04 — Tenant and authority recovery on the asynchronous path *(Q8, partially)*

Derived from §18.1, §18.5 and `contracts/triggers.md` §Consumer obligations. On receiving a command,
Integrations MUST: load the durable record by the opaque identifier; recover the customer tenant from
it and **from nothing else**; verify independently that it is authorized, active, not cancelled and
not expired; then apply its own access and policy checks; then execute. The fifteen-minute window
applies from `approved_at` regardless of trigger latency.

**The mechanism by which Integrations reads durable state is not determined — D-08.** And a concrete
gap falls out of this section: see **D-06**.

### A-05 — Retry and failure posture

Derived from §29.3 and FR-EXEC-006, unchanged by the split: read operations retry with backoff inside
the adapter; **side-effecting operations are not automatically retried**; a failed authorized action
requires fresh human authorization; dead-lettered work is not replayed and surfaces to humans;
approved-but-unexecuted work appears in `vw_approval_unexecuted_v1`. Integrations inherits all of it.
A result message reporting failure must not cause RagCore to re-dispatch.

### A-06 — OpenAPI emission rules *(Q11, partially)*

Derived from `plan.md` §OpenAPI contract emission and `contracts/README.md` rule 5: Integrations
emits its own document(s) **from the running service**, one per audience, never merged; CI publishes
them under `build/contracts/integrations/`; the five gates (generation · determinism · publishability
· compatibility · freshness) apply unchanged; documents are byte-deterministic with sorted keys;
`tenantId` remains forbidden as a parameter or request field.

The *route list* is not derivable — **D-11**.

### A-07 — Audit remains one store

Derived from §28.1 and Principle VIII: audit is distinct from telemetry, and every consequential
action produces a durable record carrying the full actor chain — *who requested it, who approved it,
which principal executed it, by what means, against which organisation, with what result*. The
executing principal is now an Integrations identity, so `execution_method` and the actor chain must
record that. **Audit does not fork into two stores**; a second audit authority would violate
Principle IV directly.

### A-08 — Health, errors, resilience, observability

Derived and inherited without change: `/health/live` process-only, `/health/ready` covering
dependencies; RFC 9457 `application/problem+json` with `correlationId`; explicit timeout on every
outbound call; transient/non-transient distinction; structured OpenTelemetry-integrated logging with
no secret, token or cross-tenant leakage; 25-second drain and explicit container resource limits;
digest-pinned runtime image.

### A-09 — Identity and trust posture

Derived from Principle I and §13.4: Integrations **MUST NOT** parse an access token. It consumes only
the closed `X-Idp-*` contract that APIM writes. It must not accept an identity header supplied by
RagCore — APIM re-establishes trusted identity on the hop, and the global inbound policy already
deletes every inbound copy of the contract. The direct-path refusal test (`FR-DEMO-004a`) must be
extended to prove a RagCore → Integrations call that bypasses APIM fails, **including one carrying a
well-formed but self-supplied header contract**.

---

## 5. Decisions requiring explicit resolution

Each of these is a genuine gap: the current architecture does not answer it, and answering it by
implementation would be exactly the silent divergence Principle X exists to catch. A recommendation
is given where one option is materially better supported; the recommendation is **not** the decision.

---

### D-01 — The APIM route for the internal Integrations API *(Q1)*

**What is already fixed.** `contracts/README.md` rule 4 states that synchronous service-to-service
interaction goes *"through the **workload audience**, app-only, and the call routes **through APIM**
like any other."* `build/infra/apim/apis.json` establishes the routing idiom: **longest matching path
wins**, proven by `/api/customer/v1/views/...` reaching the monolith while everything else under
`/api/customer/v1` reaches RagCore.

**What is not fixed.** The `workload-v1` API currently binds the whole `api/workload/v1` prefix to
the `ragcore` backend. A second backend under that audience needs a discriminating segment, and
nothing names it.

| Option | Consequence |
|---|---|
| **(a) `/api/workload/v1/integrations/...` → `integrations` backend** *(recommended)* | Reuses the proven longest-prefix idiom; one audience, one policy file, one identity derivation. Costs: the audience's OpenAPI documents are emitted by two different services, so the compatibility gate must diff per-deployable documents rather than per-audience |
| (b) A new audience `/api/integrations/v1/...` | Cleanest document story and an independent rate/quota key. Costs: a **fourth audience** — new Entra app registration, new policy file, new app role, and it contradicts rule 4's statement that the workload audience *is* the service-to-service path |
| (c) Path-based split without a new segment | Rejected — indistinguishable routes are the failure `apis.json` was written to prevent |

**Must be recorded:** the chosen prefix, the backend entry, the `credentials` block (the mutual-TLS
exemption in `apis.json` applies identically and must be restated, not assumed), and whether the
per-organisation rate limit counts Integrations traffic on the same key as RagCore's.

---

### D-02 — Audience and token for RagCore → Integrations *(Q2)*

**What is already fixed.** `build/infra/apim/workload.v1.xml` defines the workload credential
completely: app-only Entra token, `validate-azure-ad-token` against `{{operator-tenant-id}}`,
audience `{{workload-api-audience}}`, required app role `{{workload-app-role}}`, a
`client-application-ids` allow-list, and an **explicit 403 when `scp` is present** so a delegated
human token can never reach the surface. The derived contract is
`X-Idp-Credential-Class: app`, `X-Idp-Roles: none`, and the token's `tid` is the *Operator* tenant —
never the customer tenant.

**What is not fixed:** whether RagCore calling Integrations reuses that exact identity or gets a
distinct one.

| Option | Consequence |
|---|---|
| **(a) Same audience, distinct app role** *(recommended)* | Least privilege is preserved — Integrations can require an `Integrations.Invoke` role that the generic workload role does not grant, so a compromised component with the workload role cannot drive connectors. One policy file, one derivation |
| (b) Same audience, same app role | Simplest; but every workload-audience caller becomes able to invoke connectors. Hard to reconcile with Principle II's set-intersection least-privilege posture |
| (c) Distinct audience and app registration | Strongest isolation; highest operational cost; couples to D-01(b) |

---

### D-03 — **The synchronous tool-catalogue call has no lawful tenant source** *(Q2, Q3, Q8 — sharpest open conflict)*

This is the most consequential unresolved item in the change, and it is a genuine conflict between
rules that are each individually non-negotiable.

The tool catalogue is **per tenant** — §21.2 (*"There is no global toolset. Tools resolve per tenant,
least-privilege"*) and FR-EXT-015. So a catalogue read must be tenant-scoped. But:

- If RagCore calls with the **workload app-only credential** (rule 4's synchronous form), the derived
  `X-Idp-Tenant-Id` is the *Operator* tenant, not the customer's — `workload.v1.xml` says so
  explicitly. Integrations would then have to take the customer tenant from a **parameter**, which
  `contracts/README.md` rule 1 and constitution Principle I both forbid outright.
- If RagCore **forwards the user's token** — which §13.4 explicitly contemplates: *"When Service A
  needs Service B to act under the same human principal, it forwards the same user token through this
  path"* — then APIM derives the customer tenant correctly, but the call is on the **customer or
  staff audience**, not the workload one, which contradicts rule 4's characterisation of the
  synchronous service-to-service path.
- If RagCore passes an **opaque session or work-item identifier** and Integrations resolves the
  tenant from durable state (the pattern A-04 uses for the async path), it works — but catalogue
  retrieval happens during *reasoning*, potentially **before any work item exists**, and it makes
  every catalogue read a database round trip plus a cross-schema read.

| Option | Assessment |
|---|---|
| **(a) Forward the user token; catalogue reads sit on the customer/staff audience** | Spec-conformant under §13.4; tenant derived at APIM exactly as Principle I requires. Requires amending rule 4's wording, which currently implies workload-only |
| (b) Workload credential + opaque identifier, tenant from durable state | Consistent with the async path and with A-04; needs a durable record to exist at catalogue time, and D-08's read mechanism |
| (c) Workload credential + tenant parameter | **Rejected.** Directly violates Principle I and README rule 1. Named here only so it is refused on the record rather than reached for under time pressure |

**This decision must be made before any route is defined**, because it determines the audience, the
policy file, the OpenAPI document and the shape of the catalogue API at once.

---

### D-04 — Durable-record ownership: catalogue, binding, entitlement, credential reference *(Q4, Q5)*

**The requested target conflicts with specification §33.** §33 assigns:

| Entity | §33 owner | Requested target owner |
|---|---|---|
| Operation catalogue entry | Governance | Integrations ("tool catalogue") |
| Action-to-tool binding | Governance | Integrations ("connector registry") |
| Tool entitlement | Tenant & Configuration | Integrations ("tenant tool configuration") |
| Credential reference | Tenant & Configuration | Integrations ("credential lookup") |

This cannot be resolved by implementation. Principle IV forbids a second durable authority where the
specification names one; §14.2 requires exactly one owning context per capability. Compounding it:
`governance_record` is already published to the monolith as `vw_governance_catalogue_v1`, and
`tenant_entitlement.credential_reference` is read today by `integrations/credentials.py`.

A further constraint bites here: **treatment must not move.** `governance_record.default_treatment`
and `accepted_roles` drive the `AUTO`/`END_USER_APPROVAL`/`STAFF_APPROVAL`/`NOT_ALLOWED` decision,
which Principle III reserves for deterministic governance on the proposing side. A catalogue row is
therefore two things at once — a *governance* contract and a *connector* contract — and the split
runs through the middle of one table.

| Option | Assessment |
|---|---|
| **(a) Split the row by concern** *(recommended)*: Governance keeps `default_treatment`, `accepted_roles`, `risk_tier`, `requires_elevation`, `is_reference_fixture`, `commands`, `content_hash`, `verification_tool`. Integrations owns a new `connector_registry` + `connector_binding` (endpoint, kind, signing profile, idempotency policy) and takes ownership of `tenant_entitlement` | Honours §33's intent, keeps treatment with governance, gives Integrations a real registry. Cost: a §33 amendment and a defined read relationship in one direction |
| (b) Move the whole catalogue to Integrations; Governance reads it | Matches the requested wording most literally. **Puts treatment behind a service boundary from the authority that must own it** — hard to reconcile with Principle III |
| (c) Leave §33 as written; Integrations owns only the execution record and reads everything else | Smallest delta, no §33 amendment. But then Integrations does not own "tool catalogue, connector registry, tenant tool configuration" as the change requires |

**Whichever is chosen, the write side must be single.** Two writers to one logical catalogue is the
defect Principle IV names.

---

### D-05 — The execution record: one entity or two *(Q4, Q5)*

`data-model.md` gives `operation` fields that are written *at execution*: `idempotency_key`,
`status` (`executed`/`failed`), `verification`, `executed_at`. §33 assigns the `operation` entity to
**Governance**, and `vw_*` views publish it. §32.7 separately gives Tool Execution its own
**tool invocation record**.

So there are already two entities in the specification, and the split forces the question of whether
they become two *tables in two schemas*.

| Option | Assessment |
|---|---|
| **(a) Two records** *(recommended)*: `operation` stays RagCore-owned and authoritative for *what the platform concluded*; Integrations owns `integration_execution` — attempt, connector, endpoint, derived key, external reference, normalized result, outcome classification — authoritative for *what was attempted externally*. RagCore updates `operation` from the result message | Matches §32.7's existing "tool invocation record"; keeps one platform authority; the derived key joins them (A-03) |
| (b) One record, owned by Integrations, RagCore reads it | Violates Principle IV — `operation.status` is platform state and PostgreSQL-authoritative under §33.1 |
| (c) One record, owned by RagCore, Integrations writes it | Two writers to one table across a deployment boundary. Rejected for the same reason as (b) inverted |

**Also required:** whether `idempotency_record` moves to Integrations (it protects the external
system, so it should follow boundary 2), and whether RagCore retains any row for it.

---

### D-06 — **Integrations cannot currently learn what to execute** *(Q7 consequence — a concrete gap)*

This falls directly out of A-01 and A-04 together, and it has no answer in the current artefacts.

- `contracts/triggers.md` forbids a message carrying the **action, target, or command content**.
- `vw_work_item_v1` publishes `work_item_id`, `tenant_id`, `session_id`, `requested_by_oid`,
  `case_reference`, `governed_action`, `state`, `approval_state`, `expires_at`, `claimed_at`,
  `claimed_by` — and **deliberately omits `target`**, documented in `persistence/views.py` as *"the
  smallest published surface is the one hardest to widen by accident."*
- `operation.parameters` — the actual arguments — is in no published view at all.

So Integrations can recover *tenant* and *authority*, and cannot recover *what to do*. Today this is
invisible because `ExecutionLeg.run` receives `identity` and `parameters` as in-process arguments.

| Option | Assessment |
|---|---|
| **(a) A new published view** — `vw_operation_execution_v1` exposing `operation_id`, `work_item_id`, `tenant_id`, `catalogue_id`, `catalogue_version`, `parameters`, `status` — read by Integrations under the ADR-0001 view-contract discipline *(recommended)* | Reuses the existing versioned-view mechanism; no authority travels in a message; `parameters` are **data** and the destination still comes from the connector binding, never from them (FR-EXT-018) |
| (b) A synchronous callback: Integrations calls RagCore's workload API to fetch the operation | Creates a RagCore ↔ Integrations **cycle**, which the target dependency graph (§7) is specifically drawn to avoid |
| (c) Put parameters in the message | **Rejected.** `contracts/triggers.md` forbids command content, and a message-borne target is the exact shape FR-EXT-018 exists to prevent |

Note the ADR-0001 view contract assumes the reader is the *.NET monolith*. Extending it to a third
reader is a real change to that contract's scope, not a free reuse.

---

### D-07 — Extending the trigger envelope and the closed kind set *(Q7, Q9)*

`contracts/triggers.md` states the payload is `workItemId` · `correlationId` · `kind` and *"that is
the entire payload"*, over a **closed set** of five kinds, and that *"adding a kind is a contract
change."*

An execution command needs to identify **which operation** within a work item (a work item may carry
more than one), and a result needs to report an outcome. Neither fits.

**To decide:**

1. Whether `operationId` may join the envelope. It is an opaque platform identifier, scoped under a
   work item, carrying no tenant, actor, action or authority — so it is arguably in the same class as
   `workItemId`. **Recommendation: permit it, and state in `triggers.md` why it is not
   authority-bearing**, so the rule is reasoned rather than eroded.
2. The new kinds. Suggested: `integration.execute` (RagCore → Integrations) and
   `integration.completed` / `integration.failed` (Integrations → RagCore).
3. What a **result** message may carry. The outcome classification (`server_confirmed` /
   `client_attested` / `contradicted`) is a *fact about an observation*, not an authority — but a
   result message that carried a normalized payload would be carrying tool output across a trust
   boundary, and FR-EXT-017 makes tool output data that *"MUST NOT be treated as instruction."*
   **Recommendation: the result message carries identifiers and an outcome enum only; the normalized
   payload is durable in Integrations and read by RagCore through a view** — same reasoning as D-06,
   inverted.
4. Whether the fifteen-minute TTL and dead-letter rules apply unchanged. **They should** — but
   note the window now spans *two* hops rather than one, which tightens the real budget.

---

### D-08 — How Integrations reads durable state *(Q8)*

A-04 fixes *what* Integrations must recover. Nothing fixes *how*.

| Option | Assessment |
|---|---|
| **(a) Published versioned views, same discipline as ADR-0001** *(recommended)* | Proven mechanism; `0019_database_principals` already establishes per-principal database grants, so an Integrations principal that can read `vw_*` and no base table is a direct extension. Requires D-06's new view and an ADR-0003 amendment for who owns those migrations |
| (b) Integrations calls RagCore's workload API | Creates a dependency cycle. Rejected in the dependency graph |
| (c) Integrations owns its own database | Cleanest isolation; but then the work item's authority state must cross a boundary, and §18.1's *"resolved **only** from the durable work item"* becomes a remote read with a staleness window. Hard to reconcile with the expiry rule |

**Also to decide:** the database principal, its grants, whether Integrations may hold *any* write
grant on the platform schema (it should not), and which Alembic head owns its tables — see D-10.

---

### D-09 — Service Bus queues and topics *(Q9)*

Today: one queue, `synthia-triggers` (`config/settings.py`), one publisher, one consumer, managed
identity only, at-least-once, no ordering assumed, dead-lettering per the trigger contract.

**To decide:**

| Question | Recommendation |
|---|---|
| Command transport | A dedicated queue, e.g. `synthia-integration-commands`. One consumer, so a topic buys nothing and doubles the dead-letter surface |
| Result transport | A dedicated queue, e.g. `synthia-integration-results`. Separate from commands so a stuck result cannot block a command |
| Reuse `synthia-triggers`? | **No.** It is the resume path's queue with its own kinds and TTL semantics; mixing two lifecycles in one queue makes dead-letter triage ambiguous |
| Sessions / ordering | Not assumed anywhere (§27.3). Do not introduce sessions |
| Outbox | Integrations needs **its own transactional outbox** for result publication — the constitution's outbox rule is platform-wide, not RagCore-specific |
| Dead-letter posture | A dead-lettered `integration.execute` for approved work is a **governance failure**, not merely operational: it must surface in the approved-but-not-executed list, exactly as `triggers.md` already requires |
| Namespace | One namespace or two, and the role assignments per identity (RagCore: send on commands, listen on results; Integrations: listen on commands, send on results — **and nothing more**) |

---

### D-10 — Migration and schema ownership *(Q5)*

Constitution Principle V: *"RagCore owns every migration."* ADR-0003: *"Alembic owns every
migration; migrations run as a gated job, never at startup."* A second deployable owning tables
contradicts the first sentence directly.

| Option | Assessment |
|---|---|
| **(a) One Alembic project, two logical schemas** (`platform`, `integration`), RagCore's migration job applies both *(recommended for the scaffold)* | Keeps one gated migration job and one ordering; Principle V's sentence is scoped rather than broken. Cost: a deploy-time coupling between the two deployables' schemas |
| (b) Two Alembic projects, two heads, two gated jobs | True independence; requires an ordering discipline between them and a second `migrate.job.yaml` |
| (c) Separate database | Strongest isolation; forces D-08(c) and its staleness problem |

The decision must also state whether `platform` and `integration` share a PostgreSQL instance,
what grants the Integrations principal holds (**no write on `platform`**), and how the existing
"no base table read" test for the monolith extends to a third principal.

---

### D-11 — The exact OpenAPI surface *(Q11)*

A-06 fixes the *rules*. The *routes* are not derivable. Minimally required, stated as intent rather
than as a specification:

- **Tool catalogue** — read the tenant-resolved capability set. Audience and tenant source depend
  entirely on **D-03**.
- **Synchronous ServiceNow operations** — the specific operations are not enumerable from current
  material. §22.3 lists what the platform writes (case create, work notes, approval mirror, outcome,
  state transition, escalation) and classifies **all of them `AUTO`**; whether all of those are
  synchronous, or only case creation is (because §22.5 says a session that cannot commit a case
  cannot enter Resolution Mode), **is undecided**.
- **Health** — `/health/live`, `/health/ready`.
- **No execution endpoint.** Normal tool execution is a Service Bus command by requirement 3, and a
  synchronous execution route would be a second, ungoverned path to the same effect.

**Also to decide:** the deployable's stack. Nothing in the current material chooses one, and the
constitution has a full baseline for **both** .NET 10 and Python 3.12. The moving code is Python;
choosing .NET means a rewrite of every adapter rather than a move, which would turn §3.1's "moves
unchanged" list into §3.3. *Recommendation: Python, on the existing baseline.*

---

### D-12 — Repeating access and policy checks at execution time *(Q3, Q4)*

The requirement that *"Integrations must repeat access/policy checks at execution time even when
RagCore previously retrieved the catalogue"* is correct and consistent with Principle I
(*"authentication is not authorization: every consequential operation is authorized on its own
merits, every time"*). What is undecided is **what exactly Integrations re-checks**, and the answer
determines whether the platform ends up with one policy authority or two.

**To decide, precisely:**

| Check | Who | Note |
|---|---|---|
| Tenant is active | Integrations | §29.5, FR-EXEC-003 — must be re-read, not inherited |
| Work item authorized, unexpired, not cancelled | Integrations | §18.1 |
| Tenant is entitled to this capability | Integrations | FR-EXT-015 — this is the access check |
| Capability is registered and the version matches what was approved | Integrations | FR-EXT-014, `content_hash` binding |
| Capability kind is `action` and reached past a gate | Integrations | FR-EXT-013 |
| **Treatment assignment** (`AUTO`/`STAFF_APPROVAL`/…) | **RagCore only** — *recommended* | Principle III. If Integrations re-derives treatment, there are two deterministic policy authorities and they can disagree |
| **Role set intersection against the approver** | **RagCore only** — *recommended* | Roles are a gateway-derived, request-time concept; the approval record already binds the roles held at decision time |

The recommended line is: **Integrations re-verifies every *fact* (tenant, entitlement, registration,
version, window, state); RagCore remains the sole authority for every *decision* (treatment, role
intersection, approval sufficiency).** That satisfies "repeat the checks" without creating the second
policy authority Principle IV forbids — but it is a decision, and it must be recorded as one.

---

## 6. Obsolete architecture statements

Statements in force today that the target change makes false. Each must be amended in place — **not
left to be contradicted by code**, which is the failure mode Principle X names.

| # | Statement | Where | Why obsolete |
|---|---|---|---|
| O-01 | "RagCore owns orchestration, execution and all state-changing operations; the .NET modular monolith is read-only" | Constitution Principle V | Execution splits |
| O-02 | "RagCore calls MCP servers, the system of record, Graph and the realtime service inside a fifteen-minute window" | Constitution §Resilience | RagCore calls none of the first three |
| O-03 | "RagCore owns every migration" | Constitution Principle V; ADR-0003 | Second schema owner — D-10 |
| O-04 | "Ownership is split across exactly **two** application deployables" | ADR-0001 §Decision Outcome | Three |
| O-05 | "There is no application-level dependency between them in either direction" | ADR-0001 | Still true of RagCore ↔ monolith; false of the system. Must be **scoped**, not deleted |
| O-06 | Divergence #1: eleven contexts → two deployables | ADR-0001 | Partially withdrawn |
| O-07 | "RagCore owns that whole chain internally; no gateway hops between its stages" (Divergence #2, §31.4) | ADR-0001 | Gateway hops return to the tool-execution leg; the §34.2 hop-count baseline changes again |
| O-08 | "A client legitimately calls both deployables. They are two backends behind one trust boundary." | `contracts/README.md` | Three backends. Integrations is not client-facing, which is itself worth stating |
| O-09 | Rule 4's synchronous form — service-to-service *is* the workload audience | `contracts/README.md` | Survives or not depending on **D-03** |
| O-10 | "Both the publisher and the consumer currently live in the RagCore deployable, so a direct function call would be simpler today" | `contracts/triggers.md` §Why the queue exists | No longer true — and the section's third reason ("so a further decomposition of RagCore can become its own deployable later as a deployment change") is now being *exercised*. Rewrite as vindication, not as hypothesis |
| O-11 | "That is the entire payload… it carries nothing else" over a closed five-kind set | `contracts/triggers.md` | D-07 |
| O-12 | "for Alpha, the RagCore runtime holds the Workload managed identity and performs the execution leg as the Workload" | Spec §18.2 | The external-effect leg moves |
| O-13 | "One runtime holds two credential classes… the control that is *not* present is runtime separation of credential classes" | Spec §18.2, §35.2 | **Materially improved.** Update the risk rather than deleting it — connector credentials leave the RagCore runtime |
| O-14 | Ownership rows: operation catalogue entry, action-to-tool binding, tool entitlement, credential reference | Spec §33 | D-04 |
| O-15 | Adapter tables and credential-resolution flow implying one runtime | Spec §21.3, §21.4, §18.4 | The flow is unchanged; the runtime is not |
| O-16 | "Five documents, versioned by the API version in the path" | `plan.md` §OpenAPI contract emission | Six or seven |
| O-17 | `ragcore/src/ragcore/integrations/` in the source tree and `RAGCORE integrations → implement ports declared in application` in the dependency graph | `plan.md` §Project Structure, §Dependency direction | The package moves |
| O-18 | "Tool Execution — write side: `execution/`, `integrations/mcp/`" | `plan.md` §Where each bounded context lives | Now a third column |
| O-19 | Phase 9 task descriptions placing every adapter under `ragcore/src/ragcore/integrations/` | `tasks.md` T128–T138 | Marked `[X]`; needs an explicit disposition rather than silent relocation |
| O-20 | "NO VIEWS COUNTERPART… the workload audience is the execution leg" | `build/infra/apim/apis.json` | The workload audience gains a second backend under **D-01(a)** |

---

## 7. Proposed target dependency graph

```text
                         Entra ID (identity provider)
                                   │
   Desktop app ─┐                  │ authenticate
   Staff portal ─┼──> Front Door + WAF ──> APIM  ◄── the only trust boundary
   Customer portal ┘                        │
                                            │  identity derived exactly once
             ┌──────────────────────────────┼──────────────────────────────┐
             │                              │                              │
             ▼                              ▼                              ▼
    ┌─────────────────┐          ┌──────────────────────┐        ┌──────────────────┐
    │  RagCore        │          │ Integrations Service │        │ .NET monolith    │
    │  (Python)       │          │ (stack — D-11)       │        │ READ ONLY        │
    │                 │          │                      │        │                  │
    │ Session · Work  │          │ Tool catalogue       │        │ Read models over │
    │ Governance      │          │ Connector registry   │        │ vw_*_v1 views    │
    │ Approval        │          │ Tenant tool config   │        │                  │
    │ Agent/LangGraph │          │ Access + policy      │        └────────┬─────────┘
    │ Retrieval       │          │   re-check           │                 │ read
    │ Audit·Ingestion │          │ Operation execution  │                 │
    │ Claim (bnd 1)   │          │ MCP client           │                 │
    │ Verification    │          │ External API calls   │                 │
    │   *conclusion*  │          │ Credential lookup    │                 │
    │                 │          │ Normalization        │                 │
    │                 │          │ Idempotency (bnd 2)  │                 │
    │                 │          │ Execution records    │                 │
    └───┬────┬────┬───┘          └───┬─────┬────────┬───┘                 │
        │    │    │                  │     │        │                     │
        │    │    │ (1) catalogue ───────► │        │                     │
        │    │    │     via APIM  ◄────────┘        │                     │
        │    │    │ (2) sync ServiceNow ops ──────► │                     │
        │    │    │     via APIM                    │                     │
        │    │    │                                 │                     │
        │    │    └─(3a) Service Bus ──────────────►│                     │
        │    │        synthia-integration-commands  │                     │
        │    │◄──(3b) Service Bus ──────────────────┘                     │
        │    │        synthia-integration-results                         │
        │    │                                                            │
        │    │ AI Gateway ──► model providers    (RagCore only)           │
        │    │ Azure AI Search · Redis · SignalR                          │
        │    ▼                                                            ▼
        │   PostgreSQL ── platform schema (RagCore owns, writes) ─────────┘
        │        ▲                 │
        │        │                 └── vw_*_v1 published views
        │        │                        ▲                    ▲
        │        │                        │ read-only          │ read-only
        │        │                  Integrations          .NET monolith
        │        │                  (D-06, D-08)
        │        │
        │   integration schema (Integrations owns, writes — D-10)
        │
        └──► Key Vault: platform + model secrets only
                                 ▲
     Integrations ───────────────┘  connector secrets ONLY, per tenant per system
                  │
                  └──► ServiceNow · Microsoft Graph · MCP servers · OneLogin · Duo
                                   (no other component reaches these)
```

**Edges that must not exist, and must be proved not to exist:**

```text
RagCore        ↛ ServiceNow · Microsoft Graph · OneLogin · Duo · any MCP server
RagCore        ↛ connector secrets in Key Vault           (role assignment, not code)
RagCore        ↛ Integrations by any direct network path  (must traverse APIM)
Integrations   ↛ RagCore                                   (no reverse call — avoids the cycle)
Integrations   ↛ any write on the platform schema
Integrations   ↛ AI Gateway · model providers              (it does no reasoning)
Integrations   ↛ SignalR                                   (notification is RagCore's leaf)
.NET monolith  ↛ everything except vw_*_v1                 (unchanged, ADR-0001)
any deployable ↛ any other by internal address             (unchanged, §13.4)
```

**Directed dependency, stated plainly:** `RagCore → Integrations`, and nothing in the reverse
direction. Results return over Service Bus rather than as a call, which is what keeps the graph
acyclic. This is the single property most worth protecting in review, because the cheapest fix to
almost every problem in §5 is a callback from Integrations to RagCore — and that callback is what
turns two services into a distributed monolith.

---

## 8. What must happen before implementation

In order. None of these is a code change.

1. **Resolve D-03.** It determines the audience, the route, the policy file and the catalogue API
   shape. Nothing downstream can be specified until it is answered.
2. **Resolve D-04 and D-05.** Ownership decides the schema, which decides the migrations, which
   decides the deployment sequencing.
3. **Write ADR-0007.** Constitution Principle V makes it a precondition, not a deliverable. It must
   name the conflict with ADR-0001, carry the justification against "premature distributed
   decomposition is a defect", restate the §34.2 hop-count cost, and claim the OQ-02 credit.
4. **Amend ADR-0001, ADR-0003, ADR-0005 and the ADR index** in the same change — a divergence
   withdrawn in one record and left standing in another is worse than either.
5. **Amend the specification** — §9, §13.4's example, §14.1, §18.2, §21, §27, §31, §32.7–§32.9,
   §33, §35.2, §40 — with §33 as the load-bearing one.
6. **Amend the constitution** for O-01, O-02, O-03, with a Sync Impact Report and a version bump.
7. **Resolve D-01, D-02, D-06 through D-12** and record each in ADR-0007 or its own record.
8. **Update the feature artefacts** — `plan.md`, `contracts/*`, `data-model.md`, `tasks.md` — and
   only then generate tasks.

**The test obligations this change owes** are mechanical under the constitution's "which change
requires which category" table, and they are large: contract and authorization (new API and message
shapes); architecture dependency (a new deployable boundary and a new banned-edge set);
tenant isolation (a third database principal); idempotency and concurrency (a new at-least-once hop);
governance (a second evaluation point); adapter (every relocated adapter); configuration validation
(a new options surface); integration (new migrations and a new published view); security (every
prohibition in §7 must be shown unreachable); and the end-to-end golden path, which now crosses three
deployables.

**The direct-path refusal proof (`FR-DEMO-004a`, `SC-DEMO-003a`, `SC-DEMO-003b`) is the single most
important one to extend**, because it is the test that currently proves APIM is the trust boundary —
and the new RagCore → Integrations edge is exactly the shape a bypass would take.
