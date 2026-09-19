# Implementation Plan: Synthia Platform Engineering Scaffold

**Branch**: `001-platform-scaffold` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-platform-scaffold/spec.md`

**Constitution**: v3.1.0 | **Architecture source of truth**: `Synthia-Platform-Specification.md`

## Summary

Build a monorepo containing six applications across **three** deployables, proving the load-bearing
**platform infrastructure** end to end while containing no product use cases.

**Revised 2026-09-18 — the Integrations Service boundary.** `Synthia-Platform-Specification.md` §21.6
and [ADR-0007](../../docs/adr/0007-integration-service-boundary.md) make **Integrations a separately
deployed Python service parallel to RagCore**. This plan no longer treats integrations as a RagCore
package. The contexts and their responsibilities are unchanged; their runtime placement is not.
Stages 1–13 remain valid as built except where §Stage 16 names the migration out of RagCore.

**Revised 2026-09-16 — scaffold scope correction.** The architecture below is unchanged. What changed
is what the scaffold must *demonstrate*: platform integration through inert sample flows
(spec `FR-DEMO-001`–`FR-DEMO-019`), not business approval semantics. Golden path B is now
**asynchronous platform integration** rather than a governed human decision; the approval and consent
workflows remain fully specified and move past the scaffold. Nothing was removed from the design, and
no infrastructure was added.

This revision **reconciles the plan with constitution v3.1.0**. The architecture is unchanged — it
remains the one fixed by `Synthia-Platform-Specification.md` and
[ADR-0001](../../docs/adr/0001-ragcore-owns-orchestration-dotnet-owns-read.md). What changed is the
engineering contract the build must satisfy: transactional outbox, optimistic concurrency, resilience
policy, startup configuration validation, container hardening, the twelfth bounded context
(`Ingestion`), and fifteen required test categories.

**RagCore** (Python 3.12, LangGraph) owns orchestration, reasoning, governance, approval, the authority
record and the atomic claim — **and reaches no external system**. The **Integrations Service**
(Python 3.12, FastAPI) owns the tool catalogue, the connector registry and all traffic to external
systems. The **.NET 10 modular monolith** is read-only. Three client surfaces come from one Angular
workspace, with Electron as a thin host that decides nothing.

**The dependency graph is directed and acyclic**: `RagCore → Integrations`, and nothing in reverse.
RagCore and the monolith still have no application-level dependency in either direction. Results
return over Service Bus rather than as a call, which is what keeps the graph acyclic — a callback from
Integrations to RagCore would turn two services into a distributed monolith and is the single edge
most worth refusing in review.

Work is organised into **seventeen ordered stages**: eleven scaffold stages containing no product
behaviour, two architectural golden paths — A proves the synchronous governed machine, B proves the
asynchronous platform integration — **three Integrations Service stages (15–17) that must complete
before Stage 14** — and only then the twelve use cases. Stage numbers are **append-only and never
reused**, following the same permanence rule the spec applies to requirement identifiers, so 15–17
carry numbers higher than the stage they precede. The four execution treatments remain catalogue data
throughout and are classified deterministically; the two human-decided ones are not *exercised* by the
scaffold (spec `FR-DEMO-016`, `FR-DEMO-017`).

## Technical Context

**Language/Version**: C# on .NET 10 (`net10.0`); Python 3.12 (`py312`); TypeScript 5.x strict on
Angular; Electron for the desktop host.

**Primary Dependencies**: .NET — ASP.NET Core Minimal APIs, built-in OpenAPI, EF Core 10 + Npgsql,
`Microsoft.Extensions.*`, `IHttpClientFactory` with `Http.Resilience`/Polly v8, OpenTelemetry.
Python — `uv`, FastAPI, Pydantic, Pydantic Settings, LangGraph, `langgraph-checkpoint-postgres`,
SQLAlchemy + asyncpg, Alembic + `alembic_utils`, `azure-servicebus`, `azure-identity`, MCP client.
Web — Angular standalone components, Angular CDK.

**Storage**: PostgreSQL Flexible Server — the single authoritative durable store, holding platform
state, LangGraph checkpoints in their own schema, the transactional outbox, idempotency records and
audit. **One database, two schemas**: `platform`, owned and written by RagCore, and `integration`,
owned and written by the Integrations Service. **One Alembic project** applies both, as one gated job.
Integrations reads platform state through published views only and may write **only** the result
fields of an integration job row. Azure AI Search is a **derived** retrieval index. Redis is
**transient only**. Key Vault is the sole source of secret material.

**Model layer**: Azure OpenAI and Foundry for reasoning and embeddings, on private endpoints, reached
**only** through the **AI Gateway** — provider routing, provider-normalised token metering,
per-organisation budgets and throttles, semantic cache, bidirectional content safety. A policy
function, **not an identity boundary**.

**Testing**: .NET — xUnit, NetArchTest, Testcontainers, `WebApplicationFactory`. Python — pytest,
pytest-asyncio, pytest-alembic, Testcontainers. Web — the project-supported Angular runner plus
Playwright and axe-core.

**Target Platform**: Azure Container Apps (internal environment) behind Front Door + WAF and APIM;
Electron desktop on customer-managed Windows endpoints.

**Project Type**: Multi-application monorepo — **three** backend deployables, three client surfaces.

**Performance Goals**: **None committed.** Constitution Section 2 and spec `PT-001`–`PT-003` make every
performance figure good-to-have; no release is gated on one.

**Constraints**: Per-organisation budgets and rate limits are enforced **at the AI Gateway and APIM**,
not in application code. English only, no localization infrastructure (`FR-SURF-014`). Single region,
no residency support (`FR-SURF-015`). WCAG 2.2 AA on all three surfaces. Invariant globalization in
.NET containers — see [research.md](./research.md) R-011.

**Scale/Scope**: No scale envelope defined — recorded as Outstanding. Design for linear horizontal
scale on stateless compute; revisit when use cases arrive.

## Platform Environment and Access

*Added 2026-09-16.* Consolidated here because spec `FR-DEMO-019` makes a deployed environment part of
scaffold **acceptance** rather than a later deployment concern: a sample flow that has not crossed the
edge has not been demonstrated. Every resource below already appears in this plan and in §9.3 of the
platform specification. **Nothing here is new infrastructure**; this section names what must exist and
how it is reached.

### Azure resources required by the scaffold

| Resource | Role | Scaffold acceptance depends on it |
|---|---|---|
| Front Door + WAF | The public edge. Every flow enters here | Yes — `FR-DEMO-019` |
| API Management (APIM) | The trust boundary. **Identity is derived once, here**; neither deployable parses a token | Yes — `FR-DEMO-004a`, `FR-DEMO-019` |
| Azure Container Apps | Internal environment hosting **all three deployables** and the workers | Yes |
| PostgreSQL Flexible Server | The single authoritative durable store, two schemas | Yes — `FR-DEMO-005`, `FR-DEMO-006` |
| Azure Service Bus | The asynchronous seam between deployables. **Three queues**: the resume trigger, the integration command, the integration result | Yes — `FR-DEMO-007`, `FR-DEMO-023` |
| **Inert reference connector** | A stub external endpoint reachable **only** from the Integrations Service. A scaffold fixture producing no real effect | Yes — `FR-DEMO-020`–`FR-DEMO-022` |
| Azure SignalR | Server-to-client realtime delivery. A leaf, never a link | Yes — `FR-DEMO-008` |
| Azure Key Vault | The sole source of secret material | Yes — `FR-DEMO-012` |
| Application Insights / Azure Monitor | Telemetry sink for traces, metrics and structured logs | Yes — `FR-DEMO-009` |
| Azure AI Search | The **derived** retrieval index. Rebuilt by re-running ingestion, never restored | No — reachable and configured, not exercised by a sample flow |
| Azure AI Foundry | Reasoning and embedding models, on private endpoints | No — reachable through the gateway, not exercised by a sample flow |
| AI Gateway | The sole model egress. A policy function, **not an identity boundary** | No — same |
| Redis | **Transient only.** Never an authority, never a durable record | No — present, and deliberately absent from every sample flow |

The last four are required to exist and be reachable so the scaffold is deployable as designed, and are
deliberately **not** on the acceptance path: no sample flow calls a model, queries the index, or reads
a cache. A flow that did would be proving product behaviour, which is what this correction removed.

### Authentication and secret handling

These are build-gating rules, not guidance. `SC-DEMO-003` and `SC-DEMO-004` measure them.

1. **Managed identity wherever the resource supports it.** Service Bus, SignalR, PostgreSQL, Key
   Vault, Application Insights, AI Search and Foundry are all reached as a managed identity.
2. **Azure RBAC and data-plane authorization rather than application secrets.** Access is granted by
   role assignment on the resource, not by a credential the application holds. A component's rights
   are then revocable centrally and visible without reading application configuration.
3. **Key Vault is the sole source of secret material.** Any credential that genuinely cannot be
   replaced by managed identity — a third-party system's API key, for instance — lives there and is
   resolved by reference at the point of use.
3a. **Connector credentials are held by the Integrations Service alone.** Its managed identity carries
   the Key Vault role for per-organisation connector secrets; **RagCore's identity does not, and the
   role is removed rather than duplicated**. This is a role assignment, not a code convention, and
   `SC-DEMO-020` measures it by attempting the resolution from RagCore and observing Key Vault refuse.
4. **No secret is ever committed.** Not in source, not in tests, not in committed configuration. CI
   secret scanning enforces this and a finding fails the build.
5. **No Azure client secret in application configuration.** A configuration key that could hold one is
   itself the defect; the settings types expose `*_secret_name` fields holding a *name*, never a value.
6. **No connection string carrying embedded credentials** where managed identity is supported. A DSN
   with a password in it defeats every rule above at once, and is the form the violation usually takes.

### OpenAPI contract emission

`FR-DEMO-013` and `SC-DEMO-011` make the contract an artifact rather than a document.

- **.NET** emits OpenAPI from the running Minimal APIs through the built-in document generator.
- **RagCore** emits OpenAPI from FastAPI, generated from the Pydantic request and response models on
  each route — so the document cannot drift from what the service accepts.
- **Each audience has its own explicit contract**: `customer/*`, `staff/*` and `workload/*` are
  separate documents, because one merged document would let a customer-facing client discover the
  staff and workload surfaces.
- **CI emits versioned artifacts** on every build and publishes them. The contract-artifact location
  is `build/contracts/{dotnet,ragcore,integrations}/{audience}.v1.openapi.json` — **six documents**
  as of 2026-09-18, versioned by the API version in the path and, as a build artifact, by the commit
  that produced them.
- **The Integrations Service emits `integrations/workload.v1.openapi.json`.** It serves the workload
  audience only — it is not client-facing — and its document is separate from RagCore's workload
  document even though both sit under the same audience. **One document per audience per deployable**
  is the rule, and the compatibility gate therefore diffs per deployable rather than per audience.
- **Contract tests validate the emitted documents**, not hand-written copies. A route whose emitted
  shape stops matching its declared contract fails the build rather than surfacing at a client.

*Extended 2026-09-17.* Emission is a gated pipeline rather than a step that produces files. Five
gates run in order in `.github/workflows/contracts.yml`: the documents **generate** from running
services; two emissions are **byte-identical**; each document is **publishable** — no secret or
configuration material, no client-suppliable tenant, role or audience, RFC 9457 error contracts
throughout (`build/scripts/openapi_validate.py`); no **breaking** difference against the committed
contract unless recorded in `build/contracts/approved-breaking-changes.json` verbatim, with a reason
and an expiry (`build/scripts/openapi_diff.py`); and the committed contracts are not **stale**.
`build/scripts/verify-contract-guards.sh` plants each violation class and asserts every gate rejects
it — and that the one permitted exception, `tenantId` as a staff query narrowing, is accepted.

**No schema is written twice to produce OpenAPI.** Where the .NET generator could not see the paging
and filtering parameters a handler reads from the query string itself, the endpoint's own
`QueryWhitelist` was moved onto the route as metadata and is read by both the binder and the document
transformer. Declaring the fields a second time inside a transformer would have produced a correct
document and reintroduced exactly the drift this section exists to prevent.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design. Constitution v3.1.0.*

| # | Principle | How the design satisfies it | Status |
|---|---|---|---|
| I | Identity derived once; authority never asserted | Identity derived at APIM only; **all three deployables** consume the closed header contract and none parses a token. No endpoint accepts tenant, role or audience. Tenant admission is trusted identity plus registry state. | **PASS** |
| II | Authorization separate and non-hierarchical | Set-intersection helper in both stacks, with no ordering or comparison operator defined on roles. `Synthia_Agents → technician`, `Synthia_Admins → administrator`. **`senior_technician` is implemented as a defined role that no operation accepts** — see below. Customer surfaces apply no role check; the staff portal has no session-origination route. | **PASS** |
| III | Deterministic governance decides; model proposes | Governance is a distinct RagCore package. The agent loop reaches `read` tools only; every `action` passes the gate. Discovery never grants entitlement. Approval binds approver, tenant, work item, operation, target, version, expiry and audit. | **PASS** |
| IV | Isolation absolute; one authority per concern | Tenant filter in repository and retrieval layers with no unfiltered path. PostgreSQL authoritative; ServiceNow the case system of record; AI Search derived; Redis transient; exactly one checkpoint store. | **PASS** |
| V | Modular boundaries mandatory | Twelve logical contexts preserved as modules and packages — none collapsed, none promoted to a service without an ADR. Dependency points inward; ports declared by consumers; adapters in infrastructure. | **PASS** |
| VI | Design for change without speculation | Constructor injection only; no Service Locator; no `BuildServiceProvider` during configuration. No provider-neutral abstraction before a second provider — the model port is the one exception and is justified below. | **PASS (one justified)** |
| VII | No client is a security boundary | Angular role checks presentation-only; Electron `contextIsolation` on, `nodeIntegration` off, sandbox on, narrow typed bridge, every IPC sender and argument validated, navigation allow-listed. | **PASS** |
| VIII | Provable by audit and by test | Correlation from the edge through every tier on W3C Trace Context. Full actor chain on every consequential action. All fifteen test categories appear in the stage plan. | **PASS** |
| IX | Scaffold honestly | UC-01–UC-12 are labelled placeholders. Four inert reference operations, production-excluded. Use cases are Stage 14, gated behind both golden paths. **Strengthened by the 2026-09-16 correction**: the scaffold no longer stands up an approval workflow against a fixture, which was the closest thing in this plan to inventing product. | **PASS** |
| X | Decisions recorded | ADR-0001–0005 govern this plan; divergences are listed below rather than left implicit. | **PASS** |

**Result**: no unjustified violations. One justified exception and three complexities, recorded below.

### Re-evaluation after the scaffold scope correction (2026-09-16)

The correction removes demonstrations, not controls. Re-checked against every principle, three deserve
a word:

- **Principle III — deterministic governance decides.** Not weakened. The gate, the catalogue and
  deterministic treatment classification are all still built and exercised in Stage 12. What is not
  built is the *workflow* behind two of the four treatments, and spec `FR-DEMO-018` closes the hole
  that would otherwise open: an operation requiring a human decision is refused or routed to manual
  fallback, **never auto-approved**. Without that rule the correction would have been a permission
  grant wearing the clothes of a scope reduction. **PASS.**
- **Principle IV — isolation absolute.** Strengthened in practice. Tenant propagation across the
  asynchronous hop is now an acceptance criterion (`SC-DEMO-006`) rather than an untested property of
  a path the scaffold never ran. **PASS.**
- **Principle IX — scaffold honestly.** Improved. An approval workflow exercised against an inert
  fixture proves that the fixture was wired up; it reads as product capability while being none.
  Removing it is the more honest scaffold, not the lesser one. **PASS.**

No principle moved from PASS. No new violation, no new justified exception, and the Complexity
Tracking table is unchanged — the correction adds no project, no library and no abstraction.

### Re-evaluation after the Integrations Service boundary (2026-09-18)

This change adds a deployable, which is the kind of change the constitution is most sceptical of. Six
principles deserve a word:

- **Principle I — identity derived once.** Unchanged and extended. The new service does not parse a
  token and consumes only the closed header contract; APIM re-derives identity on the hop. The one
  genuinely new risk — a tenant arriving in a Service Bus payload — is closed by deriving the
  organisation from durable state and, separately, refusing an out-of-contract field
  (`FR-DEMO-025`). **PASS.**
- **Principle III — the model proposes, governance authorizes.** Not weakened. Treatment assignment
  and role intersection **stay in RagCore** (`FR-INTEG-008`); the new service re-verifies *facts* and
  originates no authorization. A serialised `PROCEED` crossing the boundary would be a model-free but
  still *asserted* authority, which is why Stage 16 re-derives it instead. **PASS.**
- **Principle IV — one authority per concern.** The sharpest check. There is **no second durable
  authority**: `governance_record` stays in RagCore, `operation` remains the platform's conclusion,
  audit remains one store, and the Integrations Service owns only what nothing else owned — the
  connector registry and the execution record. The connector binding table did not previously exist,
  so nothing is split. **PASS.**
- **Principle V — boundaries mandatory; decomposition by ADR only.** This is the principle the change
  is governed by, and it cuts both ways: it *requires* an ADR for a context to become a service, and
  it *warns* that premature distributed decomposition is a defect. ADR-0007 exists and carries the
  justification — the blast radius of an orchestrator compromise currently includes every customer
  system credential. **PASS, conditional on ADR-0007 remaining Accepted.**
- **Principle VI — no speculative abstraction.** The live temptation is a shared Python library for
  what the two services have in common. Refused: duplication across a boundary is cheaper than a false
  shared contract, and a shared package would be a build-level dependency between deployables required
  to have none. Recorded in Complexity Tracking. **PASS.**
- **Principle VIII — provable by audit and test.** One correlation identifier still spans the journey,
  by W3C Trace Context, across the gateway hop and both queues. Two Principle VIII hard failures gain
  new surface and new tests: duplicate consequential execution from a retry — now proven at **both**
  boundaries independently — and execution without required authority, now re-verified at the point of
  effect. **PASS.**

**One new justified exception**, recorded in Complexity Tracking: a third deployable, and gateway hops
restored to the tool path that ADR-0001 removed. The latency consequence is real and is tracked as
OQ-06; no performance figure is an acceptance criterion, so nothing is gated on it.

### `senior_technician` — present, accepted by nothing

The role is implemented in both stacks' role enumerations (T023, T025) and appears in the canonical
`X-Idp-Roles` set, but **no operation in this plan declares it in an accepted-role set**, and no Entra
group maps to it. That is deliberate (spec FR-AUTHZ-008), and it is recorded here because its absence
from the task list would otherwise read as an oversight.

It exists now rather than later for one reason: adding a role to a set-intersection model is trivial,
but retrofitting one into a model that has meanwhile grown an implicit ordering is not. Holding an
unused member in the set is what keeps the no-hierarchy rule honest — a three-member set with one
member that grants nothing cannot be quietly reimplemented as a rank. The authorization matrix (T158)
covers it with every other role, and every one of its intersections is empty.

**An operation declaring `senior_technician` is a policy change, not an architecture change** — it
needs a catalogue entry and an Entra group, nothing more.

## Project Structure

### Documentation (this feature)

```text
specs/001-platform-scaffold/
├── spec.md              # Feature specification (/speckit-specify)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md                 # audience routing + conventions
│   ├── customer-api.md
│   ├── staff-api.md
│   ├── workload-api.md
│   ├── read-views.md             # the PostgreSQL view contract between deployables
│   ├── notifications.md          # SignalR envelope contract
│   └── triggers.md               # Service Bus message contract
├── checklists/
│   ├── requirements.md           # spec-quality gate
│   └── architecture.md           # architecture requirements-quality gate
└── tasks.md             # Created by /speckit-tasks — NOT by this command
```

### Source Code (repository root)

```text
synthia/
├── .github/workflows/                   # CI: per-stack pipelines + boundary checks
├── build/
│   ├── docker/                          # Dockerfiles for all three deployables
│   ├── infra/ai-gateway/                # AI Gateway policy configuration
│   └── scripts/                         # boundary-check and gate scripts
├── docs/adr/                            # ADR-0001..0005
│
├── apps/
│   ├── web/                             # ONE Angular workspace, three apps + four libs
│   │   └── projects/
│   │       ├── customer-portal/         # app
│   │       ├── staff-portal/            # app — Mission Control + Synthia Admin
│   │       ├── desktop-renderer/        # app — Electron renderer, reuses customer-features
│   │       ├── customer-features/       # lib — chat, session, consent, handoff  (SHARED)
│   │       ├── staff-features/          # lib — queue, take-over, reporting
│   │       ├── platform-core/           # lib — auth, API clients, realtime, correlation, errors
│   │       └── design-system/           # lib — a11y-verified primitives, no business logic
│   └── desktop/                         # Electron host — thin, decides nothing
│       └── src/{main,preload,ipc-contracts}/
│
├── dotnet/                              # READ-ONLY modular monolith
│   ├── src/
│   │   ├── Synthia.Api/                 # composition root: Minimal APIs, DI, middleware, health
│   │   ├── Synthia.SharedKernel/        # TenantId, StaffRole set-intersection, CorrelationId
│   │   ├── Synthia.Contracts/           # cross-module abstractions + DTOs (no implementation)
│   │   ├── Synthia.Persistence/         # EF Core read contexts mapped to versioned views
│   │   ├── Synthia.Observability/       # OpenTelemetry, structured logging, health
│   │   └── Modules/                     # Sessions, Work, Approvals, Governance, Audit, Tenancy
│   └── tests/                           # architecture, contract, authorization, isolation, unit
│
├── ragcore/                             # orchestration, execution, ALL writes
│   ├── src/ragcore/
│   │   ├── api/{customer,staff,workload,middleware}/
│   │   ├── domain/                      # pure model. No I/O, no imports beyond stdlib
│   │   ├── application/                 # use cases + PORTS (Protocols) adapters implement
│   │   ├── graph/                       # LangGraph state, nodes, three interrupts, checkpointer
│   │   ├── governance/                  # catalogue, treatment policy, control gate
│   │   ├── retrieval/                   # hybrid, rerank, confidence — mandatory tenant filter
│   │   ├── execution/                   # claim, idempotency, invocation, verification
│   │   ├── ingestion/                   # 12th context: acquisition, chunking, embedding, indexing
│   │   ├── integrations/                # servicenow/, graph/, onelogin/, duo/, mcp/, model/
│   │   ├── messaging/                   # outbox dispatcher, Service Bus publisher, resume consumer
│   │   ├── notifications/               # SignalR data-plane REST client
│   │   ├── persistence/                 # SQLAlchemy models, repositories, unit of work
│   │   └── config/                      # Pydantic Settings, Key Vault resolution
│   ├── migrations/versions/             # Alembic — owns every table AND every published view
│   ├── workers/                         # resume, outbox dispatch, expiry sweep, retention, ingestion
│   └── tests/                           # the fifteen categories
│
├── integrations/                        # THE INTEGRATIONS SERVICE — separate deployable (ADR-0007)
│   ├── src/integrations/
│   │   ├── api/                         # FastAPI transport ONLY. No business policy
│   │   │   ├── workload/                # catalogue read; inert system-of-record operations
│   │   │   ├── middleware/              # correlation, identity (header contract), problems
│   │   │   ├── health.py                # /health/live · /health/ready · /health/startup
│   │   │   └── openapi.py               # emitted from the running service, never hand-written
│   │   ├── application/                 # use cases + PORTS (Protocols) adapters implement
│   │   ├── domain/                      # pure model. No I/O, no imports beyond stdlib
│   │   ├── policy/                      # execution-time access + policy RE-CHECK (FR-INTEG-019)
│   │   ├── catalogue/                   # tool catalogue + connector registry + entitlement read
│   │   ├── credentials/                 # per-organisation Key Vault resolution. The ONLY such path
│   │   ├── connectors/                  # servicenow/, graph/, onelogin/, duo/, reference/
│   │   ├── mcp/                         # MCP client; discovery NEVER confers entitlement
│   │   ├── execution/                   # invocation, derived idempotency key, normalization
│   │   ├── messaging/                   # command consumer, result publisher, own outbox, DLQ
│   │   ├── persistence/                 # `integration` schema models, repos, view readers
│   │   ├── observability/               # OTel, structured logging, correlation, connector metrics
│   │   ├── config/                      # Pydantic Settings, Key Vault refs, startup validation
│   │   └── egress/                      # typed HTTP clients, resilience, explicit per-call timeout
│   ├── workers/                         # command consumer, result dispatcher, DLQ surfacer
│   └── tests/                           # the fifteen categories, this service's own
└── README.md
```

**Why these boundaries and not fewer.** Three of the splits carry a rule that collapses if they merge:

- **`policy/` is separate from `catalogue/`** because the re-check is a different act from the lookup.
  Folding the re-check into the reader is how "we already fetched the catalogue" silently becomes
  standing permission (`FR-INTEG-019`).
- **`credentials/` is separate from `connectors/`** so that one module is the only path from an
  entitlement row to a usable secret. A second path is a second place to review.
- **`mcp/` is separate from `connectors/`** because MCP's discover/invoke type separation is what
  enforces "discovery is not entitlement". Merging it into a generic connector package puts that
  enforcement where nothing guards it.

**The service is NOT RagCore's package renamed.** It carries no `graph/`, no `retrieval/`, no
`model/`, and no tool-selection reasoning. Model egress and content safety stay in
RagCore: that is reasoning, not integration.

### Dependency direction

Arrows point from dependant to dependency. Anything not drawn is prohibited.

```text
ANGULAR     apps → customer-features | staff-features → platform-core → design-system

ELECTRON    main → ipc-contracts ← preload
            main/preload NEVER import Angular; the renderer is the built bundle

.NET        Synthia.Api → Modules.* → Synthia.Contracts → Synthia.SharedKernel
            Modules.* → Synthia.Persistence → Synthia.SharedKernel
            Modules.* ↛ Modules.*              (no module references another)
            Synthia.Api is the ONLY composition root

RAGCORE     api → application → domain
            graph | governance | execution | ingestion → application → domain
            retrieval | messaging | notifications | persistence
                                        → implement ports declared in application
            domain imports NOTHING outside the standard library

INTEGRATIONS
            api → application → domain
            policy | catalogue | execution → application → domain
            connectors | mcp | credentials | egress | messaging | persistence
                                        → implement ports declared in application
            credentials ← connectors | mcp        (the ONLY path to a connector secret)
            domain imports NOTHING outside the standard library
            NO graph, NO retrieval, NO model egress, NO tool-selection reasoning

MODELS      ragcore → AI Gateway → model provider   (no direct provider access)
            integrations ↛ AI Gateway               (it does no reasoning)

ACROSS      dotnet ↛ ragcore    and    ragcore ↛ dotnet
            They meet only at PostgreSQL (versioned views) and Service Bus (opaque triggers).

            ragcore → integrations                  (via APIM sync, via Service Bus async)
            integrations ↛ ragcore                  (NO reverse call — this keeps the graph acyclic)
            dotnet ↛ integrations  and  integrations ↛ dotnet

            ragcore      ↛ ServiceNow · Graph · OneLogin · Duo · any MCP server
            ragcore      ↛ connector secrets in Key Vault      (role assignment, not code)
            integrations ↛ any platform base table             (reads vw_*_v1 only)
            integrations ↛ any non-result column of a job row  (cannot rewrite its instruction)
            integrations ↛ SignalR                             (notification is RagCore's leaf)
            any deployable ↛ any other by internal address     (must traverse APIM)
```

### Where each bounded context lives

A context is **not** assigned to one deployable. It is assigned a write side and, where it has one, a
read model — and the two sit on opposite sides of the published-view contract. This is CQRS, and it
falls out of ADR-0001 rather than being chosen separately: RagCore owns every state change, the
monolith reads. **A context appearing on both sides is the intended shape, not a boundary breach.**

*Revised 2026-09-18.* Three contexts now have their write side in the **Integrations Service**.

| Context | Write side | Read model — monolith |
|---|---|---|
| Session | RagCore `application/sessions.py`, `api/customer/` | `Modules/Synthia.Modules.Sessions` |
| Work | RagCore `execution/`, `application/` | `Modules/Synthia.Modules.Work` |
| Governance | RagCore `governance/` | `Modules/Synthia.Modules.Governance` |
| Approval | RagCore `application/approvals.py`, `api/staff/`, `api/customer/consent.py` | `Modules/Synthia.Modules.Approvals` |
| Audit | RagCore `application/audit.py` | `Modules/Synthia.Modules.Audit` |
| Tenant & Configuration | RagCore `config/`, `persistence/` | `Modules/Synthia.Modules.Tenancy` |
| Agent / RagCore | RagCore `graph/` | — none. Working state is never published |
| Retrieval | RagCore `retrieval/` | — none |
| **Tool Execution** | **Integrations** `catalogue/`, `policy/`, `execution/`, `mcp/` | — none |
| **Integration — ServiceNow** | **Integrations** `connectors/servicenow/` | — none |
| **Integration — Microsoft Graph** | **Integrations** `connectors/graph/` | — none |
| Ingestion | RagCore `ingestion/`, `workers/ingestion_run.py` | — none |

**The rule that makes this checkable.** A context's write side is exactly one package in exactly one
deployable; its read model is at most one monolith module; the two communicate **only** through a
`vw_*_v1` view and never by call, reference or shared type. Six contexts have no read model because
nothing outside their owner needs to read them — and adding one means adding a published view, which
is a contract change under `contracts/read-views.md`, not an implementation detail.

**The three moved contexts keep their read-model answer — none — but gain a second reader.** The
Integrations Service reads `platform` state through published views, exactly as the monolith does. The
ADR-0001 view contract was written assuming the monolith was its only reader; extending it to a third
reader is a real change to that contract's scope, not a free reuse, and `contracts/read-views.md` must
say so.

### Composition roots

One per deployable, named, and the only place registration happens. A dependency constructed anywhere
else is a defect in all four.

| Deployable | Composition root | Enforced by |
|---|---|---|
| .NET monolith | `Synthia.Api/Program.cs` | T035 — no Service Locator, no `BuildServiceProvider` during configuration |
| RagCore | `ragcore/src/ragcore/config/composition.py` — builds every adapter and binds it to the port it implements; FastAPI `Depends` resolves from it and constructs nothing itself | Import-boundary test: no module outside it instantiates a concrete adapter |
| Integrations Service | `integrations/src/integrations/config/composition.py` — same contract, its own root | Same import-boundary test, its own suite |
| Angular workspace | `platform-core` providers, wired at each app's `bootstrapApplication` | ESLint library-boundary rules (T011) |
| Electron host | `apps/desktop/src/main/index.ts` | The renderer receives only the `contextBridge` surface (T051) |

**Structure Decision**: **five** top-level source trees — `apps/web`, `apps/desktop`, `dotnet`,
`ragcore`, `integrations`. One Angular workspace so the customer feature libraries are genuinely
shared rather than duplicated. The three backend trees are siblings with **no build-level
relationship**, which makes the dependency rules structural: a reference cannot be added without
appearing in a diff as a new cross-tree path, and `build/scripts/check-boundaries` fails CI if one
does.

`ragcore/` and `integrations/` are **separate Python projects** — separate `pyproject.toml`, separate
`uv.lock`, separate virtual environment, separate CI pipeline. **Neither imports the other.** The
temptation to extract a shared library for the things they have in common — correlation middleware,
the problem-details shape, the settings base, the telemetry setup — is the one to refuse: constitution
Principle VI holds that DRY applies *within* a module boundary and that duplication across boundaries
is cheaper than a false shared contract. A shared package here would be a build-level dependency
between two deployables that are required to have none.

## Divergences from the Authoritative Specification

`Synthia-Platform-Specification.md` is authoritative on architecture. This plan departs from it in four
recorded places, listed here so a plan reader sees them without having to find the constitution's
change log.

| # | Authoritative position | This plan | Recorded in | Status |
|---|---|---|---|---|
| 1 | §14.1 defines eleven independently addressable bounded contexts | **Three** application deployables. Eight contexts' write sides are RagCore packages; **three — Tool Execution, Integration — ServiceNow, Integration — Microsoft Graph — are the Integrations Service**; read models, where they exist, are monolith modules | ADR-0001, **narrowed by ADR-0007** | Accepted |
| 2 | §31.4 shows a synchronous chain `Session → RagCore → Retrieval → Governance → Tool Execution` | RagCore owns the chain **as far as Tool Execution** with no gateway hops between its stages; the tool-execution leg crosses to the Integrations Service | ADR-0001, **narrowed by ADR-0007** | Accepted |
| 3 | §37.1 defers the customer web portal beyond the initial release | Included as a scaffolded Angular application with no product behaviour | Constitution divergence register | Accepted |
| 4 | OneLogin and Duo appear nowhere in the specification | Sanctioned third-party target systems reached as MCP servers; an open set | ADR-0005 | Accepted |

**Divergences 1 and 2 shrank on 2026-09-18 rather than growing.** ADR-0007 returns three contexts to
the independently deployed shape §14.1 always described, so the plan now diverges from the
specification in *fewer* places than before. §21.6 describes the Integrations Service directly; its
existence is not a divergence.

**Nothing else diverges.** The twelve bounded contexts are preserved as responsibilities — none added,
none removed. Every piece of infrastructure appears in §9.3. §13.4's no-direct-service-to-service rule
holds between **all three** deployables, and the RagCore → Integrations path is its newest and most
load-bearing instance. If any of the four is withdrawn, this plan must be revised before
implementation continues.

### Recorded conflict, not resolved here

The constitution states the general rule that **EF migrations run in CI and deployment using migration
bundles**. ADR-0001 and ADR-0003 make the .NET monolith read-only with no schema ownership, so that
rule has **no current application**: Alembic owns every migration and the monolith reads versioned
views. Soft-delete, global query filters and audit columns are therefore schema rules owned by
RagCore's migrations, which the published views must respect. **If .NET is intended to own schema,
ADR-0001 and ADR-0003 must be amended before Stage 7.** This plan does not decide that.

## Implementation Stages

**Seventeen ordered stages.** Stages 1–11 are **scaffolding only** and contain no product behaviour.
Stages 12–13 prove the first two architectural golden paths. **Stages 15–17 build the Integrations
Service and prove its boundary, and run after Stage 13 and before Stage 14.** Stage 14 is gated behind
all five.

Execution order: `1 → 2 → … → 13 → 15 → 16 → 17 → 14`. Numbers are append-only and never reused, so
the order is stated here rather than inferred from the integer.

---

### Stage 1 — Repository and tooling foundation

**Objective.** A monorepo skeleton with both toolchains, CI and boundary enforcement. Nothing runs yet.

**Architectural boundaries.** Repository level only; no runtime boundary is crossed.

**Components.** Root layout; `Directory.Build.props`, `Directory.Packages.props`, `.editorconfig`;
`pyproject.toml` + `uv.lock`; Angular workspace config; Electron package config; `build/scripts/`;
five CI workflows.

**Dependencies.** None.

**Contracts.** None.

**Infrastructure.** None — local only.

**Security.** `.gitignore` excludes build artifacts; secret scanning in CI; no credential in source, in
tests, or in committed local configuration.

**Testing.** CI executes empty suites successfully; `check-boundaries` fails on a planted cross-tree
reference.

**Validation gates.** All five workflows green on an empty repository. `dotnet build -warnaserror`
succeeds. `ruff check`, `ruff format --check` and strict type checking succeed. The boundary script
demonstrably fails a planted violation.

**Non-goals.** No application code, no Azure resources, no database.

---

### Stage 2 — Shared contracts and architecture boundaries

**Objective.** Establish dependency direction and the tests that guard it **before** any feature code
exists, so boundaries are enforced from the first commit rather than retrofitted.

**Architectural boundaries.** Defines all of them: composition roots, ports, the inward dependency rule,
the no-cross-deployable rule.

**Components.** `Synthia.SharedKernel` (TenantId, StaffRole, CorrelationId); `Synthia.Contracts`;
`ragcore/domain/` (pure); `ragcore/application/ports.py` (Protocols);
`apps/desktop/src/ipc-contracts/`; `platform-core` skeleton.

**Dependencies.** Stage 1.

**Contracts.** Ports as Protocols and interfaces; typed IPC channel contracts; the role set-intersection
primitive in both stacks, with **no ordering or comparison operator defined**.

**Infrastructure.** None.

**Security.** Set intersection is the only authorization primitive. `Synthia.Api` is the sole composition
root; Service Locator and `BuildServiceProvider`-during-configuration are prohibited and tested for.

**Testing.** Architecture — module isolation, no-cross-deployable dependency, banned APIs
(`DateTime.Now`, `.Result`, `.Wait()`, `GetAwaiter().GetResult()`, `catch (Exception)` without rethrow).
Import-boundary tests asserting `domain/` imports nothing outside the standard library. Mirrored unit
tests for set intersection in both stacks.

**Validation gates.** Every architecture test fails when its violation is planted and passes otherwise.
No role comparison exists in either stack.

**Non-goals.** No persistence, no HTTP, no business logic, no infrastructure adapters.

---

### Stage 3 — Angular scaffold

**Objective.** Three applications and four libraries that build, route and render, with authentication,
API and realtime infrastructure centralized.

**Architectural boundaries.** Presentation only. No authorization, tenancy or policy decision.

**Components.** `customer-portal`, `staff-portal`, `desktop-renderer`; `customer-features`,
`staff-features`, `platform-core`, `design-system`.

**Dependencies.** Stage 2 (typed contracts).

**Contracts.** Typed API clients against `contracts/`; correlation propagation; RFC 9457
problem-details handling.

**Infrastructure.** None at runtime; CI only.

**Security.** Role gating is presentation-only and re-decided server-side. Route guards are not security
boundaries. No secret in browser code. Angular sanitization respected; `bypassSecurityTrust*` absent.

**CSP baseline for the two browser surfaces.** Delivered as a response header, not a `<meta>` tag, so
it cannot be stripped by injected markup:

```text
default-src 'self';
script-src 'self';                         # no 'unsafe-inline', no 'unsafe-eval', no CDN
style-src 'self' 'nonce-{random}';         # Angular's injected styles carry the nonce
img-src 'self' data:;
font-src 'self';
connect-src 'self' https://{gateway-origin} wss://{signalr-origin} https://login.microsoftonline.com;
frame-ancestors 'none';
form-action 'self';
base-uri 'none';
object-src 'none';
upgrade-insecure-requests
```

`connect-src` is the load-bearing directive: exactly one platform origin (FR-SURF-017), the SignalR
endpoint, and the Entra authority. **A surface that needs a directive loosened states why in review** —
particularly `script-src`, where `'unsafe-eval'` would be required by a JIT Angular build and is the
reason the build is AOT.

**Testing.** Unit tests on the project-supported runner; ESLint library-boundary rules; axe-core
accessibility sweep; a test asserting no authorization decision exists in a presentation component.

**Validation gates.** All three apps build under strict TypeScript. Zero axe-core Level A/AA failures on
scaffolded journeys. Boundary lint fails when `customer-features` imports `staff-features`.

**Non-goals.** No chat behaviour, no approval queue behaviour, no use-case UI.

---

### Stage 4 — Electron scaffold

**Objective.** A thin, hardened host that renders the desktop renderer and decides nothing.

**Architectural boundaries.** Host only. No business policy in the renderer **or** the main process.

**Components.** `apps/desktop/src/main/`, `preload/`, `ipc-contracts/`.

**Dependencies.** Stages 2 and 3.

**Contracts.** The narrow typed `contextBridge` surface; validated IPC channel schemas.

**Infrastructure.** None.

**Security.** `nodeIntegration=false`, `contextIsolation=true`, `sandbox=true`. Raw `ipcRenderer` never
exposed; no broad Electron or Node API on the bridge. **Every IPC sender and every IPC argument
validated.** `webSecurity` never disabled; `shell.openExternal` never receives an untrusted URL.

**`sandbox=true` is unconditional in this scaffold.** The constitution says "where compatible"; for
this application nothing makes it incompatible, so the discretion is resolved here rather than left to
the implementer. Sandbox breaks only for a renderer needing Node built-ins in the preload — and this
preload needs none, because it exposes a narrow typed bridge and nothing else. **Turning it off
requires an ADR**, not a code comment.

**Navigation allow-list — the complete set.** `will-navigate` and `setWindowOpenHandler` both deny by
default and permit only:

| Destination | Why |
|---|---|
| The renderer's own bundle origin | The application itself |
| `https://{gateway-origin}` | The single platform origin (FR-SURF-017) |
| `https://login.microsoftonline.com` and the tenant authority | Interactive Entra sign-in |

Everything else is refused. `setWindowOpenHandler` returns `{ action: 'deny' }` for every destination
without exception — an external link is handed to `shell.openExternal` after the same allow-list check,
so no destination reaches the OS handler that could not have been navigated to in-app. Scheme matching
is exact: `https:` and `wss:` only, never `http:`, `file:` or a custom scheme.

**CSP for the renderer** is the Stage 3 baseline with `connect-src` narrowed identically, delivered by
`onHeadersReceived` in the main process so the renderer cannot weaken it.

**Testing.** An Electron security suite asserting each of the above, including that IPC rejects an
unvalidated message and navigation outside the allow-list is blocked.

**Validation gates.** The security suite passes, and fails correctly when a setting is flipped.

**Non-goals.** No script execution — the catalogue is empty until Stage 11. No authorization logic.

---

### Stage 5 — .NET scaffold

**Objective.** A read-only modular monolith that starts, serves versioned resource-oriented APIs and
enforces its own module boundaries — with no data behind it yet.

**Architectural boundaries.** Six modules, none referencing another; `Synthia.Api` the only composition
root.

**Components.** `Synthia.Api`; `Modules/{Sessions,Work,Approvals,Governance,Audit,Tenancy}`;
`Synthia.Contracts`; a `Synthia.Persistence` skeleton.

**Dependencies.** Stages 1–2.

**Contracts.** `/api/{audience}/v1/views/...` routing; URI-segment versioning; plural resource nouns;
kebab-case multi-word segments; camelCase JSON; built-in OpenAPI; keyset pagination with **opaque**
cursors; typed filters; whitelisted sort fields.

**Infrastructure.** None yet — endpoints return empty, well-formed payloads.

**Security.** Gateway-derived identity header contract; no token parsing; no endpoint accepts tenant or
role as a parameter. `ProblemDetails` via `IExceptionHandler`, never exposing internal detail.

**Testing.** Contract tests for casing, pagination shape, versioning and problem-details. Architecture
tests for module isolation and for the absence of `Database.Migrate()`, `EnsureCreated()` and EF
migration files.

**Validation gates.** The app starts, `/health/live` responds, OpenAPI generates, contract tests pass.

**Non-goals.** No EF contexts, no database, and no write endpoint — ever.

---

### Stage 6 — RagCore scaffold

**Objective.** A FastAPI application and LangGraph skeleton with the three interrupt points, ports
declared and adapters absent.

**Architectural boundaries.** `api → application → domain`; adapters implement ports; `domain` imports
nothing outside the standard library. Includes `ingestion` as the twelfth context.

**Components.** `api/{customer,staff,workload,middleware}`, `application/`, `domain/`, `graph/`,
`governance/` skeleton, `ingestion/` skeleton, `config/` (Pydantic Settings).

**Dependencies.** Stages 1–2.

**Contracts.** Pydantic request/response schemas; the SSE streaming envelope; explicit DI through
FastAPI `Depends` at HTTP boundaries only.

**Infrastructure.** None yet — the graph runs in memory.

**Security.** Identity header, correlation and problem-details middleware. No endpoint accepts tenant or
role. Endpoints contain no business policy.

**Testing.** Contract tests for the API surface; import-boundary tests; async cancellation tests
asserting `asyncio.CancelledError` propagates and is never swallowed.

**Validation gates.** `mypy --strict` clean; `ruff` clean; the graph suspends and resumes in memory at
all three interrupt points.

**Non-goals.** No persistence, no model calls, no governance decisions, no product behaviour.

---

### Stage 7 — PostgreSQL and persistence scaffold

**Objective.** The authoritative durable store, its migration discipline, and the read-view contract
between the deployables.

> *Extended by Stage 16 (2026-09-18).* The `integration` schema, the `integration_job` table with its
> column-scoped grants, and a third database principal are added there. The migration discipline
> established here — one Alembic project, a gated job, never at startup, expand/contract — is
> unchanged and governs them.

**Architectural boundaries.** RagCore owns every table, every migration and every published view. The
monolith reads views only.

**Components.** `ragcore/migrations/`, `ragcore/persistence/`; `Synthia.Persistence` read contexts; the
`langgraph` schema owned by the checkpointer, with the graph **compiled against the PostgreSQL
checkpointer** and its `setup()` run from the migration job; `workers/retention_sweep.py` and
per-organisation erasure.

**Dependencies.** Stages 5–6.

**Contracts.** [contracts/read-views.md](./contracts/read-views.md) — versioned `vw_*_v1` views, never
altered in place. The schema is the contract; changing a view is a breaking change.

**Infrastructure.** PostgreSQL Flexible Server. **No second database, no second checkpoint store.**

**Security.** Separated database principals — the migration job holds DDL, the RagCore runtime DML and
SELECT, the monolith runtime SELECT on views only. Authority fields immutable at the permission
boundary. `tenant_id` on every table and every view.

**Testing.** `pytest-alembic` — single head, upgrade from base, models match DDL, and **every downgrade
succeeds**. Tenant-isolation tests. A test asserting autogenerate never proposes a change inside the
`langgraph` schema, and one asserting the compiled graph carries the PostgreSQL saver with no in-memory
saver on a non-test path. Retention tests per class, including that expiring chat content leaves its
audit records intact. Concurrency tests for optimistic concurrency and the atomic claim.

**Validation gates.** Migrations run as a gated job before revision activation, never at startup.
Expand/contract holds: no destructive change ships alongside the code that depends on it. Read
Committed is the default; Serializable is used only where a named invariant requires it.

**Non-goals.** No EF migrations in .NET — see the recorded conflict above. No business tables for use
cases. No ingestion behaviour — the worker entry point is scaffolded, nothing acquires.

---

### Stage 8 — Messaging and realtime scaffold

**Objective.** Durable asynchronous plumbing: transactional outbox, opaque triggers, at-least-once
consumption, and notification-only realtime.

**Architectural boundaries.** Messaging and notification adapters implement ports; neither carries
authority.

**Components.** `ragcore/messaging/` (outbox dispatcher, publisher, resume consumer);
`ragcore/notifications/` (SignalR data-plane REST client); `workers/` (resume, outbox dispatch, expiry
sweep).

**Dependencies.** Stage 7 — the outbox is a table.

**Contracts.** [contracts/triggers.md](./contracts/triggers.md) — a trigger carries `workItemId`,
`correlationId` and `kind` and **nothing else**.
[contracts/notifications.md](./contracts/notifications.md) — the envelope carries no authority-bearing
value.

**Infrastructure.** Azure Service Bus Standard; Azure SignalR through its data-plane REST API with an
Entra token from managed identity.

**Security.** Every trigger is untrusted; authority comes from the durable work record. SignalR is a
leaf on every consequential path, never a link. Group membership is derived from trusted identity at
negotiation.

**Testing.** Idempotency — a duplicate trigger produces exactly one effect. Concurrency — competing
claims resolve to one owner. Outbox — a record becomes durable before publication, and a crash between
the two loses nothing.

**Validation gates.** Duplicate delivery is absorbed by the atomic claim. An expired message
dead-letters rather than executing, and dead-lettered approved work surfaces to humans.

**Non-goals.** No approval semantics yet — that is Stage 13.

---

### Stage 9 — Integration adapter scaffold

> **Superseded in placement, not in substance — 2026-09-18.** This stage was built and its adapters
> work. ADR-0007 moves them out of RagCore into the Integrations Service; **Stage 16 is the migration
> and is where the work now lives.** The ports-and-adapters design, the no-provider-leak rule, the
> resilience policy and the discovery-is-not-entitlement enforcement all carry over unchanged — which
> is why Stage 16 is a move rather than a rewrite. Read this stage for the design; read Stage 16 for
> where it ends up. Paths below are the *original* locations and are stale by design.

**Objective.** Every external system behind an explicit port, with no provider type reaching inward.

**Architectural boundaries.** Ports in `application/`; adapters in `integrations/`. Provider SDK and
model types MUST NOT appear in `domain/` or `application/`.

**Components.** `integrations/{servicenow,graph,onelogin,duo,mcp,model}/`; `build/infra/ai-gateway/`.

**Dependencies.** Stages 6–7.

**Contracts.** One port per capability; an MCP client where the provider is an MCP server; the model
port routed exclusively through the AI Gateway.

**Infrastructure.** ServiceNow, Microsoft Graph, OneLogin, Duo (ADR-0005), the AI Gateway, Azure OpenAI
and Foundry, Azure AI Search.

**Security.** Credentials per organisation and per system from Key Vault, never surfaced in
conversation, step trail, telemetry or audit. `IHttpClientFactory` with typed clients, a consistent
resilience policy distinguishing transient from non-transient failure, and an **explicit timeout on
every outbound call**. Discovery never confers entitlement. Provider output is data, never instruction,
and is rejected at the boundary when malformed.

**Testing.** Adapter tests per provider against fakes honouring the contract; a test asserting no
provider type appears in `domain/` or `application/`; entitlement tests asserting an unregistered
advertised capability is not callable.

**Validation gates.** The no-leak test passes. No direct provider access exists outside
`model/`. No `HttpClient` is constructed manually.

**Non-goals.** No real tenant credentials. No use-case operations.

---

### Stage 10 — Observability, configuration and container scaffold

**Objective.** Make the system explicable and deployable: traces, correlation, structured logging,
validated configuration, hardened images.

**Architectural boundaries.** Cross-cutting; must not hide business policy.

**Components.** `Synthia.Observability`; `ragcore/observability/`; typed options in both stacks;
`build/docker/`; health endpoints.

**Dependencies.** Stages 5–6.

**Contracts.** Correlation accepted at the edge when well formed, generated when absent, echoed in
responses, bound to the logging scope and OpenTelemetry context, and carried on every trigger,
notification and audit record. W3C Trace Context; no custom propagation header replaces it.

**Infrastructure.** Application Insights / Azure Monitor; Azure Container Apps; and — newly
acceptance-critical — Front Door + WAF and APIM.

**Sequencing note, added 2026-09-16.** `FR-DEMO-019` makes edge traversal part of scaffold acceptance,
so the environment this stage configures is no longer a deployment concern that can trail the build:
Stage 13 cannot be *accepted* until Front Door, WAF and APIM are provisioned and APIM derives identity.
The work stays in this stage; what changed is that it now gates a later stage rather than only
preceding it. Provisioning should start as early as it can be started, because every sample flow will
pass locally right up until the moment it has to cross a boundary that does not exist yet.

**Security.** Logs and telemetry leak no secret, token, authorization header, sensitive payload or
cross-tenant value. Secrets resolve through managed identity and Key Vault.

**Testing.** Configuration-validation tests — options bind, validate and **fail fast at start**.
Security tests asserting no sensitive value reaches a log sink. A trace test following one request
across suspension and resume.

**Validation gates.** `/health/live` is process-only; `/health/ready` covers database and critical
dependencies.

Container hardening is stated **per image**, because the two runtimes do not share a base family and a
single combined list is unsatisfiable — `chiseled` is a .NET image family, and R-012 chose a *slim*
Python base, which has a shell by design.

| | .NET monolith (R-011) | RagCore (R-012) |
|---|---|---|
| Base | `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled` | slim Python 3.12 |
| Digest-pinned in production | Required | Required |
| Runs as | Non-root, UID 1654 (the chiseled convention) | Non-root, one fixed documented UID |
| Shell and package manager | **Absent** — a property of chiseled | Present in the base; the final layer carries **no build toolchain and no package-manager cache** |
| Installed from | Published output only | `uv.lock` only |
| Root filesystem | Read-only | Read-only, with any writable path named explicitly rather than implied |

Both images additionally carry explicit resource limits and HTTP health probes.

**Digest-update process.** A pinned digest is only a control if something re-pins it, so the process is
defined rather than merely required to exist:

| | |
|---|---|
| Owner | The platform team; the re-pin lands as an ordinary reviewed pull request, never an out-of-band registry change |
| Triggers | (a) a CVE at High or Critical against either base image, (b) a monthly scheduled check, (c) a base-image release carrying a runtime patch |
| Mechanism | A scheduled CI job resolves the current digest for each tracked tag, opens a PR when it differs, and attaches the vulnerability diff |
| Gate | The PR passes the full suite — both stacks, architecture tests, migration tests, boundary check — plus an image scan showing no new High or Critical. A digest never reaches production on a green scan alone |
| Emergency path | A Critical CVE with a published fix may skip the schedule but not the gate |

**Drain and in-flight work.** The 25-second drain is a *grace period, not a guarantee*, and what
happens when it elapses is stated because it collides with `FR-EXEC-006`'s no-retry rule:

- On `SIGTERM` an API replica stops accepting requests and finishes those in flight. Nothing is
  claimed, so nothing is at risk.
- A **worker** replica stops taking messages and finishes the message it holds. If it is *pre-claim*,
  the message returns to the queue and another replica takes it — at-least-once delivery covers this
  and the atomic claim absorbs the duplicate.
- If it is **post-claim and the drain elapses mid-execution**, the work stays claimed, unexecuted and
  non-retriable. **This is exactly the approved-but-not-executed condition of ADR-0002**: it surfaces
  in `vw_approval_unexecuted_v1` and the staff portal, raises an operational alert, and recovers only
  through fresh authorization. It is never silently re-fired, and a drain is never a reason to
  re-fire it.

The practical consequence is a scheduling rule: **workers scale in on a drain longer than the longest
single external call**, which is why every outbound call carries an explicit timeout (Stage 9). An
execution that cannot finish inside the drain is one whose timeout was set wrong.

**Telemetry retention and sampling** (`FR-OPS-011`, `FR-OPS-012`). Telemetry retains 30 days against
audit's 7 years, which is what makes "telemetry may never answer an audit question" true in practice
rather than only by policy. Sampling is **tail-based, keyed on the correlation identifier**, so a
journey that suspends and resumes hours later is sampled as one unit. Head sampling is prohibited
here: it decides at the first span, before the journey is known to be interesting, and would routinely
keep the request half of an approval journey and discard the resume half — defeating `SC-OPS-001`.
Every trace carrying an error, a governance denial or an approval is retained regardless of sampling.

**Non-goals.** No dashboards, no alert tuning, no performance targets.

---

### Stage 11 — Architecture and security test foundation

**Objective.** Complete the enforcement surface, and seed the four inert reference operations so the
governance paths become demonstrable.

**Architectural boundaries.** Guards every boundary defined in Stages 2–10.

**Components.** `dotnet/tests/Synthia.ArchitectureTests`;
`ragcore/tests/{architecture,isolation,authorization,governance,security}`; `governance/fixtures.py`.

**Dependencies.** Stages 2–10.

**Contracts.** The reference operations — one per execution treatment — inert, labelled scaffold
fixtures, excluded from production configuration, never counted as a use case.

**Infrastructure.** Test PostgreSQL and Service Bus via Testcontainers or emulators.

**Security.** The full authorization matrix — every role combination against every operation, including
the empty intersection and the `administrator`-does-not-imply-`technician` case. Adversarial
cross-tenant retrieval. A test asserting no catalogue entry can be created with `requires_elevation`.

**Testing.** All fifteen categories present and wired into CI: unit, integration, contract,
architecture, authorization, tenant isolation, retrieval isolation, governance, approval, idempotency,
concurrency, adapter, configuration, security, golden path.

**Validation gates.** Every one of the seven **hard failures** in Principle VIII has a test that fails
when its protection is removed. That is the gate: a protection without a failing test does not count.

**Non-goals.** No product behaviour. Fixtures are not use cases.

---

### Stage 12 — Golden path A: `AUTO` execution

**Objective.** Prove the full machine end to end for an operation that needs no human: propose → gate →
execute → verify → audit — and prove the same gate refuses, by demonstrating `NOT_ALLOWED`.

**Architectural boundaries.** Exercises every context except Approval.

**Components.** Governance treatment policy; control gate; Tool Execution; verification; audit;
retrieval (hybrid, rerank, confidence and margin); model access through the AI Gateway; content safety.

**Dependencies.** Stages 1–11.

**Contracts.** Customer API session and streaming; Workload API claim and outcome; the audit actor
chain.

**Infrastructure.** All of it, together for the first time.

**Security.** Treatment comes from the catalogue, never from model output. Retrieved and fetched content
is data, never instruction. Content safety runs inbound before the model and outbound before a response
returns.

**Testing.** Governance; idempotency; retrieval isolation; end-to-end golden path.

**Threshold boundary semantics.** The knowledge condition compares an absolute score and a margin
against global constants (`FR-AGENT-006`, `FR-AGENT-007`). **Both comparisons are `>=`: a value exactly
equal to its threshold passes.** The threshold is the lowest acceptable value, not the first
unacceptable one. This is stated because the choice is invisible in review — two implementers will
split on it, both will believe they chose the obvious reading, and the resulting behaviour differs only
on the exact boundary, which is precisely where a confidence gate is most often wrong. The constants
and their comparison direction live in one module (`retrieval/confidence.py`) and nowhere else, and
the unit tests assert the boundary case explicitly in both directions.

**Validation gates.** The `AUTO` reference operation completes with a verified outcome and a full actor
chain. The `NOT_ALLOWED` reference operation is refused at the gate, never surfaced as an approvable
proposal, and recorded as a denial. The two human-decided treatments are **classified** from the
catalogue and their operations refused or routed to manual fallback rather than auto-approved
(spec `FR-DEMO-018`) — classification is proven here, the workflows are not built
(`SC-SCOPE-002`, amended). A planted injection in retrieved content produces at most a
proposal, never an execution. A near-tie and a confident singleton at the same top score route
differently. A score exactly equal to the absolute threshold, and a margin exactly equal to the margin
threshold, both pass — asserted directly rather than inferred.

**Non-goals.** No approval workflow, no consent workflow, no desktop execution, no use case.

---

### Stage 13 — Golden path B: asynchronous platform integration

*Replaced 2026-09-16. The previous Stage 13 proved a governed human decision — durable suspension, an
authenticated verdict, resume. That machine is **not removed**; it remains specified in
spec `FR-INTR-*`, `FR-EXEC-*` and User Stories 2 and 3, and moves past the scaffold under
`FR-DEMO-016`. What replaces it proves the seams underneath it, which is what the scaffold is for.*

**Objective.** Prove the platform's asynchronous integration end to end, on inert fixtures: a request
entering at the public edge, becoming durable state, crossing the deployable boundary through the
outbox and the bus, being acted on by the workload leg, and returning to the client as a notification —
with one correlation identifier and one organisation binding intact the whole way.

**Why this is the harder half.** Golden path A proves a synchronous machine inside one process. Every
failure mode that actually costs a platform its integrity lives in the seams this stage crosses: the
transaction boundary between a state change and the message announcing it, the identity of one service
reaching another, the organisation binding surviving a hop that carries no tenant, and the duplicate
delivery that at-least-once guarantees will arrive. None of those is exercised by a product workflow.

**Architectural boundaries.** Exercises the Session, Work, Tool Execution, Notification and Ingestion
read paths, plus the .NET read side. **Adds no bounded context and moves no boundary.**

#### Flow B1 — the asynchronous round trip

```text
Customer API (Front Door + WAF → APIM → RagCore)
  → PostgreSQL transaction
  → transactional outbox row, same transaction
  → Azure Service Bus
  → Workload API / worker
  → sample inert execution
  → persistence of the outcome
  → Azure SignalR notification
  → client state refresh
```

The outbox row and the state change commit **together or not at all**. The trigger on the bus carries
opaque identifiers and correlation only — no tenant, requester, role, action, target or approval state
— so the workload leg reads its authority from the durable record rather than from the message that
woke it. The claim is atomic, making a duplicate delivery a no-op rather than a second effect. The
notification is a **leaf**: the client refreshes its state by reading back through the API, and the
flow's outcome is identical if no client was ever connected.

#### Flow B2 — the .NET read seam

```text
Staff API (Front Door + WAF → APIM → .NET read API)
  → PostgreSQL published view (vw_*_v1)
  → response
```

Proves the read contract as a *runtime* boundary rather than a documented one. The monolith reaches
PostgreSQL as its own least-privileged principal holding `SELECT` on published views and nothing else:
a query attempting a base table fails at the database. The staff caller's target organisation is
resolved from the platform object being read, never from the request.

#### Flow B3 — the service boundary

```text
Customer API (Front Door + WAF → APIM → RagCore)
  → workload / service boundary (app-only, via APIM)
```

Proves that a synchronous service-to-service call routes **through APIM** and that no direct route
exists (spec `SC-DEMO-003a`).

> **The negative half is narrower than it was.** It used to include a request carrying a well-formed
> but self-supplied gateway header contract — the shape a real bypass takes. That is `SC-DEMO-003b`,
> which is **deferred** along with the mechanism that made it fail (see *Deferred* below and
> [ADR-0008](../../docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md)). What is proved here now is that a direct request carrying **no**
> contract fails. A complete forgery from inside the environment is not refused.

**Components.** Sample-flow endpoints on all three audiences; the outbox dispatcher; the Service Bus
consumer; the workload claim and outcome path; the SignalR notification client; the .NET read modules
over published views; OpenTelemetry propagation across both deployables.

**Dependencies.** Stage 12, and — newly load-bearing — a **provisioned environment including the edge**.
Every flow in this stage is accepted only when driven through Front Door + WAF + APIM (`FR-DEMO-019`).
This is the longest-lead dependency in the scaffold: all three flows will pass against the deployables
long before they can be accepted.

**Contracts.** Customer, staff and workload API sample-flow operations, each in its own emitted OpenAPI
document; the trigger contract; the notification envelope; the published read views.

**Infrastructure.** Front Door + WAF, APIM, Container Apps, PostgreSQL Flexible Server, Service Bus,
SignalR, Key Vault, Application Insights — all on the critical path together for the first time.
**No new infrastructure.**

**Security.** Identity is derived once, at APIM; neither deployable parses a token. Every hop
authenticates as a managed identity under RBAC; no shared key, no connection secret, no password. The
trigger payload carries nothing authority-bearing. The notification authorizes nothing. The monolith's
database principal cannot reach a base table. No sample flow touches a model, the retrieval index or
the cache.

**Testing.** Integration across both deployables; messaging and idempotency (duplicate delivery →
exactly one effect); tenant isolation across the asynchronous hop; correlation continuity; contract
tests against the emitted OpenAPI documents; a negative suite for the gateway bypass.

**Validation gates.**

1. All three flows complete when driven through the deployed edge, and 0 are accepted on a
   direct-to-deployable or locally hosted run (`SC-DEMO-001`).
2. An induced failure between the state change and the outbox write loses 0 messages and duplicates
   0 effects (`SC-DEMO-008`).
3. The same bus message delivered twice produces exactly 1 effect (`SC-DEMO-009`).
4. The flow reaches the same outcome with no client connected, and the notification carries no
   authority (`SC-DEMO-010`).
5. One correlation identifier is recoverable across every tier and the asynchronous hop
   (`SC-DEMO-005`).
6. A request scoped to one organisation returns 0 rows belonging to another, including after the
   asynchronous hop (`SC-DEMO-006`).
7. A direct-to-deployable request carrying **no** identity contract fails across every audience.
   (`SC-DEMO-003b` — the self-supplied-contract case — is **deferred**; see *Deferred* below. It is
   not a gate of this stage and must not be signed off as one.)
8. The emitted OpenAPI documents for all three audiences match what the services accept, with 0
   hand-maintained divergences (`SC-DEMO-011`).
9. A repository scan finds 0 committed secrets and 0 credential-bearing connection strings
   (`SC-DEMO-004`).

**Non-goals.** No approval, no consent, no approval or consent UI, no real endpoint execution, no
desktop script execution, no use case. No model call, no retrieval query, no cache read — those are
product behaviour and this stage is about the platform beneath it.

---

### Stages 15–17 — The Integrations Service *(added 2026-09-18)*

**These three run after Stage 13 and before Stage 14**, despite their numbers. Stage numbers are
append-only and never reused, so ordering is stated rather than inferred from the integer.

---

### Stage 15 — Integrations Service foundation

**Objective.** A third deployable that starts, is reachable only through APIM, proves its own identity
and configuration, and emits its own contract — carrying **no connector yet**.

**Architectural boundaries.** The tree in §Project Structure. `api → application → domain`; `domain`
imports nothing outside the standard library; no module outside `config/composition.py` instantiates a
concrete adapter. **No import of `ragcore` in either direction, and no shared library between them.**

**Components.** `integrations/src/integrations/{api,application,domain,config,observability,egress,
persistence}/`; `integrations/tests/`; `build/docker/integrations.Dockerfile`;
`build/docker/containerapps/integrations.yaml`; a new APIM backend and API entry in
`build/infra/apim/apis.json`; a new identity in `build/infra/identity/managed-identities.json`;
`.github/workflows/` pipeline.

**Dependencies.** Stages 1–2 (tooling, boundary checks), 7 (PostgreSQL), 10 (observability and
container baseline). Independent of Stages 3–6 and 8.

**Contracts.** `/api/workload/v1/integrations/...` on the **workload audience**, app-only, with its own
application role, reached by the longest-matching-path rule `apis.json` already proves with `/views`.
Emits `build/contracts/integrations/workload.v1.openapi.json` from the running service, through the
same five gates: generation, determinism, publishability, compatibility, freshness.

**Engineering baseline — identical to RagCore's, independently implemented.** Typed Pydantic Settings
with `ValidateOnStart`-equivalent startup validation that fails the process rather than degrading;
structured logging with constant message templates; OpenTelemetry traces and metrics; W3C Trace
Context correlation accepted, generated when absent, echoed and bound to the logging scope; RFC 9457
`application/problem+json` with `correlationId` on every error; `/health/live` process-only and
`/health/ready` covering database, message transport and Key Vault — **never an external customer
system**, whose outage is an operational condition rather than an unready service; managed identity to
every Azure resource; Key Vault by reference at the point of use; typed HTTP clients with a shared
resilience policy and an **explicit timeout on every outbound call**; no secret in any log, span or
error body.

**Security.** The service **MUST NOT parse a token** and consumes only the closed header contract. It
MUST NOT trust an identity header a caller supplied. **No gateway-provenance layer runs before
identity** — that control is deferred (see *Deferred* below), and none may be added in its place. Its managed identity holds the Key Vault role for connector secrets; the
same role is **removed from RagCore** in this stage, not in Stage 16 — the removal is what makes
`FR-DEMO-026` provable, and doing it early means nothing can quietly depend on it.

**Testing.** Configuration validation; health and readiness; contract emission and its five gates;
architecture dependency — `integrations ↛ ragcore`, `ragcore ↛ integrations` as an import,
`domain` purity, composition-root exclusivity; security — no token parsing, no secret in logs, and
**no backend credential on the APIM hop**.

**Validation gates.** The service starts, fails fast on invalid configuration, answers both health
endpoints, is reachable through APIM and **not** by any direct address, and emits a contract that
passes all five gates. `build/scripts/check-boundaries.sh` understands three deployables.

**Non-goals.** No connector. No execution. No message consumption.

---

### Stage 16 — Connector migration out of RagCore

**Objective.** Move every external-system path out of RagCore and into the Integrations Service, and
**prove RagCore can no longer reach one**.

**Architectural boundaries.** Ports move with their consumers (constitution Principle V). The MCP
discover/invoke type separation and the single credential path survive the move intact — they are the
enforcement mechanisms, not conveniences.

**Moves substantially unchanged** — already ports-and-adapters, same language, same baseline:

| From RagCore | To Integrations |
|---|---|
| `integrations/servicenow/`, `integrations/graph/`, `integrations/onelogin/`, `integrations/duo/` | `connectors/` |
| `integrations/mcp/client.py` | `mcp/` |
| `integrations/credentials.py` (**with its port declaration**) | `credentials/` |
| `integrations/http.py`, `integrations/validation.py` | `egress/` |
| `execution/idempotency.py`, `execution/availability.py` | `execution/` |

**Refactored.** `execution/executor.py` splits — invocation and verification move; the conclusion
(`may_report_resolution`) **stays in RagCore**. `application/ports.py` — the tool, case, directory and
discovery ports become *remote* on the RagCore side and *implemented* on the Integrations side.
`graph/nodes/execution.py` becomes dispatch-and-suspend. `application/cases.py` and
`application/escalation.py` route ServiceNow writes through the new service.

**Redesigned.** The gate outcome cannot cross a process boundary as an asserted value and is
**re-derived** from durable state (`FR-INTEG-019`) — a serialised `PROCEED` is a model-free but still
*asserted* authority, which Principle I forbids. The connector registry is new. Queue-and-replay on
system-of-record outage moves with its durability story.

**Stays in RagCore, deliberately.** `model/` — the AI Gateway client, model egress and
content safety. That is reasoning, not integration, and the Integrations Service has no model access.

**Removed from RagCore.** The `integrations/` package except `model/`; the connector settings and
secret references in `config/`; the Key Vault role (already withdrawn in Stage 15); every
connector-related dependency in `pyproject.toml` and `uv.lock`.

**Dependencies.** Stage 15. Touches Stages 6, 9 and 12 as built.

**Schema.** `integration_job` in `platform` with its **column-scoped grants** — the first migration and
the one to review as DDL rather than prose; the `integration` schema and its tables; a published view
exposing the operation instruction; the Integrations database principal, readable on `vw_*` and on no
base table. **One Alembic project, one gated job.**

**Testing.** Every relocated adapter's tests move with it. New: architecture test asserting **no
adapter, connector or provider client remains in RagCore**; migration tests for the new grants,
asserting the refusal comes from PostgreSQL rather than application code; tenant isolation for the
third database principal.

**Validation gates.** RagCore contains no connector code and holds no connector credential. Every
relocated adapter passes its own suite in its new home. The column-scoped grant refuses a write to a
non-result column.

**Non-goals.** No behaviour change to any adapter. No new connector.

---

### Stage 17 — Golden path C: the Integrations boundary proven

**Objective.** Prove the boundary rather than describe it — spec `FR-DEMO-020` through `FR-DEMO-028`,
measured by `SC-DEMO-015` through `SC-DEMO-023`.

**Acceptance flows.** Each is driven through the **real deployed path** (`FR-DEMO-019`) and acts only
on the inert reference connector.

| Flow | Proves |
|---|---|
| Bypass attempt from RagCore | The direct connection fails at the network layer; the credential resolution fails at Key Vault; no connector code remains — `SC-DEMO-015` |
| Synchronous catalogue read through APIM | Gateway-routed, app-only; a call by any other route fails, **including one carrying a well-formed but self-supplied identity contract** — `SC-DEMO-016` |
| Synchronous inert system-of-record operation | The same path, the same fixture |
| Asynchronous execution | Command and result over their own queues, carrying only `jobId`, correlation and kind — `SC-DEMO-017` |
| Duplicate delivery, **twice, separately** | The claim absorbs a duplicate resume trigger; the derived key absorbs a redelivered command. **Each proof fails when its own boundary alone is removed** — `SC-DEMO-018` |
| Out-of-contract organisation field | Refused and dead-lettered; and separately, a conflicting assertion still binds to the durable organisation — `SC-DEMO-019` |
| Connector secret reachability | RagCore resolves zero; no secret in its source, configuration, environment or image — `SC-DEMO-020` |
| Result correlation | Matched to the originating work item; one identifier across the gateway hop, both queues and all three deployables — `SC-DEMO-021` |
| Independent observability | Distinct telemetry source, connector metrics, execution records queryable without RagCore — `SC-DEMO-022` |
| Integrations stopped | Conversation, retrieval and guidance continue; effect-requiring capabilities fall back visibly — `SC-DEMO-023` |

**Dependencies.** Stages 15–16, and a deployed environment.

**Infrastructure.** Two new Service Bus queues with their own role assignments — RagCore sends on
commands and listens on results; Integrations listens on commands and sends on results, **and nothing
more**. Integrations runs its **own transactional outbox** for result publication.

**Testing.** Integration and end-to-end across three deployables; idempotency and concurrency at both
boundaries; security — every prohibition in the dependency graph shown unreachable. **The direct-path
refusal proof (`FR-DEMO-004a`, `SC-DEMO-003a`) is extended to the third deployable and is the single
most important test in this stage**, because the new RagCore → Integrations edge is exactly the shape
a bypass takes. Its `SC-DEMO-003b` half — the self-supplied contract — is **deferred** and is not
extended, because there is no longer a control for it to exercise (see *Deferred* below).

**Validation gates.** All ten flows pass against a deployed environment. A gate nobody has seen fail is
a gate whose failure mode is silence: `build/scripts/verify-*-guard.sh` plants each violation class and
asserts the guards reject it.

**Non-goals.** No real external system. No use-case behaviour.

---

### Stage 14 — Use cases UC-01 through UC-12 *(gated)*

**Objective.** Implement the twelve product use cases.

**Entry gate.** **Stages 12, 13, 15, 16 and 17 must all be validated first.** Until then this stage
MUST NOT begin, and UC-01–UC-12 remain labelled placeholders.

*Gate widened 2026-09-18.* Every use case executes through the Integrations Service, so building one
before the boundary is proven would build it against a path that is about to move — and the first
thing a use case would do is re-establish the direct external access ADR-0007 removes.

**Dependencies.** Stages 12–13 and 15–17, plus the product definitions, which do not yet exist.

**Non-goals for this plan.** The use cases are **not designed here**. No behaviour, catalogue entry or
task for any of them is invented. Each will need its own specification pass.

**Blocked on.** Product definitions for UC-01–UC-12; and, before any use case touches the desktop path,
the endpoint-execution open items in ADR-0004 — script signing and the destructive taxonomy.

## Deferred from Active Implementation

**Deferred is not "not done yet".** Everything in this section was removed from the active
architecture by an explicit decision. None of it is a scaffold gap, none of it should appear on a
backlog, and none of it may be picked up as leftover work — each entry names the decision that must
be revisited first.

### Certificate-based gateway-to-backend provenance

**Decision:** [ADR-0008 — Defer certificate-based gateway-to-backend provenance](../../docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md).
**Status:** Deferred, with **no replacement mechanism of any kind**.

The APIM-to-backend hop was to carry a second, application-level control alongside its network one:
APIM presenting a client certificate, Container Apps ingress requiring and validating it, and each
backend refusing any request whose forwarded certificate hash was not allow-listed. It is removed in
full from this plan.

**No longer part of any stage, prerequisite, gate or provisioning step:**

| Removed from | What was there |
|---|---|
| Architecture and security controls | APIM client certificate; ingress `clientCertificateMode: require`; the forwarded certificate header; backend hash validation and its refusal middleware |
| Azure prerequisites | Issuing the gateway client certificate into Key Vault; registering the APIM certificate entity; the APIM identity's Key Vault role assignment |
| Deployment requirements | `EdgeTrust__GatewayCertificateThumbprints`, `SYNTHIA_EDGE_GATEWAY_CERTIFICATE_THUMBPRINTS`, `SYNTHIA_INTEGRATIONS_EDGE_TRUST__GATEWAY_CERTIFICATE_THUMBPRINTS` |
| Monitoring requirements | Certificate near-expiry and expiry alerting, and the action group they paged |
| Operational procedures | The order-sensitive certificate rotation runbook |
| Acceptance criteria | `SC-DEMO-003b`; the certificate half of `SC-DEMO-003`; `FR-IDENT-012` |

**What this does *not* relax.** Backends remain internal-only with no public FQDN and external
ingress remains prohibited and guarded. APIM remains the API trust boundary and still deletes every
inbound copy of the `X-Idp-*` contract. Managed identity, Azure RBAC, Key Vault, tenant isolation,
authorization, correlation, audit and every other control stand unchanged.

**The consequence this plan must not obscure.** The hop now rests on network placement alone, which
`FR-IDENT-012` states is not sufficient proof. A caller inside the environment can present a forged
identity contract to a backend and be believed. `FR-IDENT-012` and `SC-DEMO-003b` are marked
**DEFERRED** in `spec.md` for that reason rather than quietly left as unmet active requirements.

**Re-entry.** Requires the architecture and security decision in ADR-0008 to be revisited and
explicitly approved, and that ADR superseded. Until then, a change introducing a backend credential,
an ingress client-certificate requirement, a provenance middleware or a trusted header on this hop is
out of scope by construction.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| 11 .NET projects for a read-only API (6 modules + host + 4 shared) | Principle V requires module boundaries "enforced by architecture tests, not convention". Separate projects make a breach a compile error. | Namespace-only boundaries are advisory; the required architecture tests would reduce to reflection over naming — the convention the constitution rules out. |
| 3 Angular apps + 4 libraries | Three surfaces are required and the desktop renderer must reuse customer UI rather than reimplement it. | One app with runtime surface switching would ship staff code to customer clients and make the staff-portal no-chat rule a runtime flag rather than a build-time fact. |
| A model port before a second provider exists | Principle VI forbids provider-neutral abstraction before a second provider — but §13.5 *mandates* provider routing at the AI Gateway, so a second provider is architecturally assumed. | A direct provider client was rejected: no metering point, no budget enforcement, and provider coupling spread across every call site. |
| Separate worker processes inside the RagCore deployable | The approval API must return before execution runs; claim, expiry sweep, outbox dispatch and dead-lettering cannot live in a request handler. | Resuming inside the request would hold the approver's HTTP call open and forfeit retry, expiry and dead-lettering. |
| **A third deployable, and gateway hops restored to the tool path** | ADR-0007. RagCore processes untrusted model output, retrieved content and chat text; co-locating every organisation's connector credentials with it makes an orchestrator compromise a credential breach for every customer system. Principle V permits the split only by explicit ADR, which exists. | Keeping integrations inside RagCore was rejected: it leaves the most damaging half of OQ-02 unaddressed. Splitting RagCore into user-facing and execution runtimes was rejected as insufficient — it separates the *platform* credential classes but leaves connector credentials wherever the adapters live. Three separate services, one per integration context, was rejected as the premature decomposition Principle V names as a defect. |
| **Two Python projects duplicating correlation, problem-details, settings and telemetry setup** | Principle VI: DRY applies *within* a boundary, and duplication across boundaries is cheaper than a false shared contract. | A shared library was rejected because it would be a build-level dependency between two deployables required to have none — the coupling would not appear as a cross-tree path and `check-boundaries` could not catch it. |

## Phase Status

- [x] Phase 0 — research complete → [research.md](./research.md)
- [x] Phase 1 — design complete → [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
- [x] Constitution re-check after Phase 1 — v3.1.0, no new violations. The 3.0.0 to 3.1.0 amendment is additive (test-category mapping, coverage position); no principle changed and no stage is affected
- [x] Scaffold scope correction applied 2026-09-16 — Summary, Platform Environment and Access (new),
  Stage 10 sequencing, Stage 12 gates, Stage 13 replaced. Architecture unchanged; no infrastructure
  added; no bounded context or deployable boundary moved
- [x] Integrations Service boundary applied 2026-09-18 — Summary, Technical Context, Platform
  Environment, OpenAPI emission, Project Structure, Dependency direction, Context placement,
  Composition roots, Structure Decision, Divergences, Stage 9 (superseded in placement), Stage 14
  gate, Stages 15–17 (new), Complexity Tracking. Architecture unchanged from
  `Synthia-Platform-Specification.md` §21.6 and ADR-0007; **this plan follows them and decides
  nothing architectural of its own**
- [ ] Phase 2 — task breakdown (`/speckit-tasks`), to be re-run against the **seventeen** stages.
  **Stale on two counts**: Phase 13 tasks still describe the approval and consent golden path and no
  tasks exist for the three Stage 13 sample flows or the OpenAPI emission requirements; and
  T128–T138 place every adapter under `ragcore/src/ragcore/integrations/`, which Stage 16 moves.
  Those tasks are marked `[X]` and need an explicit disposition — completed-then-relocated, not
  reopened — rather than silent rewriting

## Open items this plan does not close

Carried from ADR-0007 §Unresolved. Neither blocks Stage 15; both block parts of Stages 16–17.

| Item | Blocks | Met at |
|---|---|---|
| **Which system-of-record operations are synchronous.** §22.3 lists six write classes and classifies all of them `AUTO`; §22.5 makes only case creation clearly blocking | The Integrations contract surface, and therefore contract freeze | Stage 15, before the contract is frozen |
| **The job row's result columns and the `GRANT` expressing their column scope** | `FR-INTEG-020`, `FR-DEMO-025` — the protection is enforced at the database permission boundary, so it is provable only once the DDL exists | Stage 16, first migration |
| **OQ-06 — the latency re-baseline.** Stages 15–17 restore gateway hops to the tool path that ADR-0001 removed | Nothing. No performance figure is an acceptance criterion | After Stage 17, measured |
| **How gateway-to-backend provenance is proved.** Deferred with no replacement by ADR-0008; the hop rests on network placement alone, which `FR-IDENT-012` states is insufficient | `FR-IDENT-012`, `SC-DEMO-003b` — both marked DEFERRED rather than met | Before the platform carries production customer data |
