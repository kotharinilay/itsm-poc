# Implementation Plan: Synthia Platform Engineering Scaffold

**Branch**: `001-platform-scaffold` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-platform-scaffold/spec.md`

**Constitution**: v3.1.0 | **Architecture source of truth**: `Synthia-Platform-Specification.md`

## Summary

Build a monorepo containing five applications across two deployables, proving every load-bearing
behaviour of the platform end to end while containing no product use cases.

This revision **reconciles the plan with constitution v3.1.0**. The architecture is unchanged — it
remains the one fixed by `Synthia-Platform-Specification.md` and
[ADR-0001](../../docs/adr/0001-ragcore-owns-orchestration-dotnet-owns-read.md). What changed is the
engineering contract the build must satisfy: transactional outbox, optimistic concurrency, resilience
policy, startup configuration validation, container hardening, the twelfth bounded context
(`Ingestion`), and fifteen required test categories.

**RagCore** (Python 3.12, LangGraph) owns orchestration, execution and all state-changing operations.
The **.NET 10 modular monolith** is read-only. There is no application-level dependency between them;
they meet only at PostgreSQL and asynchronous messaging. Three client surfaces come from one Angular
workspace, with Electron as a thin host that decides nothing.

Work is organised into **fourteen ordered stages**: eleven scaffold stages containing no product
behaviour, two architectural golden paths that prove the governance machine end to end — between them
exercising all four execution treatments — and only then the twelve use cases.

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
audit. Azure AI Search is a **derived** retrieval index. Redis is **transient only**. Key Vault is the
sole source of secret material.

**Model layer**: Azure OpenAI and Foundry for reasoning and embeddings, on private endpoints, reached
**only** through the **AI Gateway** — provider routing, provider-normalised token metering,
per-organisation budgets and throttles, semantic cache, bidirectional content safety. A policy
function, **not an identity boundary**.

**Testing**: .NET — xUnit, NetArchTest, Testcontainers, `WebApplicationFactory`. Python — pytest,
pytest-asyncio, pytest-alembic, Testcontainers. Web — the project-supported Angular runner plus
Playwright and axe-core.

**Target Platform**: Azure Container Apps (internal environment) behind Front Door + WAF and APIM;
Electron desktop on customer-managed Windows endpoints.

**Project Type**: Multi-application monorepo — two backend deployables, three client surfaces.

**Performance Goals**: **None committed.** Constitution Section 2 and spec `PT-001`–`PT-003` make every
performance figure good-to-have; no release is gated on one.

**Constraints**: Per-organisation budgets and rate limits are enforced **at the AI Gateway and APIM**,
not in application code. English only, no localization infrastructure (`FR-SURF-014`). Single region,
no residency support (`FR-SURF-015`). WCAG 2.2 AA on all three surfaces. Invariant globalization in
.NET containers — see [research.md](./research.md) R-011.

**Scale/Scope**: No scale envelope defined — recorded as Outstanding. Design for linear horizontal
scale on stateless compute; revisit when use cases arrive.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design. Constitution v3.1.0.*

| # | Principle | How the design satisfies it | Status |
|---|---|---|---|
| I | Identity derived once; authority never asserted | Identity derived at APIM only; both deployables consume the closed header contract and neither parses a token. No endpoint accepts tenant, role or audience. Tenant admission is trusted identity plus registry state. | **PASS** |
| II | Authorization separate and non-hierarchical | Set-intersection helper in both stacks, with no ordering or comparison operator defined on roles. `Synthia_Agents → technician`, `Synthia_Admins → administrator`. **`senior_technician` is implemented as a defined role that no operation accepts** — see below. Customer surfaces apply no role check; the staff portal has no session-origination route. | **PASS** |
| III | Deterministic governance decides; model proposes | Governance is a distinct RagCore package. The agent loop reaches `read` tools only; every `action` passes the gate. Discovery never grants entitlement. Approval binds approver, tenant, work item, operation, target, version, expiry and audit. | **PASS** |
| IV | Isolation absolute; one authority per concern | Tenant filter in repository and retrieval layers with no unfiltered path. PostgreSQL authoritative; ServiceNow the case system of record; AI Search derived; Redis transient; exactly one checkpoint store. | **PASS** |
| V | Modular boundaries mandatory | Twelve logical contexts preserved as modules and packages — none collapsed, none promoted to a service without an ADR. Dependency points inward; ports declared by consumers; adapters in infrastructure. | **PASS** |
| VI | Design for change without speculation | Constructor injection only; no Service Locator; no `BuildServiceProvider` during configuration. No provider-neutral abstraction before a second provider — the model port is the one exception and is justified below. | **PASS (one justified)** |
| VII | No client is a security boundary | Angular role checks presentation-only; Electron `contextIsolation` on, `nodeIntegration` off, sandbox on, narrow typed bridge, every IPC sender and argument validated, navigation allow-listed. | **PASS** |
| VIII | Provable by audit and by test | Correlation from the edge through every tier on W3C Trace Context. Full actor chain on every consequential action. All fifteen test categories appear in the stage plan. | **PASS** |
| IX | Scaffold honestly | UC-01–UC-12 are labelled placeholders. Four inert reference operations, production-excluded. Use cases are Stage 14, gated behind both golden paths. | **PASS** |
| X | Decisions recorded | ADR-0001–0005 govern this plan; divergences are listed below rather than left implicit. | **PASS** |

**Result**: no unjustified violations. One justified exception and three complexities, recorded below.

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
│   ├── docker/                          # Dockerfiles for both deployables
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
└── README.md
```

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
            retrieval | integrations | messaging | notifications | persistence
                                        → implement ports declared in application
            domain imports NOTHING outside the standard library

MODELS      ragcore → AI Gateway → model provider   (no direct provider access)

ACROSS      dotnet ↛ ragcore    and    ragcore ↛ dotnet
            They meet only at PostgreSQL (versioned views) and Service Bus (opaque triggers).
```

### Where each bounded context lives

A context is **not** assigned to one deployable. It is assigned a write side and, where it has one, a
read model — and the two sit on opposite sides of the published-view contract. This is CQRS, and it
falls out of ADR-0001 rather than being chosen separately: RagCore owns every state change, the
monolith reads. **A context appearing on both sides is the intended shape, not a boundary breach.**

| Context | Write side — RagCore | Read model — monolith |
|---|---|---|
| Session | `application/sessions.py`, `api/customer/` | `Modules/Synthia.Modules.Sessions` |
| Work | `execution/`, `application/` | `Modules/Synthia.Modules.Work` |
| Governance | `governance/` | `Modules/Synthia.Modules.Governance` |
| Approval | `application/approvals.py`, `api/staff/`, `api/customer/consent.py` | `Modules/Synthia.Modules.Approvals` |
| Audit | `application/audit.py` | `Modules/Synthia.Modules.Audit` |
| Tenant & Configuration | `config/`, `persistence/` | `Modules/Synthia.Modules.Tenancy` |
| Agent / RagCore | `graph/` | — none. Working state is never published |
| Retrieval | `retrieval/` | — none |
| Tool Execution | `execution/`, `integrations/mcp/` | — none |
| Integration — ServiceNow | `integrations/servicenow/` | — none |
| Integration — Microsoft Graph | `integrations/graph/` | — none |
| Ingestion | `ingestion/`, `workers/ingestion_run.py` | — none |

**The rule that makes this checkable.** A context's write side is exactly one RagCore package; its read
model is at most one monolith module; the two communicate **only** through a `vw_*_v1` view and never
by call, reference or shared type. Six contexts have no read model because nothing outside RagCore
needs to read them — and adding one to any of those six means adding a published view, which is a
contract change under `contracts/read-views.md`, not an implementation detail.

### Composition roots

One per deployable, named, and the only place registration happens. A dependency constructed anywhere
else is a defect in all four.

| Deployable | Composition root | Enforced by |
|---|---|---|
| .NET monolith | `Synthia.Api/Program.cs` | T035 — no Service Locator, no `BuildServiceProvider` during configuration |
| RagCore | `ragcore/src/ragcore/config/composition.py` — builds every adapter and binds it to the port it implements; FastAPI `Depends` resolves from it and constructs nothing itself | Import-boundary test: no module outside it instantiates a concrete adapter |
| Angular workspace | `platform-core` providers, wired at each app's `bootstrapApplication` | ESLint library-boundary rules (T011) |
| Electron host | `apps/desktop/src/main/index.ts` | The renderer receives only the `contextBridge` surface (T051) |

**Structure Decision**: four top-level source trees — `apps/web`, `apps/desktop`, `dotnet`, `ragcore`.
One Angular workspace so the customer feature libraries are genuinely shared rather than duplicated.
The two backend trees are siblings with no build-level relationship, which makes the no-dependency rule
structural: a reference cannot be added without appearing in a diff as a new cross-tree path, and
`build/scripts/check-boundaries` fails CI if one does.

## Divergences from the Authoritative Specification

`Synthia-Platform-Specification.md` is authoritative on architecture. This plan departs from it in four
recorded places, listed here so a plan reader sees them without having to find the constitution's
change log.

| # | Authoritative position | This plan | Recorded in | Status |
|---|---|---|---|---|
| 1 | §14.1 defines eleven independently addressable bounded contexts | Two application deployables; each context's **write side** becomes a RagCore package and its **read model**, where it has one, a monolith module — see the placement rule below | ADR-0001 | Accepted |
| 2 | §31.4 shows a synchronous chain `Session → RagCore → Retrieval → Governance → Tool Execution` | RagCore owns that chain internally with no gateway hops between stages; the monolith is read-only | ADR-0001 | Accepted |
| 3 | §37.1 defers the customer web portal beyond the initial release | Included as a scaffolded Angular application with no product behaviour | Constitution divergence register | Accepted |
| 4 | OneLogin and Duo appear nowhere in the specification | Sanctioned third-party target systems reached as MCP servers; an open set | ADR-0005 | Accepted |

**Nothing else diverges.** The twelve bounded contexts are preserved as responsibilities — none added,
none removed. Every piece of infrastructure appears in §9.3. §13.4's no-direct-service-to-service rule
holds between the two deployables. If any of the four is withdrawn, this plan must be revised before
implementation continues.

### Recorded conflict, not resolved here

The constitution states the general rule that **EF migrations run in CI and deployment using migration
bundles**. ADR-0001 and ADR-0003 make the .NET monolith read-only with no schema ownership, so that
rule has **no current application**: Alembic owns every migration and the monolith reads versioned
views. Soft-delete, global query filters and audit columns are therefore schema rules owned by
RagCore's migrations, which the published views must respect. **If .NET is intended to own schema,
ADR-0001 and ADR-0003 must be amended before Stage 7.** This plan does not decide that.

## Implementation Stages

Fourteen ordered stages. Stages 1–11 are **scaffolding only** and contain no product behaviour.
Stages 12–13 prove the two architectural golden paths. Stage 14 is gated behind both.

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
between the two deployables.

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
`integrations/model/`. No `HttpClient` is constructed manually.

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

**Infrastructure.** Application Insights / Azure Monitor; Azure Container Apps.

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
proposal, and recorded as a denial. A planted injection in retrieved content produces at most a
proposal, never an execution. A near-tie and a confident singleton at the same top score route
differently. A score exactly equal to the absolute threshold, and a margin exactly equal to the margin
threshold, both pass — asserted directly rather than inferred.

**Non-goals.** No approval, no consent, no desktop execution, no use case.

---

### Stage 13 — Golden path B: governed human decision (`STAFF_APPROVAL` and `END_USER_APPROVAL`)

**Objective.** Prove the hardest guarantee: durable suspension, an authenticated human decision, and
execution that survives the requester's absence.

Both human-decided treatments run on **one machine** — suspend → verdict → outbox → trigger → resume →
atomic claim → execute — differing only in **who may decide** (a `technician` versus the work's own
requester) and **on which surface** (staff portal versus customer). Proving them together is what makes
`SC-SCOPE-002` reachable without a third path, and it directly tests constitution Principle II's rule
that the two authorization models never decide for one another.

**Architectural boundaries.** Adds Approval and the resume path, for both the staff verdict and the
end-user consent decision.

**Components.** The approval and consent APIs in RagCore; the approval and consent interrupt nodes;
outbox → trigger → resume worker; atomic claim; Workload execution; the Mission Control queue read
model; the in-conversation consent prompt.

**Dependencies.** Stage 12.

**Contracts.** Staff API verdict; the trigger contract; the notification envelope; the fifteen-minute
window.

**Infrastructure.** As Stage 12, plus Service Bus on the critical path.

**Security.** Approval binds approver, tenant, work item, operation, target, version, expiry and audit.
`technician` may approve; `administrator` may not. The verdict enters only through the authenticated
API — never the realtime channel. **Approval records authority; it never executes.** Consent is given
only by the work item's own requester, only through the authenticated consent endpoint, and **an
affirmative chat message is never consent**. Consent never satisfies a `STAFF_APPROVAL` requirement.

**Testing.** Approval; consent; checkpoint/resume; concurrency; idempotency; the authorization matrix;
end-to-end golden path with the client closed, and a second end-to-end run proving an affirmative chat
message confers nothing while the explicit consent action resumes the work.

**Validation gates.** With the customer client **entirely closed**, an approved operation resumes and
completes. The `END_USER_APPROVAL` reference operation suspends at consent, ignores an affirmative chat
message, and resumes only on the explicit authenticated action; consent from anyone but the requester is
rejected. Expiry without execution is not an error and surfaces as approved-but-not-executed. A failed
action does not re-fire. **All four execution treatments are now demonstrable (`SC-SCOPE-002`).**

**Non-goals.** No desktop script, no use case.

---

### Stage 14 — Use cases UC-01 through UC-12 *(gated)*

**Objective.** Implement the twelve product use cases.

**Entry gate.** **Stages 12 and 13 must both be validated first.** Until then this stage MUST NOT begin,
and UC-01–UC-12 remain labelled placeholders.

**Dependencies.** Stages 12–13, plus the product definitions, which do not yet exist.

**Non-goals for this plan.** The use cases are **not designed here**. No behaviour, catalogue entry or
task for any of them is invented. Each will need its own specification pass.

**Blocked on.** Product definitions for UC-01–UC-12; and, before any use case touches the desktop path,
the endpoint-execution open items in ADR-0004 — script signing and the destructive taxonomy.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| 11 .NET projects for a read-only API (6 modules + host + 4 shared) | Principle V requires module boundaries "enforced by architecture tests, not convention". Separate projects make a breach a compile error. | Namespace-only boundaries are advisory; the required architecture tests would reduce to reflection over naming — the convention the constitution rules out. |
| 3 Angular apps + 4 libraries | Three surfaces are required and the desktop renderer must reuse customer UI rather than reimplement it. | One app with runtime surface switching would ship staff code to customer clients and make the staff-portal no-chat rule a runtime flag rather than a build-time fact. |
| A model port before a second provider exists | Principle VI forbids provider-neutral abstraction before a second provider — but §13.5 *mandates* provider routing at the AI Gateway, so a second provider is architecturally assumed. | A direct provider client was rejected: no metering point, no budget enforcement, and provider coupling spread across every call site. |
| Separate worker processes inside the RagCore deployable | The approval API must return before execution runs; claim, expiry sweep, outbox dispatch and dead-lettering cannot live in a request handler. | Resuming inside the request would hold the approver's HTTP call open and forfeit retry, expiry and dead-lettering. |

## Phase Status

- [x] Phase 0 — research complete → [research.md](./research.md)
- [x] Phase 1 — design complete → [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
- [x] Constitution re-check after Phase 1 — v3.1.0, no new violations. The 3.0.0 to 3.1.0 amendment is additive (test-category mapping, coverage position); no principle changed and no stage is affected
- [ ] Phase 2 — task breakdown (`/speckit-tasks`), to be re-run against the fourteen stages
