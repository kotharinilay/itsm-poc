# Tasks: Synthia Platform Engineering Scaffold

**Input**: Design documents from `/specs/001-platform-scaffold/`

**Prerequisites**: [plan.md](./plan.md) (17 stages), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), constitution v3.2.0

**Tests**: REQUIRED. The constitution mandates fifteen test categories and makes them a merge gate.

**Organization**: Phases mirror the plan's stages, in dependency order. **Phases 1–11 are scaffold** and
carry no story label — they are setup and foundational work. **Phases 12–13 are the two architectural
golden paths** and carry story labels. Phase 12 proves the synchronous governed machine (`AUTO` and
`NOT_ALLOWED`); **Phase 13 proves asynchronous platform integration** through the three inert sample
flows in [contracts/sample-flows.md](./contracts/sample-flows.md). The twelve business use cases are
**not here**; they are Stage 14, gated behind both golden paths.

**Revised 2026-09-16 — scaffold scope correction.** Phases 1–6 are complete and untouched. The
approval and consent workflow tasks that formed the old Phase 13 are **withdrawn from the scaffold, not
from the platform** (spec `FR-DEMO-016`, `FR-DEMO-017`); their IDs are permanently retired and listed
under *Withdrawn 2026-09-16*. No completed task was reopened. The four execution treatments remain
catalogue data and are classified deterministically in Phase 12; two of the four are no longer
*exercised*, and `FR-DEMO-018` makes the unexercised gate **fail closed** rather than permit by
default.

**Revised 2026-09-18 — the Integrations Service boundary.** `Synthia-Platform-Specification.md` §21.6
and [ADR-0007](../../docs/adr/0007-integration-service-boundary.md) make Integrations a **separately
deployed Python service parallel to RagCore**. Three phases are added — **15 (foundation), 16
(connector migration), 17 (golden path C)** — and they run **after Phase 13 and before Phase 14**.
Phase and task numbers are append-only and never reused, so ordering is stated rather than inferred
from the integer.

**No completed task was reopened and no task ID was reused.** Phase 9 is *relocated, not retired*: its
tasks stay `[X]` because they were done and the code they produced is being moved rather than rebuilt.
The old→new traceability is in *Relocated 2026-09-18*. Six of its tasks do **not** move — model egress
is reasoning, not integration.

## Format: `[ID] [P?] [Story] Description — Boundary: … | Validates: …`

- **[P]**: parallelizable — different files, no incomplete dependency
- **[Story]**: US1–US6 from spec.md, on golden-path phases only. **US6** is *The platform proves its
  own plumbing before it carries any product* — the scaffold's own acceptance story
- **Boundary**: the architectural boundary the task sits on or guards
- **Validates**: the requirement, principle or gate the task must satisfy

## Path Conventions

Per plan.md: `apps/web/`, `apps/desktop/`, `dotnet/`, `ragcore/`, `build/`, `docs/`.

---

## Phase 1: Repository and tooling foundation *(Stage 1)*

**Goal**: A monorepo skeleton with both toolchains, CI and boundary enforcement. Nothing runs yet.

- [X] T001 Create the monorepo skeleton per plan.md in the repository root: `apps/web/`, `apps/desktop/`, `dotnet/`, `ragcore/`, `build/{docker,infra/ai-gateway,scripts}/` — Boundary: repository | Validates: Plan §Project Structure
- [X] T002 [P] Write root `README.md` describing the two deployables and the no-dependency rule — Boundary: repository | Validates: Constitution P-X
- [X] T003 [P] Create `docs/adr/README.md` indexing ADR-0001 through ADR-0005 with status — Boundary: documentation | Validates: Constitution P-X
- [X] T004 [P] Create `dotnet/Directory.Build.props` with `Nullable=enable`, `TreatWarningsAsErrors=true`, `EnableNETAnalyzers=true`, `AnalysisLevel=latest-Recommended`, `EnforceCodeStyleInBuild=true`, `Deterministic=true`, `InvariantGlobalization=true` — Boundary: .NET build | Validates: Constitution §.NET baseline
- [X] T005 [P] Create `dotnet/Directory.Packages.props` with `ManagePackageVersionsCentrally=true`, pinning EF Core 10, Npgsql, OpenTelemetry, `Http.Resilience`, xUnit, NetArchTest, Testcontainers — Boundary: .NET build | Validates: Constitution §.NET baseline
- [X] T006 [P] Create `dotnet/.editorconfig` setting IDE0055 and IDE1006 to `error` — Boundary: .NET build | Validates: Constitution §.NET baseline
- [X] T007 Create `dotnet/Synthia.sln` with stubs for the 11 projects in plan.md — Boundary: .NET solution | Validates: Plan §Complexity Tracking
- [X] T008 [P] Create `ragcore/pyproject.toml` (PEP 621) with `requires-python >=3.12`, ruff select `["E","F","B","I","UP","S","PTH","SIM","ASYNC","DTZ","N"]`, ruff format authoritative, `[tool.mypy] strict = true` — Boundary: Python build | Validates: Constitution §Python baseline
- [X] T009 [P] Generate and commit `ragcore/uv.lock` pinning FastAPI, Pydantic, Pydantic Settings, LangGraph, langgraph-checkpoint-postgres, SQLAlchemy, asyncpg, Alembic, alembic_utils, azure-servicebus, azure-identity, httpx — Boundary: Python build | Validates: Constitution §Python baseline
- [X] T010 [P] Initialise the Angular workspace in `apps/web/` with `tsconfig.base.json` setting `strict`, `strictTemplates`, `noUncheckedIndexedAccess`, `noImplicitOverride` — Boundary: web build | Validates: Constitution §Angular
- [X] T011 [P] Create `apps/web/eslint.config.js` with library boundary rules: `customer-features` may not import `staff-features` or any application; `design-system` may not import business logic — Boundary: Angular libraries | Validates: Plan Stage 3
- [X] T012 [P] Initialise the Electron host in `apps/desktop/package.json` with main/preload/renderer builds and strict TypeScript — Boundary: desktop host | Validates: Constitution P-VII
- [X] T013 Create `build/scripts/check-boundaries.sh` failing on any cross-deployable reference: a `ragcore` string in any `.csproj`, a `Synthia` import in `ragcore/`, or an HTTP client in either targeting the other — Boundary: cross-deployable | Validates: Constitution P-V, ADR-0001
- [X] T014 [P] Create `.github/workflows/dotnet.yml` running restore, `dotnet build -warnaserror` and every `dotnet/tests/` suite — Boundary: CI | Validates: Constitution §Quality gate
- [X] T015 [P] Create `.github/workflows/ragcore.yml` running `ruff check`, `ruff format --check`, `mypy --strict src/` and pytest as failing steps — Boundary: CI | Validates: Constitution §Python baseline
- [X] T016 [P] Create `.github/workflows/web.yml` running lint, type-check, unit tests and the accessibility sweep — Boundary: CI | Validates: Constitution §Angular
- [X] T017 Create `.github/workflows/boundaries.yml` invoking `build/scripts/check-boundaries.sh` as a required check — Boundary: cross-deployable | Validates: Constitution P-V
- [X] T018 [P] Create `.github/workflows/migrations.yml` running `pytest --test-alembic` in `ragcore/` — Boundary: schema | Validates: ADR-0003
- [X] T019 [P] Add secret scanning to CI and a `.gitignore` excluding build artifacts in the repository root — Boundary: repository | Validates: Constitution §Secrets, §Commits
- [X] T020 [P] Create unit test projects `dotnet/tests/Synthia.SharedKernel.Tests/` and `dotnet/tests/Synthia.Modules.<Name>.Tests/` for all six modules, added to the solution — Boundary: .NET test | Validates: Constitution §Required test categories
- [X] T021 [P] Create the RagCore unit test structure in `ragcore/tests/unit/` mirroring `src/ragcore/` packages — Boundary: Python test | Validates: Constitution §Required test categories
- [X] T022 Plant a deliberate cross-tree reference and confirm `build/scripts/check-boundaries.sh` fails, then remove it — Boundary: cross-deployable | Validates: Stage 1 gate (the guard must demonstrably fail)

**Checkpoint**: All five workflows green on an empty repository; the boundary script provably fails a violation.

---

## Phase 2: Shared contracts and architecture boundaries *(Stage 2)*

**Goal**: Dependency direction and the tests that guard it, before any feature code exists.

- [X] T023 [P] Implement `TenantId`, `CorrelationId` and `StaffRole` in `dotnet/src/Synthia.SharedKernel/` as explicit domain types, with **no comparison or ordering operator on roles** — Boundary: shared kernel | Validates: Spec §FR-AUTHZ-003
- [X] T024 [P] Implement set-intersection authorization in `dotnet/src/Synthia.SharedKernel/Authorization/RoleIntersection.cs` — empty intersection denies — Boundary: authorization | Validates: Spec §FR-AUTHZ-004, §FR-AUTHZ-010
- [X] T025 [P] Implement the pure domain model in `ragcore/src/ragcore/domain/` — work item, operation, execution treatment, staff role — importing nothing outside the standard library — Boundary: domain | Validates: Constitution P-V (dependency inward)
- [X] T026 [P] Implement set-intersection role evaluation in `ragcore/src/ragcore/domain/roles.py`, mirroring T024 with no ordering — Boundary: authorization | Validates: Spec §FR-AUTHZ-003
- [X] T027 Declare application ports as Protocols in `ragcore/src/ragcore/application/ports.py` for retrieval, model, notification, messaging, tool execution, ingestion and each integration — Boundary: ports | Validates: Constitution P-V (ports belong to the consumer)
- [X] T028 [P] Define cross-module abstractions and DTOs in `dotnet/src/Synthia.Contracts/` with no implementation — Boundary: module contracts | Validates: Constitution P-V
- [X] T029 [P] Define typed IPC channel contracts with schema validators in `apps/desktop/src/ipc-contracts/` — Boundary: IPC | Validates: Constitution P-VII
- [X] T030 [P] Unit tests for set intersection in `ragcore/tests/unit/test_roles.py` asserting no ordering exists, no role implies another, and an empty intersection denies — Boundary: authorization | Validates: Spec §FR-AUTHZ-003, §FR-AUTHZ-006
- [X] T031 [P] Unit tests for set intersection in `dotnet/tests/Synthia.SharedKernel.Tests/RoleIntersectionTests.cs`, mirroring T030 so both stacks are proven independently — Boundary: authorization | Validates: Spec §FR-AUTHZ-004
- [X] T032 Write architecture tests in `dotnet/tests/Synthia.ArchitectureTests/ModuleIsolationTests.cs` asserting no module project references another — Boundary: module | Validates: Constitution P-V
- [X] T033 Write architecture tests in `dotnet/tests/Synthia.ArchitectureTests/NoRagCoreDependencyTests.cs` asserting no assembly reference, type or configured `HttpClient` base address resolves to RagCore — Boundary: cross-deployable | Validates: ADR-0001
- [X] T034 [P] Write architecture tests in `dotnet/tests/Synthia.ArchitectureTests/BannedApiTests.cs` for `DateTime.Now`, `Thread.Sleep` in async paths, `.Result`, `.Wait()`, `GetAwaiter().GetResult()`, and `catch (Exception)` without rethrow — Boundary: .NET | Validates: Constitution §.NET baseline
- [X] T035 [P] Write architecture tests in `dotnet/tests/Synthia.ArchitectureTests/CompositionRootTests.cs` asserting no Service Locator usage and no `BuildServiceProvider` call during configuration — Boundary: composition root | Validates: Constitution §Dependency injection
- [X] T036 [P] Write import-boundary tests in `ragcore/tests/architecture/test_layering.py` asserting `domain/` imports nothing outside the standard library and no adapter type appears in `domain/` or `application/` — Boundary: layering | Validates: Constitution P-V
- [X] T037 [P] Write a test in `ragcore/tests/architecture/test_no_dotnet.py` asserting no import, package or HTTP client targets the monolith — Boundary: cross-deployable | Validates: ADR-0001

**Checkpoint**: Every architecture test fails when its violation is planted and passes otherwise.

---

## Phase 3: Angular scaffold *(Stage 3)*

**Goal**: Three applications and four libraries that build and render, with shared infrastructure centralized.

- [X] T038 [P] Implement `apps/web/projects/design-system/` accessible primitives — focus management, live regions, state conveyed by more than colour — Boundary: presentation | Validates: Spec §FR-SURF-010, §FR-SURF-013
- [X] T039 [P] Implement loading, empty and partial-failure states in `apps/web/projects/design-system/states/` so no failure renders as an empty result — Boundary: presentation | Validates: Spec §FR-SURF-016
- [X] T040 Implement `apps/web/projects/platform-core/` with typed API clients for both backends, auth/token handling, correlation propagation and RFC 9457 problem-details handling — Boundary: client infrastructure | Validates: Constitution §Angular (centralized infrastructure)
- [X] T041 [P] Implement the realtime client in `apps/web/projects/platform-core/realtime/` that rebuilds state from the API on reconnect rather than from missed notifications — Boundary: realtime | Validates: Spec §FR-SESS-019
- [X] T042 [P] Scaffold `apps/web/projects/customer-features/` shells for chat, session, consent and handoff with no behaviour — Boundary: presentation | Validates: Constitution P-IX (scaffold honestly)
- [X] T043 [P] Scaffold `apps/web/projects/staff-features/` shells for the queue, take-over and reporting — Boundary: presentation | Validates: Constitution P-IX
- [X] T044 Compose `apps/web/projects/customer-portal/` from `customer-features` and `platform-core` — Boundary: customer surface | Validates: Spec §FR-SURF-001
- [X] T045 Compose `apps/web/projects/staff-portal/` with module visibility by role and **no session-origination route** — Boundary: staff surface | Validates: Spec §FR-SURF-006
- [X] T046 Compose `apps/web/projects/desktop-renderer/` reusing `customer-features`, adding only the desktop bridge service — Boundary: desktop surface | Validates: Plan Stage 3
- [X] T047 [P] Write a test in `apps/web/projects/platform-core/no-authz.spec.ts` asserting no presentation component makes an authorization decision — Boundary: presentation | Validates: Spec §FR-SURF-004
- [X] T048 [P] Configure the plan Stage 3 CSP baseline as a **response header** (never a meta tag) and the Angular sanitization policy in `apps/web/projects/platform-core/security/`, with `bypassSecurityTrust*` absent and no unsafe-inline or unsafe-eval in script-src — Boundary: browser security | Validates: Constitution P-VII
- [X] T049 [P] Write the axe-core accessibility sweep in `apps/web/e2e/a11y-scaffold.spec.ts` across all three surfaces — Boundary: presentation | Validates: Spec §SC-SURF-002

**Checkpoint**: All three apps build under strict TypeScript; zero Level A/AA failures; boundary lint fails a cross-library import.

---

## Phase 4: Electron scaffold *(Stage 4)*

**Goal**: A thin, hardened host that renders the renderer and decides nothing.

- [X] T050 Implement main-process window creation in `apps/desktop/src/main/window.ts` with `nodeIntegration=false`, `contextIsolation=true`, `sandbox=true` **unconditionally** (plan Stage 4 resolves "where compatible"; disabling it requires an ADR) — Boundary: desktop host | Validates: Constitution P-VII
- [X] T051 Implement the narrow typed `contextBridge` surface in `apps/desktop/src/preload/bridge.ts`, never exposing raw `ipcRenderer` or broad Electron/Node APIs — Boundary: IPC | Validates: Constitution P-VII
- [X] T052 Implement IPC **sender** validation and **argument** validation as two distinct checks in `apps/desktop/src/main/ipc-guard.ts` — Boundary: IPC | Validates: Constitution P-VII
- [X] T053 [P] Implement the navigation and new-window allow-list in `apps/desktop/src/main/navigation.ts` permitting **only** the renderer bundle origin, the single gateway origin and the Entra authority (plan Stage 4 names the complete set); the window-open handler denies every destination without exception; exact scheme match on HTTPS/WSS only; `webSecurity` never disabled — Boundary: desktop host | Validates: Constitution P-VII, Spec §FR-SURF-017
- [X] T054 [P] Implement the plan Stage 3 CSP baseline for the renderer in `apps/desktop/src/main/csp.ts`, applied from the main process on received headers so the renderer cannot weaken it, with connect-src narrowed to the gateway, SignalR and Entra origins — Boundary: desktop host | Validates: Constitution P-VII
- [X] T055 [P] Write the Electron security suite in `apps/desktop/tests/security.spec.ts` asserting each switch, that IPC rejects an unvalidated sender and an unvalidated argument, and that navigation outside the allow-list is blocked — Boundary: desktop host | Validates: Stage 4 gate
- [X] T056 [P] Write a test in `apps/desktop/tests/no-policy.spec.ts` asserting no business authorization decision exists in the renderer **or** the main process — Boundary: desktop host | Validates: Constitution P-VII

*Added during Stage 4 implementation. The seven tasks above harden the host; these seven make it a
host that actually renders something, and record the two boundaries the desktop path must not cross.*

- [X] T056a Implement host origin configuration in `apps/desktop/src/main/config.ts` — one validated, frozen source for the gateway, realtime and Entra origins that the allow-list, the CSP and the reported endpoints all derive from; rejects a non-HTTPS/WSS origin, credentials, a path or a query at startup — Boundary: desktop host | Validates: Spec §FR-SURF-017, Constitution P-VII
- [X] T056b Implement renderer integration in `apps/desktop/src/main/renderer-protocol.ts` — the Angular bundle served over a standard, secure scheme with an assertable origin instead of `file://`, with path-traversal containment — Boundary: desktop host | Validates: Constitution P-VII (`file://` avoided where a safer protocol strategy applies)
- [X] T056c Implement the application shell in `apps/desktop/src/main/app-shell.ts` — the guarded IPC handler table, permissions denied by default, certificate errors never trusted, and a refusal to start under a switch that would disable a control — Boundary: desktop host | Validates: Constitution P-VII
- [X] T056d Implement the desktop session integration boundary in `apps/desktop/src/main/session-boundary.ts` — a descriptor, not a session: token custody is the renderer's, authority is the platform's, the main process persists nothing — Boundary: desktop session | Validates: Constitution P-VII, Spec §FR-SURF-004
- [X] T056e Implement the endpoint execution boundary **placeholder** in `apps/desktop/src/main/endpoint-execution-boundary.ts` — the four required bindings declared as a type, execution and verification both refusing unconditionally, reachable from no IPC channel — Boundary: endpoint execution | Validates: Constitution P-III, P-VII, ADR-0004 (deferred)
- [X] T056f Implement the Angular desktop bridge in `apps/web/projects/desktop-renderer/src/app/desktop/` and the renderer shell that consumes it, degrading to browser mode when no host is present — Boundary: desktop surface | Validates: Plan Stage 3 (T046, bridge service only)
- [X] T056g [P] Write `apps/desktop/tests/bridge-surface.spec.ts`, `tests/renderer-contract.spec.ts` and `build/scripts/verify-desktop-security-guard.sh` — the bridge stays narrow, the two hand-maintained declarations of it cannot drift, and the security suite is proven to fail when each control is weakened — Boundary: desktop host | Validates: Stage 4 gate, Plan Stage 11

**Checkpoint**: The security suite passes, and fails correctly when a setting is flipped.

---

## Phase 5: .NET scaffold *(Stage 5)*

**Goal**: A read-only modular monolith that starts and serves versioned APIs with no data behind it.

- [X] T057 Implement the Gateway-derived identity header contract in `dotnet/src/Synthia.Api/Middleware/IdentityContextMiddleware.cs` — no token parsing; reject any request supplying tenant or role — Boundary: identity | Validates: Spec §FR-IDENT-002
- [X] T058 [P] Implement correlation middleware in `dotnet/src/Synthia.Api/Middleware/CorrelationMiddleware.cs` accepting `X-Correlation-Id` only when well formed, generating when absent, echoing in responses — Boundary: observability | Validates: Spec §FR-OPS-001
- [X] T059 [P] Configure `IExceptionHandler` with RFC 9457 ProblemDetails in `dotnet/src/Synthia.Api/Errors/`, never exposing internal detail — Boundary: API | Validates: Constitution §.NET validation and errors
- [X] T060 Configure Minimal API routing in `dotnet/src/Synthia.Api/Program.cs` — URI-segment versioning under `/api/{audience}/v1/views/...`, plural nouns, kebab-case multi-word segments, camelCase JSON, built-in OpenAPI — Boundary: API | Validates: Constitution §.NET APIs
- [X] T061 [P] Implement keyset pagination with **opaque** cursors in `dotnet/src/Synthia.Api/Paging/` — Boundary: API | Validates: Contracts §README
- [X] T062 [P] Implement typed filter binding and a whitelisted sort resolver in `dotnet/src/Synthia.Api/Querying/` against the **per-resource field sets enumerated in `contracts/README.md`**, defaulting to `-createdAt` (`-occurredAt` for audit) so keyset pagination has a deterministic order, and rejecting an unknown field with 400 — Boundary: API | Validates: Contracts §README
- [X] T063 [P] Scaffold the six module projects under `dotnet/src/Modules/` — Sessions, Work, Approvals, Governance, Audit, Tenancy — each with a registration extension and no reference to another module — Boundary: module | Validates: Constitution P-V
- [X] T064 Wire module registration from the single composition root in `dotnet/src/Synthia.Api/Program.cs` using constructor injection only — Boundary: composition root | Validates: Constitution §Dependency injection
- [X] T065 [P] Add liveness `/health/live` (process-only, no dependency checks) in `dotnet/src/Synthia.Api/Health/` — Boundary: runtime | Validates: Constitution §Health
- [X] T066 [P] Write contract tests in `dotnet/tests/Synthia.ContractTests/ApiConventionTests.cs` for camelCase, cursor shape, versioning, kebab-case segments and problem-details — Boundary: API | Validates: Stage 5 gate
- [X] T067 [P] Write an architecture test in `dotnet/tests/Synthia.ArchitectureTests/NoWriteEndpointTests.cs` asserting the monolith exposes no state-changing endpoint — Boundary: read-only | Validates: Spec §FR-SURF-004, ADR-0001
- [X] T068 [P] Write an architecture test in `dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs` asserting `Database.Migrate()`, `EnsureCreated()` and EF migration files are absent — Boundary: schema ownership | Validates: ADR-0003

**Checkpoint**: The app starts, `/health/live` responds, OpenAPI generates, contract tests pass.

---

## Phase 6: RagCore scaffold *(Stage 6)*

**Goal**: A FastAPI application and LangGraph skeleton with the three interrupts, ports declared, adapters absent.

- [X] T069 Implement typed settings in `ragcore/src/ragcore/config/settings.py` using Pydantic Settings, resolving secrets from Key Vault via managed identity, with no scattered environment reads — Boundary: configuration | Validates: Constitution §Python (Pydantic Settings)
- [X] T070 Implement the identity header middleware in `ragcore/src/ragcore/api/middleware/identity.py` — no token parsing; reject any request supplying tenant or role — Boundary: identity | Validates: Spec §FR-IDENT-002
- [X] T071 [P] Implement correlation middleware in `ragcore/src/ragcore/api/middleware/correlation.py` binding the identifier to the logging context — Boundary: observability | Validates: Spec §FR-OPS-001
- [X] T072 [P] Implement RFC 9457 problem-details handling in `ragcore/src/ragcore/api/middleware/problems.py` matching the .NET shape — Boundary: API | Validates: Contracts §README
- [X] T073 Scaffold the customer, staff and workload routers in `ragcore/src/ragcore/api/{customer,staff,workload}/` with explicit Pydantic request/response schemas and **no business policy in endpoints** — Boundary: API | Validates: Constitution §FastAPI
- [X] T074 Wire dependency injection via FastAPI `Depends` at HTTP boundaries only in `ragcore/src/ragcore/api/deps.py` — Boundary: composition root | Validates: Constitution §Dependency injection
- [X] T075 Implement the LangGraph state and builder in `ragcore/src/ragcore/graph/{state.py,builder.py}` with the three interrupt points: clarification, consent, approval — Boundary: orchestration | Validates: Spec §FR-INTR-001
- [X] T076 [P] Implement the session state machine in `ragcore/src/ragcore/domain/session_state.py` covering the nine states, with the three `awaiting_*` states persisting indefinitely — Boundary: domain | Validates: Spec §FR-SESS-015, §FR-SESS-016
- [X] T077 [P] Scaffold `ragcore/src/ragcore/ingestion/` — the twelfth bounded context: acquisition, normalisation, chunking, embedding, indexing — with no behaviour — Boundary: Ingestion context | Validates: Plan §Project Structure, research R-021
- [X] T078 [P] Implement the SSE streaming envelope in `ragcore/src/ragcore/api/customer/streaming.py` with event kinds `token`, `step`, `interrupt`, `done`, `error` — Boundary: API | Validates: Contracts §customer-api
- [X] T079 [P] Write contract tests in `ragcore/tests/contracts/test_api_surface.py` for the three audiences and the SSE envelope — Boundary: API | Validates: Stage 6 gate
- [X] T080 [P] Write async cancellation tests in `ragcore/tests/unit/test_cancellation.py` asserting `asyncio.CancelledError` propagates and is never swallowed — Boundary: async | Validates: Constitution §Python (cancellation)
- [X] T081 [P] Write a test in `ragcore/tests/unit/test_graph_interrupts.py` asserting the graph suspends and resumes in memory at all three interrupt points — Boundary: orchestration | Validates: Stage 6 gate

**Checkpoint**: `mypy --strict` and `ruff` clean; the graph suspends and resumes in memory.

---

## Phase 7: PostgreSQL and persistence scaffold *(Stage 7)*

**Goal**: The authoritative durable store, migration discipline, and the read-view contract.

- [X] T082 Initialise Alembic in `ragcore/` with the async template; configure `ragcore/migrations/env.py` with `async_engine_from_config`, `NullPool` and `connection.run_sync` — Boundary: schema | Validates: ADR-0003
- [X] T083 Configure `ragcore/migrations/env.py` to exclude the `langgraph` schema from autogenerate via `include_schemas`/`include_object` — Boundary: schema | Validates: research R-004
- [X] T084 Configure the durable LangGraph checkpointer in `ragcore/src/ragcore/graph/checkpointer.py` using `langgraph-checkpoint-postgres` against the `langgraph` schema, compile the graph with it in place of the in-memory saver, and run the checkpointer's own `setup()` from the migration job — never at application startup — Boundary: orchestration | Validates: Constitution P-IV (one checkpoint store), research R-004
- [X] T085 [P] Create the `tenant_mapping` migration in `ragcore/migrations/versions/` — `tenant_id` uuid PK, `entra_tid` uuid unique not null, `display_name` text not null, `status` enum (`active`, `suspended`, `offboarded`) not null, `retention_overrides` jsonb null, `version` int not null — Boundary: Tenant & Configuration | Validates: data-model.md
- [X] T086 [P] Create the `chat_session` migration in `ragcore/migrations/versions/` — `state` enum (`conversational`, `resolving`, `awaiting_user`, `awaiting_consent`, `awaiting_approval`, `staff_controlled`, `resolved`, `escalated`, `closed_declined`) not null, `content_expires_at` timestamptz **null while active**, `version` int not null — Boundary: Session | Validates: Spec §FR-SESS-015, §FR-SESS-020
- [X] T087 [P] Create the `message` migration in `ragcore/migrations/versions/` — `tenant_id` uuid not null (denormalised for non-bypassable filtering), `sender_kind` enum (`end_user`, `agent`, `staff`) not null — Boundary: Session | Validates: data-model.md
- [X] T088 [P] Create the `feedback` migration in `ragcore/migrations/versions/` — `signal` enum (`positive`, `negative`) not null, **unique on (`message_id`, `given_by_oid`)** so a revision updates rather than inserts — Boundary: Session | Validates: Spec §FR-SESS-010
- [X] T089 Create the `work_item` migration in `ragcore/migrations/versions/` with `state` enum (`open`, `awaiting_decision`, `authorized`, `claimed`, `executed`, `failed`, `expired`, `cancelled`, `escalated`) and `approval_state` enum (`none`, `pending`, `approved`, `rejected`, `expired`), plus `version` int not null — Boundary: Work | Validates: data-model.md
- [X] T090 Add a database-level immutability guard on `work_item` authority fields (`tenant_id`, `requested_by_oid`, `case_reference`, `governed_action`, `target`) via trigger or column grant in `ragcore/migrations/versions/` — Boundary: Work | Validates: Spec §FR-EXEC-008
- [X] T091 [P] Create the `operation` migration in `ragcore/migrations/versions/` — `treatment` enum (`AUTO`, `END_USER_APPROVAL`, `STAFF_APPROVAL`, `NOT_ALLOWED`), `verification` enum (`server_confirmed`, `client_attested`, `contradicted`) null — Boundary: Governance | Validates: data-model.md
- [X] T092 [P] Create the `governance_record` migration in `ragcore/migrations/versions/` — composite PK (`catalogue_id`, `version`), `accepted_roles` text[] not null, `is_reference_fixture` bool not null, `requires_elevation` bool not null **with a CHECK constraint enforcing false** — Boundary: Governance | Validates: ADR-0004
- [X] T093 [P] Create the `tenant_entitlement` migration in `ragcore/migrations/versions/` — `credential_reference` text null (a Key Vault reference, **never a secret value**) — Boundary: Tool Execution | Validates: Spec §FR-EXT-016
- [X] T094 [P] Create the `approval` migration in `ragcore/migrations/versions/` — `work_item_id` uuid FK **unique** not null (at most one approval per case), `decided_by_roles` text[] null, `expires_at` timestamptz null — Boundary: Approval | Validates: Spec §FR-INTR-010
- [X] T095 [P] Create the `consent` migration in `ragcore/migrations/versions/` — `consented_by_oid` uuid not null, `verdict` enum (`granted`, `refused`) not null — Boundary: Approval | Validates: Spec §FR-INTR-005
- [X] T096 [P] Create the `audit_event` migration in `ragcore/migrations/versions/` with the full actor chain, `execution_method` enum (`workload`, `desktop_script`, `none`), `correlation_id` text not null, `retain_until` timestamptz not null, append-only with no update or delete grant — Boundary: Audit | Validates: Spec §FR-AUDIT-001
- [X] T097 [P] Create the `outbox_message` migration in `ragcore/migrations/versions/` — `payload` jsonb carrying opaque identifiers and correlation only, `dispatched_at` timestamptz null, `attempts` int, `version` int — Boundary: messaging | Validates: research R-017
- [X] T098 [P] Create the `idempotency_record` migration in `ragcore/migrations/versions/` — `idempotency_key` text PK, `outcome` jsonb null replayed on repeat, and **no `version` column**: this is the single named exemption from the optimistic-concurrency convention (data-model.md §Conventions) — Boundary: Tool Execution | Validates: data-model.md
- [X] T099 [P] Create the `ingestion_run` migration in `ragcore/migrations/versions/` — `watermark` text null, `state` enum (`running`, `completed`, `failed`), tenant-stamped — Boundary: Ingestion | Validates: research R-021
- [X] T100 [P] Scaffold the ingestion worker entry point in `ragcore/workers/ingestion_run.py` opening an `ingestion_run` row and recording its watermark and terminal state, with **no acquisition, chunking or embedding behaviour** — Boundary: Ingestion | Validates: Plan §Project Structure, Constitution P-IX
- [X] T101 Create the published-view migration in `ragcore/migrations/versions/` using `alembic_utils` defining all eleven `vw_*_v1` views, each carrying `tenant_id`, none exposing credential material, each respecting retention and excluding soft-deleted rows — Boundary: read contract | Validates: Contracts §read-views
- [X] T102 Grant separated database principals in `ragcore/migrations/versions/`: migration job DDL, RagCore runtime DML+SELECT, monolith runtime SELECT on published views only — Boundary: schema ownership | Validates: ADR-0003
- [X] T103 Implement SQLAlchemy models and repositories in `ragcore/src/ragcore/persistence/` where **every** query applies `tenant_id` and no method omits it — Boundary: tenant isolation | Validates: Spec §FR-IDENT-008
- [X] T104 [P] Implement optimistic concurrency in `ragcore/src/ragcore/persistence/concurrency.py` using the `version` column on every table except the named `idempotency_record` exemption, with **no distributed lock anywhere**, **no Serializable transaction** and **no `deleted_at` column on any scaffold entity** — all three positions stated in data-model.md §Conventions — Boundary: persistence | Validates: research R-018
- [X] T105 [P] Implement retention-from-terminal-state in `ragcore/src/ragcore/persistence/retention.py` so `content_expires_at` is set only on a terminal transition — Boundary: Session | Validates: Spec §FR-SESS-020
- [X] T106 Implement the retention sweeper in `ragcore/workers/retention_sweep.py` removing data past its window for every class in data-model.md §Retention summary — chat content 90 days from terminal state, graph checkpoints 30 days after the work completes, audit events 7 years — resolving each window from `tenant_mapping.retention_overrides` and falling back to the platform default wherever no override is configured — Boundary: retention | Validates: Spec §FR-SESS-007, §FR-SESS-008, §FR-AUDIT-004, §FR-AUDIT-005
- [X] T107 Implement per-organisation erasure in `ragcore/src/ragcore/persistence/erasure.py` removing that organisation's records, their derived representations and any cached copies — Boundary: Tenant & Configuration | Validates: Spec §FR-AUDIT-006
- [X] T108 Configure EF Core read contexts in `dotnet/src/Synthia.Persistence/` mapped to `vw_*_v1` views with `AsNoTracking` default, parameterized queries, and a mandatory tenant filter with no unfiltered path — Boundary: read contract | Validates: Constitution §.NET data access
- [X] T109 [P] Write migration tests in `ragcore/tests/migrations/test_migrations.py` importing pytest-alembic's `test_single_head_revision`, `test_upgrade`, `test_model_definitions_match_ddl`, `test_up_down_consistency` — Boundary: schema | Validates: ADR-0003
- [X] T110 [P] Write a test in `ragcore/tests/migrations/test_schema_isolation.py` asserting autogenerate never proposes a change inside the `langgraph` schema — Boundary: schema | Validates: research R-004
- [X] T111 [P] Write a test in `ragcore/tests/checkpoint/test_durable_checkpointer.py` asserting the compiled graph carries the PostgreSQL saver, that no in-memory saver reaches a non-test path, and that no second durable checkpoint store exists — Boundary: orchestration | Validates: Constitution P-IV
- [X] T112 [P] Write concurrency tests in `ragcore/tests/concurrency/test_optimistic.py` asserting a losing writer sees a version conflict and re-reads rather than blocking — Boundary: persistence | Validates: research R-018
- [X] T113 [P] Write retention tests in `ragcore/tests/retention/test_retention_classes.py` verifying removal independently for each class and asserting that expiring chat content leaves its audit records intact and complete — Boundary: retention | Validates: Spec §SC-AUDIT-002, §SC-AUDIT-003

**Checkpoint**: Migrations run as a gated job, never at startup; every downgrade succeeds; no unfiltered query path exists; the graph is backed by the durable PostgreSQL checkpointer and every retention class is removable.

---

## Phase 8: Messaging and realtime scaffold *(Stage 8)*

**Goal**: Transactional outbox, opaque triggers, at-least-once consumption, notification-only realtime.

- [X] T114 Implement the outbox writer in `ragcore/src/ragcore/messaging/outbox.py` so the outbox row commits **in the same transaction** as the state change it describes — Boundary: messaging | Validates: research R-017
- [X] T115 Implement the outbox dispatcher worker in `ragcore/workers/outbox_dispatch.py` publishing to Service Bus and setting `dispatched_at`, with exponential backoff and jitter to a **ceiling of 10 attempts**, after which the row is marked undispatchable, left in place and never auto-retried — and, for a `granted` kind, surfaced as approved-but-not-executed with an operational alert; a blocked row never blocks another — Boundary: messaging | Validates: Contracts §triggers, research R-017
- [X] T116 [P] Implement the Service Bus publisher in `ragcore/src/ragcore/messaging/publisher.py` emitting only `workItemId`, `correlationId` and a `kind` drawn from the closed set in `contracts/triggers.md` — Boundary: trigger contract | Validates: Contracts §triggers
- [X] T117 Implement the resume consumer in `ragcore/workers/resume_worker.py` performing load, verify, atomic claim, resume, execute, record — dispatching on `kind` while reading authority **only** from the work record, never from the message. *Amended 2026-09-16*: the scaffold wires the **sample-flow kind** only; the four approval and consent kinds remain in the closed set in `contracts/triggers.md` and their handlers are deferred (spec FR-DEMO-016). An unhandled kind is dead-lettered with an alert, **never** treated as authorization to proceed (spec FR-DEMO-018) — Boundary: Work | Validates: ADR-0002, Contracts §triggers
- [X] T118 [P] Implement the atomic claim in `ragcore/src/ragcore/execution/claim.py` as a conditional update on `claimed_at IS NULL` — idempotency boundary 1 — Boundary: Work | Validates: Spec §FR-EXEC-004
- [X] T119 [P] Implement idempotency-key generation and the replay path in `ragcore/src/ragcore/execution/idempotency.py` — idempotency boundary 2 — Boundary: Tool Execution | Validates: Spec §FR-EXEC-005
- [X] T120 [P] Implement bounded pre-claim retry with jitter in `ragcore/src/ragcore/messaging/retry.py`, and **no post-claim retry** — Boundary: execution | Validates: Spec §FR-EXEC-006
- [X] T121 [P] Implement the expiry sweeper in `ragcore/workers/expiry_sweep.py` marking work non-executable once the window passes with no claim — Boundary: Work | Validates: Spec §FR-EXEC-001
- [X] T122 [P] Implement dead-letter handling in `ragcore/src/ragcore/messaging/deadletter.py` raising an operational alert with no automatic replay — Boundary: messaging | Validates: Spec §FR-EXEC-007
- [X] T123 Implement the SignalR data-plane REST client in `ragcore/src/ragcore/notifications/signalr.py` using an Entra token (scope `https://signalr.azure.com/.default`) via managed identity — Boundary: realtime | Validates: research R-002
- [X] T124 [P] Implement connection negotiation and group derivation in `ragcore/src/ragcore/api/customer/negotiate.py` — group membership derived from trusted identity, never requested by the client — Boundary: realtime | Validates: Contracts §notifications
- [X] T125 [P] Write idempotency tests in `ragcore/tests/idempotency/test_duplicate_trigger.py` asserting a duplicate trigger produces exactly one execution and one external effect — Boundary: messaging | Validates: Stage 8 gate
- [X] T126 [P] Write an outbox crash test in `ragcore/tests/integration/test_outbox_crash.py` asserting a crash between commit and publish loses nothing and duplicates nothing — Boundary: messaging | Validates: quickstart V16

- [X] T219 Authenticate the Service Bus client by **managed identity** in `ragcore/src/ragcore/messaging/credentials.py` using `DefaultAzureCredential`, with **no connection string, no shared access key and no SAS token** anywhere in source or configuration; the namespace is a fully qualified name, not a credential-bearing DSN — Boundary: messaging | Validates: Spec §FR-DEMO-011, Plan §Authentication
- [X] T220 Implement the **sample async message flow** end to end in `ragcore/src/ragcore/messaging/sample_flow.py` — publish a `sample.flow` trigger from the outbox and consume it in the resume worker, acting only on an inert reference operation and producing **no external effect** — Boundary: sample flow | Validates: Spec §FR-DEMO-007, §FR-DEMO-014
- [X] T221 [P] Propagate the correlation identifier and W3C `traceparent` onto every outbox row and every published message in `ragcore/src/ragcore/messaging/publisher.py`, and restore them as the ambient context in the consumer, so one journey is followable across the asynchronous hop — Boundary: observability | Validates: Spec §FR-DEMO-009, §FR-OPS-001
- [X] T222 [P] Write a test in `ragcore/tests/messaging/test_trigger_payload.py` asserting a published trigger carries **only** `workItemId`, `correlationId` and `kind` — no tenant, requester, role, action, target or approval state — Boundary: trigger contract | Validates: Contracts §triggers, Spec §FR-DEMO-010

**Checkpoint**: Duplicate delivery absorbed by the claim; expired messages dead-letter rather than executing; the bus is reached by managed identity and the payload carries no authority.

---

## Phase 9: Integration adapter scaffold *(Stage 9)*

**Goal**: Every external system behind a port, with no provider type reaching inward.

> **Relocated, not retired — 2026-09-18.** These tasks are complete and **stay `[X]`**. ADR-0007 moves
> most of what they produced out of RagCore into the Integrations Service; Phase 16 covers the move,
> and §Relocated 2026-09-18 carries the task-by-task traceability. The paths in the descriptions below
> are the **original** locations and are stale by design — they record where the work was done, which
> is what a completed task is for. `T127`, `T128`, `T138`, `T223`, `T225` and `T225a` are **not**
> relocated: model egress is reasoning, and the identity registry is platform-wide.

- [X] T127 Configure the AI Gateway in `build/infra/ai-gateway/` as the sole model egress — provider routing, provider-normalised token metering per organisation, budgets and throttles, semantic cache, bidirectional content safety — Boundary: model egress | Validates: Constitution §Model access
- [X] T128 Implement the model adapter in `ragcore/src/ragcore/integrations/model/` behind the port from T027, routed exclusively through the AI Gateway — Boundary: model | Validates: Spec §FR-OPS-007
- [X] T129 [P] Implement the ServiceNow adapter in `ragcore/src/ragcore/integrations/servicenow/` as the sole path to the system of record, with idempotent write-backs and queue-and-replay on outage — Boundary: Integration—ServiceNow | Validates: Spec §FR-EXT-004, §FR-EXT-007
- [X] T130 [P] Implement the Microsoft Graph adapter in `ragcore/src/ragcore/integrations/graph/` behind its port — Boundary: Integration—Graph | Validates: Spec §FR-EXT-008
- [X] T131 [P] Implement the MCP client boundary in `ragcore/src/ragcore/integrations/mcp/client.py` where discovery never confers entitlement — Boundary: Tool Execution | Validates: Spec §FR-EXT-014
- [X] T132 [P] Implement the OneLogin and Duo adapters in `ragcore/src/ragcore/integrations/{onelogin,duo}/` as MCP-backed target systems — Boundary: Tool Execution | Validates: ADR-0005
- [X] T133 Implement typed HTTP clients with pooled lifetime management, a shared resilience policy distinguishing transient from non-transient failure, and an **explicit timeout on every outbound call** in `ragcore/src/ragcore/integrations/http.py` — Boundary: egress | Validates: research R-020
- [X] T134 [P] Implement boundary contract validation in `ragcore/src/ragcore/integrations/validation.py` rejecting malformed, oversized or contract-violating provider output before it reaches the agent loop — Boundary: integration | Validates: Spec §FR-EXT-021
- [X] T135 [P] Implement the entitled-but-unreachable distinction in `ragcore/src/ragcore/execution/availability.py`, reported separately from not-entitled and never as a user request failure — Boundary: Tool Execution | Validates: Spec §FR-EXT-022
- [X] T136 [P] Write adapter tests in `ragcore/tests/integrations/test_adapters.py` exercising each adapter against a fake honouring its contract — Boundary: integration | Validates: Constitution §Required test categories
- [X] T137 [P] Write a test in `ragcore/tests/integrations/test_no_provider_leak.py` asserting no provider SDK or model type appears in `domain/` or `application/` — Boundary: layering | Validates: Spec §FR-EXT-011
- [X] T138 [P] Write a test in `ragcore/tests/architecture/test_no_direct_model_call.py` asserting no module holds a provider endpoint outside `integrations/model/` — Boundary: model egress | Validates: Constitution §Model access

- [X] T223 [P] Implement the **Azure AI Search** boundary in `ragcore/src/ragcore/retrieval/search.py` behind the `RetrievalPort` from T027 — reached by **managed identity**, tenant filter applied on every query with **no code path able to issue an unfiltered one**, and the index treated as **derived**: a lost index is rebuilt by re-running ingestion, never restored — Boundary: Retrieval | Validates: Spec §FR-IDENT-008, §FR-IDENT-009, Constitution P-IV
- [X] T224 [P] Implement Key Vault credential-reference resolution in `ragcore/src/ragcore/config/secrets.py` — resolves a `*_secret_name` **reference** to a value at the point of use via managed identity, caches within the process lifetime only, and **never logs, echoes or persists a resolved value**; `tenant_entitlement.credential_reference` resolves through this path and nowhere else — Boundary: configuration | Validates: Spec §FR-EXT-016, §FR-DEMO-012
- [X] T225 Implement the shared Azure credential chain in `ragcore/src/ragcore/infrastructure/azure_credentials.py` — one `DefaultAzureCredential`, reused by every Azure SDK client (Service Bus, SignalR, Key Vault, AI Search, Foundry, PostgreSQL), so **managed identity is used wherever the resource supports it** and no client constructs its own credential — Boundary: identity | Validates: Spec §FR-DEMO-011, Plan §Authentication
- [X] T225a [P] Enforce the **cross-platform Azure identity rule**. One shared registry in `build/policy/azure-identity.json` naming all eight resources (PostgreSQL, Service Bus, SignalR, Key Vault, AI Search, Foundry/gateway, Application Insights, Redis), their managed-identity position and any named exemption; enforced on both stacks by `ragcore/tests/security/test_azure_identity.py` and `dotnet/tests/Synthia.ArchitectureTests/AzureIdentityTests.cs`, each of which asserts the other exists, reads the same registry and covers the same resources. Rejects application-owned credential types, credential-bearing connection strings, embedded PostgreSQL passwords and secret-valued configuration keys — Boundary: secrets | Validates: Spec §SC-DEMO-004, Plan §Authentication

**Checkpoint**: No provider type reaches inward; no direct model access exists; every outbound call has a timeout; every Azure resource is reached by managed identity and every secret by reference.

---

## Phase 10: Observability, configuration and container scaffold *(Stage 10)*

**Goal**: Traces, correlation, validated configuration and hardened images.

- [X] T139 Configure OpenTelemetry tracing, metrics and structured logging in `dotnet/src/Synthia.Observability/` with constant message templates and PascalCase placeholders, exporting to Application Insights — Boundary: observability | Validates: Spec §FR-OPS-002
- [X] T140 [P] Configure OpenTelemetry and structured logging in `ragcore/src/ragcore/observability/` tagged with the owning organisation from trusted context, never from a header or message content — Boundary: observability | Validates: Spec §FR-OPS-002
- [X] T141 Ensure W3C Trace Context propagation across both deployables and onto every trigger, notification and audit record in `ragcore/src/ragcore/observability/propagation.py` — Boundary: observability | Validates: Spec §FR-OPS-001
- [X] T142 [P] Emit agent-specific signals in `ragcore/src/ragcore/observability/agent_metrics.py` — token usage per organisation, cache-hit ratio, guardrail actions, gate-outcome distribution, retrieval confidence — Boundary: observability | Validates: Spec §FR-OPS-003
- [X] T142a [P] Configure telemetry retention at 30 days and **tail-based sampling keyed on the correlation identifier** in the exporter and Container Apps configuration, so a suspended-and-resumed journey is sampled as one unit and every trace carrying an error, a governance denial or an approval is retained regardless; head sampling is prohibited — Boundary: observability | Validates: Spec §FR-OPS-011, §FR-OPS-012
- [X] T143 [P] Configure typed Options in `dotnet/src/Synthia.Api/Configuration/` using `AddOptions<T>()`, `BindConfiguration`, `ValidateDataAnnotations()` and `ValidateOnStart()`, with no `Configuration["..."]` in application code — Boundary: configuration | Validates: research R-019
- [X] T144 [P] Add readiness `/health/ready` in `dotnet/src/Synthia.Api/Health/` covering database and critical dependency readiness, distinct from liveness — Boundary: runtime | Validates: Constitution §Health
- [X] T145 [P] Add liveness and readiness endpoints in `ragcore/src/ragcore/api/health.py` with the same semantics — Boundary: runtime | Validates: Constitution §Health
- [X] T146 Create `build/docker/dotnet.Dockerfile` — multi-stage SDK → `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled`, **digest-pinned**, non-root UID 1654, shell-less, no package manager, read-only root filesystem — Boundary: runtime | Validates: Constitution §Containers, research R-011
- [X] T147 [P] Create `build/docker/ragcore.Dockerfile` — multi-stage slim Python 3.12, **digest-pinned** in production, non-root under a fixed documented UID, install from `uv.lock` only, no build toolchain and no package-manager cache in the final layer, read-only root filesystem with every writable path named — Boundary: runtime | Validates: research R-012, Constitution §Containers
- [X] T148 [P] Define Container Apps configuration in `build/docker/containerapps/` with HTTP health probes, explicit resource limits per deployable and a 25-second drain, documenting that drain is a grace period: a post-claim execution outliving it surfaces as approved-but-not-executed and is **never** re-fired (plan Stage 10) — Boundary: runtime | Validates: Constitution §Containers, Spec §FR-EXEC-006
- [X] T148a [P] Create the scheduled digest-update workflow in `.github/workflows/base-image-digests.yml` — resolves the current digest per tracked tag monthly and on a High or Critical CVE, opens a PR carrying the vulnerability diff, and gates it on the full suite plus a clean image scan — Boundary: supply chain | Validates: Constitution §Containers, Plan Stage 10
- [X] T149 Create the migration job definition in `build/docker/migrate.job.yaml` running Alembic **and the checkpointer's own `setup()`** before revision activation, never at startup — Boundary: schema ownership | Validates: ADR-0003
- [X] T150 [P] Write configuration-validation tests in `dotnet/tests/Synthia.ContractTests/ConfigurationValidationTests.cs` and `ragcore/tests/unit/test_settings.py` asserting a missing required setting fails the process at start — Boundary: configuration | Validates: quickstart V17
- [X] T151 [P] Write security tests in `ragcore/tests/security/test_no_leakage.py` asserting no secret, token, authorization header, sensitive payload or cross-tenant value reaches a log sink — Boundary: observability | Validates: Spec §FR-OPS-002
- [X] T152 [P] Write a trace test in `ragcore/tests/integration/test_trace_continuity.py` following one request across suspension and resume via a single correlation identifier — Boundary: observability | Validates: quickstart V18

### Public edge and the gateway trust boundary *(added 2026-09-16)*

Spec `FR-DEMO-019` makes edge traversal part of **acceptance**, not deployment. These tasks gate
Phase 13, and provisioning is the scaffold's longest-lead dependency — start it early, because every
sample flow passes locally right up until it has to cross a boundary that does not exist.

**Status 2026-09-16** — T226–T230a and T232 were implemented in commit `1f8d312`. Paths differ from the
originals as recorded below: the edge lives in `build/infra/frontdoor/`, and APIM policy is split into a
cross-cutting `global.inbound.xml` plus one file per audience rather than a single `identity.xml` — one
policy per audience is what makes "the surface decides the authorization model" structural, since there
is then no shared branch in which the customer path could read a role claim.

**Status 2026-09-17** — the edge scaffold was audited against the twelve edge/gateway requirements and
three gaps were closed. They strengthen T227, T228 and T237 rather than adding tasks, so no task id
changed state:

1. **Routing was prose.** `/api/{audience}/v1/views/...` → .NET and everything else → RagCore lived in
   `contracts/README.md` and in T227's description, enforced by nothing. It is now
   `build/infra/apim/apis.json` — five APIs, two backends, each naming the manifest it routes to. A
   misrouted view does not fail loudly: it reaches a service that serves the audience but not the
   route and returns a 404 indistinguishable from a client error.
2. **The OpenAPI documents were emitted but never imported.** T234–T236 produce five generated
   documents; nothing said which API imported which. Each API now names its source document, the
   generator that produced it, and `handWritten: false` — asserted, along with the converse: a
   document the contract workflow emits and no API imports is a surface nobody routed.
3. **The rate boundary was per-IP only.** `FR-OPS-005` is per *organisation*, and counting by IP
   throttles the wrong callers — one organisation behind one NAT is one IP. Each audience policy now
   applies `rate-limit-by-key` and `quota-by-key` on the **derived** `X-Idp-Tenant-Id`, after
   identity derivation, because a budget keyed on anything a caller supplies is one a caller escapes.

Proven by `ragcore/tests/security/test_edge_topology.py` and
`dotnet/tests/Synthia.ArchitectureTests/ApimRoutingTests.cs`, with seven planted violation classes in
`build/scripts/verify-architecture-guards.sh`.

**These tasks define committed configuration; they do not provision it.** Acceptance still requires a
deployed environment (`FR-DEMO-019`, `SC-DEMO-001`), and T256 remains the gate. Provisioning is tracked
separately under *Azure provisioning* below (T227a, T227b) together with the certificate issuance it
depends on (T233e, T233f) — the longest-lead items in the scaffold, and the ones every sample flow
passes without right up until it has to cross a boundary that does not exist.

- [X] T226 Define the **Front Door + WAF** public edge in `build/infra/frontdoor/` — the single public entry point for all three audiences, WAF in prevention mode with a documented managed rule set, origin reaching APIM over Private Link so neither APIM nor the containers are **publicly reachable** — Boundary: edge | Validates: Spec §FR-DEMO-019, Plan §Platform Environment
- [X] T227 Define **APIM** as the trust boundary in `build/infra/apim/` — terminates the public edge, routes `/api/{customer,staff,workload}/v1/...` to the correct deployable, and is the **only** network path to either container — Boundary: gateway | Validates: Spec §FR-DEMO-004a, Contracts §README rule 4
- [X] T228 Implement **identity derivation at APIM** in `build/infra/apim/global.inbound.xml` (cross-cutting) and `build/infra/apim/{customer,staff,workload}.v1.xml` (one per audience) — validates the Entra token once and emits the closed `X-Idp-*` contract of **exactly five values**: `X-Idp-Tenant-Id`, `X-Idp-Principal-Id`, `X-Idp-Roles` (complete set, canonical order), `X-Idp-Credential-Class`, `X-Idp-Client-Surface`. **Audience is not a header** — it is the route prefix APIM matched, so a caller cannot promote themselves by supplying one. **Neither deployable parses a token**; both consume the contract — Boundary: identity | Validates: Constitution P-I, P-II, Spec §FR-IDENT-011, Contracts §README
- [X] T229 Implement **trusted tenant, audience and role propagation** from the derived header contract through both deployables in `ragcore/src/ragcore/api/middleware/identity.py` and `dotnet/src/Synthia.Api/Middleware/IdentityContextMiddleware.cs`, so tenant and roles reach every layer from trusted context and from nowhere else — Boundary: identity | Validates: Spec §FR-IDENT-002, §FR-DEMO-010
- [X] T230 Implement **rejection of client-supplied authority headers** at APIM and, as defence in depth, at both deployables — any inbound `X-Idp-*` header arriving from a client is stripped at the gateway, and a deployable receiving one that did not come from APIM refuses the request rather than trusting it — Boundary: identity | Validates: Spec §FR-IDENT-002, §SC-DEMO-003b, Constitution P-I
- [X] T230a [P] Write a test in `ragcore/tests/security/test_gateway_provenance.py` and `dotnet/tests/Synthia.ContractTests/GatewayProvenanceTests.cs` asserting a request carrying a **well-formed but self-supplied** `X-Idp-*` header set is refused — the shape a real bypass takes, and the case a naive negative test misses. Refused **on provenance, before any header is parsed**, so a better-formed forgery fares no better — Boundary: identity | Validates: Spec §SC-DEMO-002, §SC-DEMO-003b, §FR-IDENT-012

### Platform resource access *(added 2026-09-16)*

- [X] T231 [P] Implement the **Redis transient cache** abstraction in `ragcore/src/ragcore/infrastructure/cache.py` — reached by managed identity, **every entry carries a TTL**, and the type exposes no API that could persist an authority record or a durable decision. Redis is **transient only**; it is never a source of truth and no sample flow reads it — Boundary: cache | Validates: Constitution P-IV, Plan §Platform Environment
- [X] T232 [P] Bind **Key Vault** to both deployables in `build/docker/containerapps/` — secrets surfaced as references resolved at the point of use, **never** as environment variables holding values, and never baked into an image — Boundary: configuration | Validates: Spec §FR-DEMO-012
- [X] T233 Assign **managed identity and Azure RBAC** per deployable in `build/infra/identity/managed-identities.json` — one identity each, **plus one for APIM**, with data-plane role assignments named per resource. Rights come from role assignment on the resource, **not** from a credential the application holds, so they are centrally revocable and visible without reading application configuration. Sets are **deliberately unequal**: the monolith is read-only (ADR-0001) and holds no Service Bus, SignalR, AI Search or model role, so a write path added to it by mistake fails at the platform rather than succeeding quietly. PostgreSQL and Redis are recorded as **not RBAC** — database-level role and access policy respectively — because writing either as a role assignment deploys cleanly and then cannot connect — Boundary: identity | Validates: Plan §Authentication, Spec §SC-DEMO-003, ADR-0001
- [X] T233a Grant the **APIM identity** Key Vault read in `build/infra/identity/managed-identities.json` — APIM reads the gateway client certificate as itself, so without this there is no certificate on the backend connection, ingress rejects the handshake and **every application request fails**. Guarded by `check-edge-path.sh`, because the failure lands in a different file and a different resource from everything it breaks — Boundary: identity | Validates: Spec §FR-IDENT-012, §SC-DEMO-003

### Gateway provenance certificate *(added 2026-09-16)*

The application half of the APIM-to-backend hop. Network placement alone is not sufficient
(`FR-IDENT-012`): internal ingress admits everything already inside the environment, and for a
backend that consumes the `X-Idp-*` contract as authoritative, reachability *is* the ability to
assert any organisation and any role.

- [X] T233b Enforce **gateway provenance** in both deployables — `dotnet/src/Synthia.Api/Middleware/GatewayProvenanceMiddleware.cs` and `ragcore/src/ragcore/api/middleware/provenance.py`, each running **before** identity, validating the ingress-forwarded certificate hash against a required allow-list. The request is **refused, not sanitised**: stripping the headers and continuing returns success to an attacker and leaves the attempt indistinguishable from an ordinary unauthenticated call. An empty allow-list **fails the process at start** — an unconfigured vault fails loudly, an unconfigured allow-list fails silently by accepting forged identity — Boundary: identity | Validates: Spec §FR-IDENT-012, §SC-DEMO-003b
- [X] T233c Require the client certificate at **ingress** in `build/docker/containerapps/*.yaml` — `clientCertificateMode: require`, so ingress itself sets `X-Forwarded-Client-Cert` and a caller cannot forge it. `accept` is not sufficient: it forwards a certificate when one is offered and nothing when one is not, making an unauthenticated caller indistinguishable from a correctly configured one — Boundary: identity | Validates: Spec §FR-IDENT-012
- [X] T233d Define **expiry alerting** in `build/infra/monitoring/gateway-certificate-expiry.json` — Key Vault lifetime action at 45 days, `CertificateNearExpiry` paging at 30 (Azure fixes this and offers no setting), `CertificateExpired` at Sev0. Expiry is the **residual risk of the pinned-version rotation strategy** and is a misleading outage: health probes are exempt from provenance, so every replica stays green while serving nothing — Boundary: operations | Validates: Spec §FR-IDENT-012
- [ ] T233e **Issue the gateway client certificate into Key Vault** and register it as an APIM certificate entity referenced by `certificate-id` — **never by thumbprint**, which changes on rotation and makes the policy silently stop attaching a certificate at all. Pin the Key Vault version so APIM's four-hour auto-sync cannot rotate it out from under the backend allow-list unattended — Boundary: identity | Validates: Spec §FR-IDENT-012
- [ ] T233f Set the certificate hash allow-list on both deployables — `EdgeTrust__GatewayCertificateThumbprints` and `SYNTHIA_EDGE_GATEWAY_CERTIFICATE_THUMBPRINTS`. Rotation is an **overlap and the order is the control**: widen the allow-list on both deployables *before* repointing APIM, per `docs/runbooks/rotate-gateway-certificate.md`. The reverse order is a total outage — Boundary: identity | Validates: Spec §FR-IDENT-012

### Azure provisioning *(added 2026-09-16)*

Everything above **defines** committed configuration. Nothing above **provisions** it, and the spec
makes traversal of the real deployed path part of acceptance (`FR-DEMO-019`, `SC-DEMO-001`) —
configuration review explicitly does not substitute. These are the scaffold's longest-lead items.

- [ ] T227a Provision **Front Door + WAF, APIM and the Container Apps environment** in a deployed environment from `build/infra/` — including the Private Link connection from Front Door to APIM, the `front-door-id` and `gateway-client-certificate-id` named values, and the Event Grid system topic and action group backing `build/infra/monitoring/` — Boundary: platform | Validates: Spec §FR-DEMO-019, §SC-DEMO-001
- [ ] T227b Apply the **role assignments** from `build/infra/identity/managed-identities.json`, and create the PostgreSQL database-level principals and the Redis access policy, which are **not** role assignments — Boundary: identity | Validates: Spec §SC-DEMO-003

### OpenAPI contract emission *(added 2026-09-16)*

**Status 2026-09-17** — T234–T238 were audited against the emission requirements and the artifacts
they produced. The tasks were complete as written; the *documents* were not contracts. Five gaps
were closed. They strengthen T234–T238 rather than adding tasks, so no task id changed state. New
task ids **T239a–T239d** record the work that had no task at all.

1. **The .NET documents described nothing.** Every handler returns `IResult`, which the generator can
   infer nothing from, so each operation published a bare `200: OK` with no schema, no parameters and
   no error responses — a document that named the routes and described none of them. The routes now
   declare their success body and the RFC 9457 error set (`ContractResponses.Returns<T>()`), and the
   paging, sorting and filtering parameters are published from the endpoint's **own** `QueryWhitelist`,
   moved onto the route as metadata and read by the binder through `QueryBinding.WhitelistOf`. One
   declaration, read twice; restating the fields in a transformer would have fixed the document and
   introduced the drift the generated-contract rule exists to prevent.
2. **Both stacks published an error contract the services do not send.** RagCore's document declared
   FastAPI's `HTTPValidationError` for 422 while `problems.py` returned RFC 9457; the .NET documents
   declared no error at all. Both now declare `ProblemDetails`/`ProblemContract` at
   `application/problem+json`, and `openapi_validate.py` fails a build where any non-2xx response is
   anything else.
3. **`servers: [{"url": "http://localhost/"}]` was published.** The test host's address, in a
   committed contract — configuration material describing a deployment (spec FR-DEMO-012) that also
   differs between the machine that emits and the machine that verifies. Stripped, and the document
   is now versioned `v1` rather than by the assembly version, which moves on a patch release changing
   no route.
4. **Emission was not deterministic and nothing checked.** The .NET emitter wrote unsorted keys and
   `Environment.NewLine`; RagCore's wrote platform line endings. Every gate downstream compares bytes.
   Both are canonical now, and CI emits **twice** and requires byte-identical output — a single
   emission always looks deterministic.
5. **`/realtime/negotiate` was registered twice.** `customer/routes.py` served a 501 while
   `negotiate.py`'s 200 won the OpenAPI path entry, so the published document disagreed with the
   running service about a route that exists. The duplicate is gone; `negotiate.py` owns it (T124).

The audit also corrected the disclosure policy. `tenantId`, `roles` and `audience` were forbidden by
**name, anywhere** — which blocked read models from reporting the organisation an audit record
concerns, the field a staff reviewer opens it for, and which a rename would have satisfied without
closing any channel. The rule is now positional: forbidden in a parameter or a request body on every
audience, permitted in a response, with `tenantId` as a **query** parameter on the **staff**
documents named as the one exception (contracts §README). Proven by
`build/scripts/verify-contract-guards.sh`, which plants eleven violation classes and asserts the
staff narrowing is *accepted*.

- [X] T234 [P] Emit the **customer** audience OpenAPI document from the running services — FastAPI for RagCore, the built-in generator for .NET Minimal APIs — written to `build/contracts/customer.v1.openapi.json` — Boundary: API contract | Validates: Spec §FR-DEMO-013
- [X] T235 [P] Emit the **staff** audience OpenAPI document to `build/contracts/staff.v1.openapi.json` — Boundary: API contract | Validates: Spec §FR-DEMO-013
- [X] T236 [P] Emit the **workload** audience OpenAPI document to `build/contracts/workload.v1.openapi.json`. **One document per audience; a merged document is prohibited** — it would let a customer-facing client discover the staff and workload surfaces — Boundary: API contract | Validates: Contracts §README rule 5
- [X] T237 Publish **versioned OpenAPI artifacts** from CI in `.github/workflows/contracts.yml` — emitted on every build, versioned by API version and commit, and attached to the build rather than committed by hand — Boundary: CI | Validates: Spec §FR-DEMO-013
- [X] T238 Implement **CI contract validation** in `.github/workflows/contracts.yml` — contract tests run against the **emitted** documents, not hand-written copies, and a route whose emitted shape stops matching its declared contract **fails the build** rather than surfacing at a client — Boundary: CI | Validates: Spec §SC-DEMO-011
- [X] T239a Declare the **request and response schemas** on both stacks so the emitted documents describe what the services accept and return — `.NET` through `Synthia.Api/Contracts/ContractResponses.cs` and the query-whitelist metadata in `Synthia.Api/Querying/QueryDeclaration.cs`, `RagCore` through per-router `problem_responses(...)` and an explicit `ProblemDetails` model. **No schema is duplicated to produce OpenAPI**: the application contract is the source, and where the generator could not see a parameter the endpoint's own whitelist was moved to where both the binder and the document read it — Boundary: API contract | Validates: Spec §FR-DEMO-013, Contracts §README
- [X] T239b Make emission **deterministic on every platform** — sorted keys and bare line feeds in `dotnet/tests/Synthia.ContractTests/OpenApiEmissionTests.cs` and `ragcore/scripts/emit_contracts.py` — and gate it in CI by emitting **twice** and requiring byte-identical output. A single emission always looks deterministic, and every gate downstream compares bytes — Boundary: CI | Validates: Spec §SC-DEMO-011
- [X] T239c Implement **publishability validation** over the emitted artifacts in `build/scripts/openapi_validate.py` — no secret or configuration material, no client-suppliable tenant/role/audience, RFC 9457 error contracts throughout, and no `servers` block or assembly version. One validator for both stacks reading `build/policy/openapi-disclosure.json`; the authority rule is **positional**, with the staff `tenantId` narrowing as its one named exception — Boundary: CI | Validates: Spec §FR-DEMO-012, §FR-IDENT-002, Constitution P-I, Contracts §README rule 1
- [X] T239d Implement the **breaking-change approval register** in `build/contracts/approved-breaking-changes.json`, honoured by `build/scripts/openapi_diff.py --approved` — an approval quotes the finding verbatim, names a person, gives a reason and a client migration, and **expires**. No environment variable and no commit-message keyword bypasses the gate. Proven in both directions by `build/scripts/verify-contract-guards.sh`, which also asserts an expired or differently-worded approval does not apply — Boundary: CI | Validates: Spec §SC-DEMO-011

**Checkpoint**: Configuration fails fast; images are digest-pinned, non-root and read-only; the edge and gateway exist and derive identity; every audience emits a validated contract.

---

## Phase 11: Architecture and security test foundation *(Stage 11)*

**Goal**: Complete the enforcement surface and seed the inert reference operations.

- [X] T153 Implement the governance catalogue and deterministic treatment policy in `ragcore/src/ragcore/governance/catalogue.py` — treatment assigned from the catalogue, **never** from model output — Boundary: Governance | Validates: Spec §FR-AGENT-004
- [X] T154 Implement the control gate in `ragcore/src/ragcore/governance/gate.py` evaluating Knowledge, Ability and Security as independent conditions where none averages away another and Knowledge may withhold but never authorize — Boundary: Governance | Validates: Spec §FR-AGENT-005
- [X] T155 Seed the four inert reference operations in `ragcore/src/ragcore/governance/fixtures.py` — one per treatment, `is_reference_fixture=true`, no external effect, excluded from production configuration — Boundary: Governance | Validates: Spec §FR-SCOPE-004, §FR-SCOPE-006
- [X] T156 [P] Unit tests for the treatment policy in `ragcore/tests/unit/test_treatment_policy.py` asserting treatment comes from the catalogue entry and is unaffected by any model-supplied value — Boundary: Governance | Validates: Spec §FR-AGENT-004
- [X] T157 [P] Unit tests for the atomic claim and idempotency key in `ragcore/tests/unit/test_claim.py` covering first-claim-wins, already-claimed, expired and cancelled — Boundary: Work | Validates: Spec §FR-EXEC-004
- [X] T158 Write the full authorization matrix test in `dotnet/tests/Synthia.AuthorizationTests/RoleMatrixTests.cs` covering every role combination against every operation, including the empty intersection — Boundary: authorization | Validates: Spec §SC-AUTHZ-001
- [X] T159 [P] Write a test in `dotnet/tests/Synthia.AuthorizationTests/NoImpliedPrivilegeTests.cs` asserting `administrator` never implies `technician` — Boundary: authorization | Validates: Spec §FR-AUTHZ-003
- [X] T160 [P] Write a test in `ragcore/tests/authorization/test_role_change_midflight.py` asserting a role change neither rewrites a recorded decision nor cancels authorized work — Boundary: authorization | Validates: Spec §FR-AUTHZ-011
- [X] T161 [P] Write tenant isolation tests in `dotnet/tests/Synthia.TenantIsolationTests/` asserting no read path returns another organisation's data and a foreign resource returns 404 — Boundary: tenant isolation | Validates: Spec §SC-IDENT-002
- [X] T162 [P] Write an aggregate leakage test in `dotnet/tests/Synthia.TenantIsolationTests/AggregateLeakageTests.cs` asserting no count, ranking or distribution reveals a single organisation's contribution — Boundary: tenant isolation | Validates: Spec §FR-IDENT-010
- [X] T163 [P] Write adversarial retrieval tests in `ragcore/tests/isolation/test_cross_tenant_retrieval.py` asserting the tenant filter cannot be evaded by crafted input — Boundary: Retrieval | Validates: Spec §FR-IDENT-009
- [X] T164 [P] Write a test in `ragcore/tests/governance/test_no_elevation.py` asserting no catalogue entry can be created or activated with `requires_elevation = true` — Boundary: Governance | Validates: ADR-0004
- [X] T165 [P] Write a test in `ragcore/tests/governance/test_fixtures_excluded.py` asserting reference fixtures are absent from production configuration and never counted as UC-01..UC-12 — Boundary: scaffold scope | Validates: Spec §FR-SCOPE-007
- [X] T166 Write hard-failure tests in `ragcore/tests/security/test_hard_failures.py` — one per item in Principle VIII, each failing when its protection is removed — Boundary: cross-cutting | Validates: Stage 11 gate

**Status 2026-09-17** — Phase 11 completed. Three notes on how the tasks landed, so the differences
between what they say and what exists read as decisions rather than drift:

1. **T153's treatment policy already existed**, in `governance/policy.py`, which is where it belongs —
   the task named one file for two things. What was genuinely missing was the catalogue *type*, and
   its absence was a live defect: `OperationCatalogue.lookup` returned a raw database row whose
   treatment column is `default_treatment` and whose roles are an array of text, while
   `assign_treatment` reads `entry.treatment` and `entry.accepted_roles`. The production path would
   have failed on an attribute inside the execution path. `governance/catalogue.py` is now where a
   row becomes a validated `CatalogueRecord`, and the repository returns one.
2. **T154's Knowledge/Ability/Security conditions did not exist.** The gate evaluated treatment,
   decision and roles — which is the *security* condition alone. `governance/conditions.py` adds the
   other two, with the rule expressed structurally rather than asserted: every condition answers a
   boolean, the combiner is a conjunction, and there is nowhere to put a weight without deleting a
   type. Knowledge exposes `withholds` and no `authorizes`. The gate checks it **before** the
   treatment branches, so an ungrounded proposal cannot be put in front of a human to approve.
3. **T155's fixtures enforce their own exclusion.** `reference_fixtures(environment)` raises in
   production rather than relying on a runbook step. It decides whether rows are *installed*, never
   what a row *means* — no treatment, role or entitlement varies by environment, and
   `test_fixtures_excluded.py` asserts that separately, because "exclude the fixtures in production"
   is one careless step away from "relax the gate in development".

**Checkpoint**: Every hard failure has a test that fails when its protection is removed. **Scaffold complete.**

---

## Phase 12: Golden path A — `AUTO` execution *(Stage 12)*

**Goal**: Prove the full machine end to end with no human in the loop: propose → gate → execute → verify → audit — and prove the gate also refuses, by demonstrating `NOT_ALLOWED`.

**Independent test**: Drive the `AUTO` reference operation from a chat turn to a verified outcome with a complete actor chain, and drive the `NOT_ALLOWED` reference operation to a recorded refusal.

- [X] T167 [P] [US1] Implement the session lifecycle use case in `ragcore/src/ragcore/application/sessions.py` including the triage gate — a work record commits only when a genuine problem is articulated — Boundary: Session | Validates: Spec §FR-SESS-003
- [X] T168 [US1] Implement case creation at the triage gate in `ragcore/src/ragcore/application/cases.py`, anchoring each session to exactly one case — Boundary: Integration—ServiceNow | Validates: Spec §FR-EXT-002
- [X] T169 [P] [US1] Implement hybrid retrieval in `ragcore/src/ragcore/retrieval/hybrid.py` combining a dense leg with a weighted, load-bearing sparse lexical leg — Boundary: Retrieval | Validates: Plan Stage 12
- [X] T170 [P] [US1] Implement cost-gated rerank in `ragcore/src/ragcore/retrieval/rerank.py` reranking a small top-k above a minimum floor — Boundary: Retrieval | Validates: Plan Stage 12
- [X] T171 [P] [US1] Implement confidence and margin in `ragcore/src/ragcore/retrieval/confidence.py` using absolute score plus top-1-minus-top-2, thresholds as global constants defined **only in this module**, with both comparisons `>=` so a value exactly equal to its threshold passes (plan Stage 12), plus unit tests asserting the boundary in both directions — Boundary: Retrieval | Validates: Spec §FR-AGENT-014, §FR-AGENT-015
- [X] T172 [P] [US1] Implement the embedding path in `ragcore/src/ragcore/retrieval/embedding.py` embedding the symptom or description field only — Boundary: Retrieval | Validates: Plan Stage 9
- [X] T173 [US1] Implement graph nodes for intake, classify and ground in `ragcore/src/ragcore/graph/nodes/` where classification never authorizes — Boundary: Agent/RagCore | Validates: Spec §FR-AGENT-002
- [X] T174 [US1] Implement content safety in `ragcore/src/ragcore/integrations/model/safety.py` — inbound before the model, outbound before a response returns, every decision logged with its correlation identifier — Boundary: model egress | Validates: Spec §FR-AGENT-010, §FR-AGENT-013
- [X] T175 [US1] Implement the scope guardrail in `ragcore/src/ragcore/graph/nodes/guardrail.py` declining non-ITSM requests and routing unanswered IT questions to vendor fallback — Boundary: Agent/RagCore | Validates: Spec §FR-SCOPE-009, §FR-SCOPE-010
- [X] T176 [US1] Implement `POST /api/customer/v1/sessions` and `.../messages` with SSE streaming in `ragcore/src/ragcore/api/customer/sessions.py` — Boundary: Customer API | Validates: Contracts §customer-api
- [X] T177 [US1] Implement the execution leg and verification stage in `ragcore/src/ragcore/execution/executor.py` recording `server_confirmed`, `client_attested` or `contradicted` — Boundary: Tool Execution | Validates: Spec §FR-AGENT-008
- [X] T178 [US1] Implement audit writing in `ragcore/src/ragcore/application/audit.py` capturing requester, approver, executor, method, organisation and result — Boundary: Audit | Validates: Spec §FR-AUDIT-001
- [X] T179 [US1] Implement the escalation path in `ragcore/src/ragcore/application/escalation.py` placing the request on the ServiceNow queue with transcript, candidates and reason, and telling the user **why** — Boundary: Integration—ServiceNow | Validates: Spec §FR-FALL-002, §FR-FALL-010
- [X] T180 [P] [US1] Implement the Sessions read module in `dotnet/src/Modules/Synthia.Modules.Sessions/` over `vw_session_summary_v1`, `vw_session_message_v1`, `vw_session_step_v1` — Boundary: Session (read) | Validates: Contracts §read-views
- [X] T181 [P] [US1] Implement customer view endpoints in `dotnet/src/Synthia.Api/Endpoints/CustomerViews.cs` with cursor pagination and whitelisted sort — Boundary: Customer API | Validates: Contracts §customer-api
- [X] T182 [P] [US1] Implement the chat feature in `apps/web/projects/customer-features/chat/` consuming the SSE stream with accessible live-region announcement — Boundary: presentation | Validates: Spec §FR-SURF-011
- [X] T183 [P] [US1] Implement the handoff notice in `apps/web/projects/customer-features/handoff/` stating plainly that a human will take the request — Boundary: presentation | Validates: Spec §FR-FALL-007
- [X] T184 [US1] Implement `PUT` and `DELETE /api/customer/v1/messages/{messageId}/feedback` in `ragcore/src/ragcore/api/customer/feedback.py` — an idempotent replace of the signal, owner-scoped so only the session's own user may record against an agent-authored message — Boundary: Customer API | Validates: Spec §FR-SESS-009, §FR-SESS-010, §FR-SESS-011
- [X] T185 [P] [US1] Implement the feedback read path in `dotnet/src/Modules/Synthia.Modules.Sessions/` over `vw_message_feedback_v1`, exposing aggregate figures retained independently of the underlying signals — Boundary: Session (read) | Validates: Spec §FR-SESS-012, §FR-SESS-014
- [X] T186 [P] [US1] Implement the feedback control in `apps/web/projects/customer-features/chat/feedback/` as a keyboard-operable binary signal announced to assistive technology, with the current state visible — Boundary: presentation | Validates: Spec §FR-SESS-009, §SC-SESS-003
- [X] T187 [P] [US1] Write a test in `ragcore/tests/governance/test_feedback_no_influence.py` asserting feedback reaches no authorization, governance treatment, retrieval scope or execution path — Boundary: Governance | Validates: Spec §FR-SESS-013
- [X] T188 [P] [US4] Implement the clarification interrupt node and `POST .../answers` in `ragcore/src/ragcore/graph/nodes/clarification_interrupt.py` and `api/customer/answers.py` — Boundary: Agent/RagCore | Validates: Spec §FR-INTR-004
- [X] T189 [P] [US1] Governance test in `ragcore/tests/governance/test_auto_path.py` asserting the `AUTO` reference operation reaches execution without any human gate and with treatment from the catalogue — Boundary: Governance | Validates: Stage 12 gate
- [X] T190 [P] [US1] Governance test in `ragcore/tests/governance/test_not_allowed_path.py` asserting the `NOT_ALLOWED` reference operation is refused at the gate, never surfaced to a human as an approvable proposal, and recorded as a denial in audit — Boundary: Governance | Validates: Spec §SC-SCOPE-002, §FR-AUDIT-003
- [X] T191 [P] [US1] Injection containment test in `ragcore/tests/integration/test_injection_containment.py` asserting injected instructions in retrieved content produce at most a proposal and never reach execution — Boundary: Agent/RagCore | Validates: Stage 12 gate
- [X] T192 [P] [US1] End-to-end golden path test in `ragcore/tests/e2e/test_auto_golden_path.py` asserting a verified outcome and a complete actor chain — Boundary: cross-cutting | Validates: Stage 12 gate

**Status 2026-09-17** — Phase 12 completed. Five notes on how the tasks landed, so the differences
between what they say and what exists read as decisions rather than drift:

1. **T171 moved two constants and split one comparison out.** The knowledge thresholds already
   existed, in `governance/conditions.py`, which is one of the two places the plan says they must
   not be. They now live in `retrieval/confidence.py` alone and governance imports them;
   `test_confidence.py` asserts identity rather than equality, so two modules holding `0.45` fails
   rather than passes. The comparison itself is now `clears_thresholds`, because the boundary the
   plan demands be asserted **directly** is not reachable from a pair of scores: the difference of
   two doubles near 0.85 is a multiple of that binade's ulp, and 0.08's stored value is not such a
   multiple. Feeding in scores and hoping for equality would have asserted `>` or `<` at the mercy
   of whichever values somebody picked — the exact accident the plan calls out. The extracted
   predicate takes the thresholds themselves, and the answer is unambiguous.
2. **T173's three nodes are two new modules and one addition.** `intake` and `classify` are their
   own files; `ground` sits beside `retrieve` in `grounding.py`, because the two are one
   question — what did we find, and is it enough — and separating them would have put a file
   boundary through the middle of it. `classify` is deliberately redundant: the gate re-reads the
   catalogue and re-assigns the treatment, so deleting the node would change what a user is told
   and nothing about what is permitted. That redundancy is the point — a classification the gate
   *trusted* would be an authorization written by an earlier, cheaper node.
3. **T175's guardrail escalates on "unanswered", not on "ungrounded".** The first implementation
   read the grounding assessment alone and broke the `AUTO` path: an operation acting on platform
   state needs no retrieved knowledge, which is exactly what the gate's
   `KnowledgeCondition.not_required` says. Requiring grounding for both would have withheld every
   operational request on the grounds that no article described it.
4. **T176 needed a run host, and T188 did not get one.** `graph/host.py` compiles the graph once at
   startup and turns a turn into typed events that the transport renders as SSE — the endpoint
   holds no orchestration policy, and the graph layer does not know what SSE is. `POST .../answers`
   is implemented as far as it honestly can be and **returns 501**: the interrupt node, its payload
   contract and the bounded answer exist and are tested, but wiring a resume against a graph the
   process may not host would be a route that appears to work and silently drops the answer.
5. **T184 exposed a live contract defect.** `SendMessageRequest` and `AnswerRequest` were declared
   with `body` and `answer` in `platform-core`, while the emitted OpenAPI has said `content` since
   Stage 6. No client could have discovered that without sending a turn and reading a 422. The
   TypeScript now matches the artifact, which is the authority.

**Checkpoint**: Golden path A validated — the machine works end to end without a human, and refuses what it must. `AUTO` and `NOT_ALLOWED` demonstrated.

---

## Phase 13: Golden path B — asynchronous platform integration *(Stage 13)*

**Goal**: Prove the platform's integration seams end to end on **inert** fixtures — a request entering
at the public edge, becoming durable state, crossing the deployable boundary through the outbox and
the bus, being acted on by the workload leg, and returning to the client as a notification, with one
correlation identifier and one organisation binding intact throughout.

*Replaced 2026-09-16. The approval and consent tasks that stood here proved product workflow against a
fixture. They are **not lost**: the behaviour remains specified in spec `FR-INTR-*` and User Stories 2
and 3, and is deferred under `FR-DEMO-016`. Tasks T208–T211 and T216 were **kept** — take-over,
cancellation, the staff read modules and the concurrency test are session and read-side behaviour, not
approval behaviour.*

**Every task in this phase is driven through the deployed edge** (Front Door → WAF → APIM →
Container Apps). A run against a deployable directly does not satisfy `FR-DEMO-019`, however green it
looks. Phase 13 therefore **depends on T226–T230a**.

**Independent test**: Drive all three flows in `contracts/sample-flows.md` through the deployed edge and
confirm the nine Stage 13 validation gates in plan.md.

### Reference fixtures and the inertness guard

- [ ] T239 [P] [US6] Seed the **sample-flow reference operations** in `ragcore/src/ragcore/governance/fixtures.py` — inert, `is_reference_fixture=true`, `requires_elevation=false`, producing **no external effect** and excluded from production configuration — Boundary: Governance | Validates: Spec §FR-DEMO-014, §FR-SCOPE-005
- [ ] T240 [P] [US6] Write an inertness guard in `ragcore/tests/e2e/test_sample_flows_are_inert.py` asserting no sample flow reaches an external system, a model, the retrieval index or the cache, and that **no sample flow is presented as product capability** on any surface, and that **0 of UC-01 through UC-12** are implemented or stood in for — Boundary: scaffold honesty | Validates: Spec §FR-DEMO-014, §FR-DEMO-015, §SC-DEMO-012, §SC-DEMO-013

### Flow 1 — Customer API

- [ ] T241 [US6] Implement `POST /api/customer/v1/sample-flows/round-trip` in `ragcore/src/ragcore/api/customer/sample_flows.py` — accepts no tenant, role or audience parameter, derives organisation from trusted context, opens the durable record and returns the correlation identifier — Boundary: Customer API | Validates: Spec §FR-DEMO-001, §FR-DEMO-005, Contracts §sample-flows
- [ ] T242 [US6] Implement `GET /api/customer/v1/sample-flows/round-trip/{id}` in the same module as the **client state refresh**, returning the outcome the workload leg persisted — the **read back** of FR-DEMO-005 — Boundary: Customer API | Validates: Spec §FR-DEMO-001, §FR-DEMO-005

### Flow 2 — Staff API

- [ ] T243 [US6] Implement `GET /api/staff/v1/sample-flows/records` in `dotnet/src/Synthia.Api/Endpoints/StaffSampleFlows.cs` reading **`vw_*_v1` only**, with the target organisation resolved from the platform object being read and never from the request — Boundary: Staff API | Validates: Spec §FR-DEMO-002, §SC-DEMO-007, Contracts §read-views
- [ ] T244 [P] [US6] Write a test in `dotnet/tests/Synthia.IntegrationTests/BaseTableDeniedTests.cs` asserting the monolith's database principal **cannot** read a base table — the refusal comes from PostgreSQL, not from application code — Boundary: read contract | Validates: Spec §FR-DEMO-002, ADR-0003

### Flow 3 — Workload API

- [ ] T245 [US6] Implement `POST /api/workload/v1/sample-flows/execute` in `ragcore/src/ragcore/api/workload/sample_flows.py` — app-only, carrying **no customer-organisation authority of its own**, resolving its tenant from the durable work record, claiming atomically and recording an outcome with **no external effect** — Boundary: Workload API | Validates: Spec §FR-DEMO-003, §FR-DEMO-014

### Flow 4 — Service-to-service

- [ ] T246 [US6] Implement `POST /api/customer/v1/sample-flows/service-hop` in `ragcore/src/ragcore/api/customer/sample_flows.py` reaching the workload boundary **through APIM**, app-only, and returning what the callee reports about the caller's identity — Boundary: service boundary | Validates: Spec §FR-DEMO-004
- [ ] T247 [US6] Write the **bypass negative suite** in `ragcore/tests/security/test_no_direct_route.py` asserting a request presented straight to a deployable fails across every audience — including one carrying a **well-formed but self-supplied gateway header contract** — and that no pod-to-pod route is reachable — Boundary: service boundary | Validates: Spec §FR-DEMO-004a, §SC-DEMO-003a, §SC-DEMO-003b

> **T230a and T247 overlap deliberately, and the split is the point.** Both refuse a well-formed
> self-supplied `X-Idp-*` set; both cite `SC-DEMO-003b`. T230a poses the attack **in process**, against
> the real pipeline, and runs on every commit — it is fast, needs no Azure, and catches a middleware
> regression the day it lands. T247 poses it **against the deployed topology** and catches what no
> in-process test can: an ingress misconfigured to `accept`, a network path that should not resolve,
> a certificate that is not actually required. Neither subsumes the other, and collapsing them would
> either make the fast check need a deployment or let the deployed check stand in for one.

### Flow 5 — Service Bus

- [ ] T248 [US6] Wire the sample flow onto the bus end to end in `ragcore/workers/resume_worker.py` — dispatcher publishes, consumer claims and executes — reading authority **only** from the durable record and never from the message — Boundary: messaging | Validates: Spec §FR-DEMO-007
- [ ] T249 [P] [US6] Write an idempotency test in `ragcore/tests/idempotency/test_sample_flow_duplicate.py` asserting the same bus message delivered twice produces **exactly one** effect — Boundary: messaging | Validates: Spec §SC-DEMO-009

### Flow 6 — SignalR notification

- [ ] T250 [US6] Publish the sample-flow completion notification in `ragcore/src/ragcore/notifications/sample_flow.py` carrying **no authority-bearing value**; the client learns the outcome by reading back through T242, not from the payload — Boundary: realtime | Validates: Spec §FR-DEMO-008, Contracts §notifications
- [ ] T251 [P] [US6] Write a test in `ragcore/tests/integration/test_notification_is_a_leaf.py` asserting the flow reaches an **identical outcome with no client connected** — Boundary: realtime | Validates: Spec §SC-DEMO-010

### Flow 7 — Persistence and outbox

`FR-DEMO-005` is the persistence half — a write, a read back, and a concurrent write resolving to
exactly one outcome. The write and read back are T241 and T242 on the customer flow; T252a is the
concurrent leg. `FR-DEMO-006` is the outbox half, in T252 and T253.

The concurrent leg is asserted **again** here even though `ragcore/tests/concurrency/test_optimistic.py`
already covers optimistic concurrency at the persistence layer. That suite proves the conditional
update behaves; this one proves the property survives the whole sample flow through the deployed path,
where two requests race across replicas rather than two sessions racing in one process. The first can
pass while the second fails.

- [ ] T252a [US6] Demonstrate the **concurrent write** in the sample flow — two simultaneous requests against the same durable record in `ragcore/tests/concurrency/test_sample_flow_concurrent_write.py`, asserting exactly **one** resolves to an effect and the loser is told it lost rather than made to wait. **Nothing blocks and nothing locks**: the loser returns promptly with a conflict, which is the property a distributed lock would regress by hanging instead of failing — Boundary: persistence | Validates: Spec §FR-DEMO-005
- [ ] T252 [US6] Wire the sample flow's state change and its outbox row into **one transaction** in `ragcore/src/ragcore/application/sample_flows.py`, so the two are durable together or not at all — Boundary: messaging | Validates: Spec §FR-DEMO-006
- [ ] T253 [P] [US6] Write a crash test in `ragcore/tests/integration/test_sample_flow_outbox_crash.py` inducing a failure between the state change and the publish, asserting **0 messages lost and 0 effects duplicated** — Boundary: messaging | Validates: Spec §SC-DEMO-008

### Cross-cutting proofs

- [ ] T254 [P] [US6] Write a tenant-isolation test in `ragcore/tests/isolation/test_sample_flow_isolation.py` asserting a flow scoped to one organisation returns **0 rows** belonging to another, **including after the asynchronous hop** — Boundary: tenant isolation | Validates: Spec §SC-DEMO-006
- [ ] T255 [P] [US6] Write a correlation-continuity test in `ragcore/tests/integration/test_sample_flow_correlation.py` asserting one identifier is recoverable across both deployables and the asynchronous hop — Boundary: observability | Validates: Spec §SC-DEMO-005
- [ ] T256 [US6] Write the **edge-traversal end-to-end suite** in `ragcore/tests/e2e/test_sample_flows_through_edge.py` driving all three flows through the deployed Front Door → WAF → APIM path and asserting **0 are accepted on a direct-to-deployable or locally hosted run** — Boundary: cross-cutting | Validates: Spec §FR-DEMO-019, §SC-DEMO-001

### Retained from the previous Stage 13 — session and read-side behaviour, not approval

- [ ] T208 [P] [US5] Implement take-over in `ragcore/src/ragcore/application/takeover.py` as an authenticated state transition resolving concurrently to a single owner — Boundary: Session | Validates: Spec §FR-INTR-013
- [ ] T209 [P] [US5] Implement `POST /api/staff/v1/work/{workItemId}/cancel` in `ragcore/src/ragcore/api/staff/work.py`, permitted at every suspension point before claim — Boundary: Work | Validates: Spec §FR-INTR-014
- [ ] T210 [P] [US5] Implement the Audit, Governance and Tenancy read modules in `dotnet/src/Modules/` over `vw_audit_event_v1`, `vw_governance_catalogue_v1`, `vw_tenant_v1` and the reporting rollup — Boundary: read contract | Validates: Contracts §read-views
- [ ] T211 [P] [US5] Implement Mission Control and Synthia Admin in `apps/web/projects/staff-features/{mission-control,admin}/` with module visibility by role — Boundary: presentation | Validates: Spec §FR-SURF-003
- [ ] T216 [P] [US5] Concurrency test in `ragcore/tests/concurrency/test_concurrent_takeover.py` asserting two simultaneous take-overs resolve to one owner — Boundary: Session | Validates: Spec §FR-INTR-013

**Checkpoint**: Golden path B validated — all three sample flows complete **through the deployed edge**,
a duplicate delivery produces one effect, the notification is a leaf, the organisation binding survives
the asynchronous hop, and a gateway bypass fails. **The scaffold is complete when the SC-DEMO group is
met.**

---

## Phase 15: Integrations Service foundation *(Stage 15)*

**Goal**: A third deployable that starts, is reachable only through APIM, proves its own identity and
configuration, and emits its own contract — **carrying no connector yet**.

**Runs after Phase 13 and before Phase 14.** Task and stage numbers are append-only and never reused,
so ordering is stated rather than inferred from the integer.

- [X] T257 Create the Python project in `integrations/pyproject.toml` with a committed `integrations/uv.lock` — PEP 621, `requires-python = ">=3.12"`, Ruff selection `E, F, B, I, UP, S, PTH, SIM, ASYNC, DTZ, N` with the formatter authoritative, and strict type checking. **A separate project from `ragcore/`: separate lockfile, separate virtual environment, and neither imports the other** — Boundary: repository | Validates: Constitution §Python baseline, Plan §Structure Decision
- [X] T258 Create the package skeleton under `integrations/src/integrations/` — `api/{workload,middleware}/`, `application/`, `domain/`, `policy/`, `catalogue/`, `credentials/`, `connectors/`, `mcp/`, `execution/`, `messaging/`, `persistence/`, `observability/`, `config/`, `egress/`, plus `integrations/workers/` and `integrations/tests/`. **`domain/` imports nothing outside the standard library** — Boundary: layering | Validates: Plan §Project Structure
- [X] T259 [P] Implement typed configuration in `integrations/src/integrations/config/settings.py` using Pydantic Settings — every secret exposed as a `*_secret_name` field holding a **name, never a value**, with **startup validation that fails the process** rather than degrading — Boundary: configuration | Validates: Spec §FR-INTEG-017, Constitution §Configuration
- [X] T260 [P] Implement structured logging and OpenTelemetry in `integrations/src/integrations/observability/` — constant message templates, traces and metrics exported, **no secret, token, credential or cross-organisation value in any log or span** — Boundary: observability | Validates: Spec §FR-INTEG-024, Constitution P-VIII
- [X] T261 [P] Implement correlation middleware in `integrations/src/integrations/api/middleware/correlation.py` — accept `X-Correlation-Id` only when well formed, generate when missing or invalid, echo on every response, bind to the logging scope and the OpenTelemetry context. **W3C Trace Context; a custom propagation header MUST NOT replace it** — Boundary: observability | Validates: Spec §FR-INTEG-024, Constitution P-VIII
- [X] T262 [P] Implement RFC 9457 problem responses in `integrations/src/integrations/api/middleware/problems.py` — `application/problem+json` with `type`, `title`, `status`, `detail`, `instance`, `correlationId`; **internal exception detail never reaches a client** — Boundary: errors | Validates: Contracts §integrations-api, Constitution §Validation and errors
- [X] T263 Implement gateway provenance and identity-contract middleware in `integrations/src/integrations/api/middleware/{provenance,identity}.py` — provenance validated **before** identity against a required certificate-hash allow-list that **fails the process at start when empty**; the service **consumes only the closed `X-Idp-*` contract and MUST NOT parse a token**; a request carrying a caller-supplied contract is **refused, not sanitised** — Boundary: identity | Validates: Spec §FR-INTEG-015, Constitution P-I
- [X] T264 [P] Implement health endpoints in `integrations/src/integrations/api/health.py` — `/health/live` process-only with no dependency checks; `/health/ready` covering the durable store, the message transport and the secret store. **Readiness MUST NOT depend on any external customer system** — Boundary: operations | Validates: Spec §FR-INTEG-026, Constitution §Health
- [X] T265 Implement the composition root in `integrations/src/integrations/config/composition.py` — builds every adapter and binds it to the port it implements; FastAPI `Depends` resolves from it and constructs nothing itself — Boundary: composition | Validates: Constitution §Dependency injection, Plan §Composition roots
- [X] T266 [P] Implement typed outbound HTTP in `integrations/src/integrations/egress/http.py` — pooled client lifetime, a shared resilience policy distinguishing transient from non-transient failure, and an **explicit timeout on every outbound call**. `HttpClient`-equivalent ad-hoc clients MUST NOT be constructed — Boundary: egress | Validates: Spec §FR-INTEG-027, Constitution §Resilience
- [X] T267 [P] Implement persistence bootstrap in `integrations/src/integrations/persistence/engine.py` — async engine over the `integration` schema, plus read-only accessors for published `vw_*_v1` views. **No write path to any `platform` base table exists** — Boundary: persistence | Validates: Spec §FR-INTEG-018, Constitution P-V
- [X] T268 Implement OpenAPI emission in `integrations/scripts/emit_contracts.py`, producing `build/contracts/integrations/workload.v1.openapi.json` from the **running service** with sorted keys and bare line feeds so two emissions are byte-identical — Boundary: contracts | Validates: Spec §FR-INTEG-025, §FR-DEMO-013
- [X] T269 Create `build/docker/integrations.Dockerfile` — multi-stage, non-root, shell-less where possible, **base image pinned by digest**, read-only root filesystem preferred, no package manager in the production image — Boundary: containers | Validates: Constitution §Containers
- [X] T270 [P] Create `build/docker/containerapps/integrations.yaml` — internal ingress, HTTP health probes bound to T264, explicit resource limits, 25-second drain, secrets surfaced as **references** never as environment variables holding values — Boundary: containers | Validates: Constitution §Containers, Spec §FR-DEMO-012
- [X] T271 Add the Integrations managed identity to `build/infra/identity/managed-identities.json` and **remove RagCore's Key Vault role for connector secrets** — the role is withdrawn, not duplicated. Doing this in Stage 15 rather than Stage 16 is deliberate: nothing can come to depend on it in the meantime — Boundary: identity | Validates: Spec §FR-INTEG-016, §FR-DEMO-026
- [X] T272 Add the `integrations` backend and the `/api/workload/v1/integrations/...` API entry to `build/infra/apim/apis.json` — resolved by the **longest-matching-path** rule already proven by `/views`, sharing `workload.v1.xml`, with the same mutual-TLS backend credential and its recorded exemption — Boundary: gateway | Validates: Contracts §integrations-api, Spec §FR-INTEG-011
- [X] T273 Require a **distinct application role** for the Integrations audience in `build/infra/apim/workload.v1.xml`, so a generic workload-audience caller cannot drive connectors merely by being one — Boundary: identity | Validates: Spec §FR-INTEG-011, Constitution P-II
- [X] T274 Add the Integrations CI pipeline in `.github/workflows/` — lint, format, strict type check, tests, contract emission through all five gates, image build. **A third pipeline, not a branch of RagCore's** — Boundary: CI | Validates: Constitution §Quality gate
- [X] T275 Extend `build/scripts/check-boundaries.sh` to **three** deployables — asserting `ragcore ↛ integrations` and `integrations ↛ ragcore` as imports, that no shared Python package exists between them, and that the monolith references neither — Boundary: layering | Validates: Plan §Dependency direction, Constitution P-V
- [X] T276 [P] Write architecture tests in `integrations/tests/architecture/` asserting `domain/` imports only the standard library, no module outside `config/composition.py` instantiates a concrete adapter, and **no import of `ragcore` exists anywhere** — Boundary: layering | Validates: Constitution §Required test categories

**Checkpoint**: The service starts, fails fast on invalid configuration, answers both health endpoints, is reachable **only** through APIM, and emits a contract passing all five gates. It contains no connector.

> **Slice stopped here — 2026-09-18.** The boundary slice is delivered: T257–T265 and T269, T270,
> T274–T276. `ruff`, `ruff format`, `mypy --strict` and `pytest` all pass in `integrations/`
> (15 tests), and `build/scripts/check-boundaries.sh` passes and was **verified to fail on a planted
> violation**.
>
> **Still open in this phase, and deliberately so** — each needs a subsystem this slice does not
> build:
>
> | Task | Why it is not done |
> |---|---|
> | T266 | Typed outbound HTTP. Nothing calls outward yet; building the egress layer before a connector exists would be the speculative abstraction Principle VI forbids |
> | T267 | Persistence bootstrap. Needs the `integration` schema, which Phase 16 creates |
> | T268 | OpenAPI emission. The workload routes land with T305/T306; emitting a document for a surface with no operations would publish an empty contract that reads as "this surface has none" |
> | T271, T272, T273 | Azure identity, APIM backend and the distinct application role — deployment configuration, applied against a subscription rather than the repository |
>
> **One honest scoping note on T264.** The health *endpoints* and their semantics are delivered and
> tested: liveness is process-only, readiness is an AND across registered platform probes, neither
> discloses anything, and an external customer system can never be one. **No infrastructure probe is
> registered yet**, because the durable store, message transport and secret store are bound by T267,
> T298 and T284. A registry with no probes reports ready, which is the honest answer for a process
> that has nothing to wait on — and becomes wrong the moment a dependency exists, which is why
> registration is each subsystem's obligation rather than the health module's.

---

## Phase 16: Connector migration out of RagCore *(Stage 16)*

**Goal**: Move every external-system path into the Integrations Service, and **prove RagCore can no
longer reach one**.

**The relocated modules are moves, not rewrites** — see §Relocated 2026-09-18 for the old→new
traceability. Their original tasks stay `[X]`; these tasks cover the relocation and what it changes.

- [X] T277 Create the `integration` schema and the `integration_job` table in `ragcore/migrations/versions/` — one Alembic project, two schemas, one gated job. `integration_job` carries `job_id` PK, `work_item_id`, `operation_id`, `tenant_id` not null, `catalogue_id` text not null, `catalogue_version` int not null, `parameters` jsonb not null, `status` enum (`created`, `dispatched`, `completed`, `failed`, `expired`), `expires_at` inheriting the work item's window, and `version` — Boundary: persistence | Validates: Data-model §Integration job, ADR-0003
- [X] T278 Add the four result columns to `integration_job` — `result_status` enum (`executed`, `failed`), `result_verification` enum (`server_confirmed`, `client_attested`, `contradicted`), `result_execution_id` uuid null, `result_recorded_at` timestamptz null — and **a column-scoped `GRANT` giving the Integrations principal `UPDATE` on those four columns and nothing else**. This is the first migration to review as DDL rather than prose — Boundary: security | Validates: Spec §FR-INTEG-020, Constitution P-VIII
- [X] T279 [P] Create the `integration` schema tables — `connector` (`connector_id` PK, `kind` enum `native`/`mcp`, `base_endpoint` not null, `is_reference_fixture` bool not null), `connector_binding` (composite PK `catalogue_id`+`catalogue_version`, `connector_id` FK, `operation_path`, `signing_profile` **a Key Vault reference, never a value**, `idempotency_policy` enum), `execution_record`, plus the service's own outbox — Boundary: persistence | Validates: Data-model §Connector registry
- [X] T280 [P] Create the `execution_record` table with `unique(idempotency_key)` — **that uniqueness is idempotency boundary 2** — plus `job_id`, `tenant_id`, `connector_id`, `catalogue_id`, `catalogue_version`, `external_reference` null, `outcome` enum (`succeeded`, `failed`, `refused_unentitled`, `refused_unregistered`, `refused_window`, `unreachable`), `normalized_result` jsonb null, `correlation_id` not null. Append-only: a second attempt is a second row — Boundary: persistence | Validates: Data-model §Execution record, Spec §FR-INTEG-022
- [X] T281 Create the Integrations database principal in `ragcore/migrations/versions/` — write on `integration`, read on published views, **no grant on any `platform` base table** and no grant on any non-result column of `integration_job` — Boundary: security | Validates: Spec §FR-INTEG-018, ADR-0007
- [ ] T282 Publish a versioned view exposing the operation instruction for the Integrations Service to read, added to `ragcore/src/ragcore/persistence/views.py` and recorded in `contracts/read-views.md` as a **third reader** of a contract written for the monolith alone — Boundary: read contract | Validates: ADR-0003, ADR-0007
- [X] T283 Write a grant test in `integrations/tests/security/test_job_grants.py` asserting an attempted write to `catalogue_id`, `catalogue_version`, `parameters` or `tenant_id` on `integration_job` is refused **by PostgreSQL, not by application code** — an executing service able to rewrite its own instruction could run an operation governance never authorized — Boundary: security | Validates: Spec §FR-INTEG-020, Constitution P-VIII
- [X] T284 Relocate per-organisation credential resolution to `integrations/src/integrations/credentials/` **with its port declaration** — ports belong to the consuming module, and the consumer is now this service. One path from an entitlement row to a usable secret; a missing reference is a refusal, never a fallback — Boundary: credentials | Validates: Spec §FR-INTEG-017, Constitution P-V
- [X] T285 [P] Implement catalogue and entitlement reads in `integrations/src/integrations/catalogue/` over the published views — resolving capabilities **per organisation**, with no global capability set — Boundary: Tool Execution | Validates: Spec §FR-INTEG-002, §FR-INTEG-004
- [X] T286 [P] Implement the connector registry in `integrations/src/integrations/catalogue/registry.py` — resolving a catalogue identifier and version to its connector, endpoint, signing profile and idempotency policy. **The destination comes from here and never from parameters, model output or retrieved content** — Boundary: Tool Execution | Validates: Spec §FR-INTEG-003, §FR-EXT-018
- [X] T287 Implement the execution-time re-check in `integrations/src/integrations/policy/` — organisation active, work authorized and uncancelled and inside its window, organisation entitled, capability registered, **catalogue version matching what was authorized**, capability reached past the gate. **It assigns no treatment and performs no role intersection**; prior catalogue retrieval is not standing permission — Boundary: policy | Validates: Spec §FR-INTEG-019, §FR-INTEG-008, Constitution P-III
- [X] T288 [P] Relocate the ServiceNow adapter to `integrations/src/integrations/connectors/servicenow/` — idempotent write-backs, queue-and-replay on outage, tenant stamping on every record. Behaviour unchanged from T129 — Boundary: Integration—ServiceNow | Validates: Spec §FR-EXT-004, §FR-EXT-007
- [X] T289 [P] Relocate the Microsoft Graph adapter to `integrations/src/integrations/connectors/graph/` — token caching, throttling compliance and retry inside the adapter. Behaviour unchanged from T130 — Boundary: Integration—Graph | Validates: Spec §FR-EXT-008
- [X] T290 [P] Relocate the OneLogin adapter to `integrations/src/integrations/connectors/onelogin/` as an MCP-backed target system. Behaviour unchanged from T132 — Boundary: Tool Execution | Validates: ADR-0005
- [X] T291 [P] Relocate the Duo adapter to `integrations/src/integrations/connectors/duo/` as an MCP-backed target system. Behaviour unchanged from T132 — Boundary: Tool Execution | Validates: ADR-0005
- [X] T292 Relocate the MCP client to `integrations/src/integrations/mcp/client.py` — **the `discover`/`invoke` type separation must survive the move intact**, because it is what enforces "discovery is not entitlement" rather than a convenience. There is no overload taking an advertised tool — Boundary: Tool Execution | Validates: Spec §FR-EXT-014, §FR-INTEG-005
- [X] T293 [P] Relocate boundary contract validation to `integrations/src/integrations/execution/normalization.py` — provider output size-checked and contract-checked at the boundary, **treated as data**: never an instruction, destination, identity, organisation or source of authority. Malformed, oversized or off-contract output is rejected rather than passed inward — Boundary: integration | Validates: Spec §FR-INTEG-023, §FR-EXT-017, §FR-EXT-021
- [X] T294 Implement the execution leg in `integrations/src/integrations/execution/executor.py` — derives the idempotency key from organisation, work item and operation (**derived, never random**), invokes the connector, records the attempt. **It refuses to run without a `PROCEED` re-derived from durable state**; a serialised gate outcome is a model-free but still *asserted* authority and MUST NOT be accepted — Boundary: execution | Validates: Spec §FR-INTEG-019, §FR-INTEG-021, Constitution P-I
- [X] T295 Split RagCore's execution leg in `ragcore/src/ragcore/execution/executor.py` — invocation and verification move to the Integrations Service; **`ExecutionReport.may_report_resolution` stays in RagCore**. A service that both acted and judged its own success would report an attestation as a confirmation — Boundary: Agent/RagCore | Validates: Spec §FR-INTEG-009, Constitution P-III
- [X] T296 **Remove** `ragcore/src/ragcore/integrations/` **except `model/`**, together with its connector settings and secret references in `ragcore/src/ragcore/config/` and its connector dependencies in `ragcore/pyproject.toml` and `uv.lock`. `integrations/model/` **stays**: model egress and content safety are reasoning, not integration — Boundary: Agent/RagCore | Validates: Spec §FR-INTEG-016, ADR-0007
- [X] T297 Write an architecture test in `ragcore/tests/architecture/test_no_connector_in_ragcore.py` asserting **no adapter, connector, MCP client or external-provider client remains in RagCore**, and that no module outside `integrations/model/` holds an external endpoint — Boundary: layering | Validates: Spec §FR-DEMO-021, §FR-EXT-011

> **Slice checkpoint — the boundary removal (2026-09-18).** Delivered **T289–T291, T295–T297**.
> RagCore no longer owns connector execution, and the claim is now enforced rather than asserted.
>
> **What moved.** The Graph adapter is `integrations/connectors/graph/`, rewritten to take its
> destination from the connector registry rather than from settings — the relocation removed the
> last place an address came from configuration instead of the registry. OneLogin and Duo are
> `integrations/connectors/{onelogin,duo}/`, still a name each, which is the ADR-0005 evidence and
> is now asserted rather than described: a test fails if either module grows a client.
>
> **What was removed from RagCore.** `ragcore/integrations/` holds `model/` and nothing else. Gone:
> the Graph adapter, the MCP client, OneLogin, Duo, `credentials.py`, `EntitlementCredentials`,
> `IntegrationSettings` and the `mcp` dependency (removed from `pyproject.toml` **and** the lock —
> a library in the lock file is a library an import can reach). `http.py` and `validation.py` were
> **not** deleted: they are the shared outbound transport and the boundary-validation rule, not
> connectors, and they moved to `ragcore/egress/` because leaving them under a package named
> `integrations` kept suggesting connectors belonged there.
>
> **The four connector ports are bound to `None`, and that is the design.** A stand-in would be
> worse than a connector: it is an object with a method to call, so the first caller to call it
> would have re-created the in-process path — and every test would keep passing, because a stand-in
> returns successfully. `test_scaffold.py`'s assertion was **inverted** to require the absence.
>
> **T295 split the verification workflow, not the verification.** The *call* is a server-side read
> against an external system and moved with everything else; `ExecutionReport.may_report_resolution`
> — the **conclusion** — stayed. `ExecutionLeg` now carries the reported outcome instead of
> computing one, so RagCore cannot upgrade an attestation into a confirmation. A stale comment in
> the Integrations executor claiming verification ran in RagCore was the code disagreeing with
> constitution Principle III; the code is now what the constitution says.
>
> **Gates.** RagCore **1229 passed** (ruff, `mypy --strict` clean, 17 migration tests against real
> PostgreSQL); Integrations **77 passed**, up from 69. `check-boundaries.sh` green.
>
> **The build-time guard was widened and then proven by mutation.** Four new checks: a connector
> import, a connector client dependency, a customer-system host, and connector-credential
> resolution. Each was verified by planting a violation and observing it caught. **The host check
> failed that verification the first time** — it required a `base_url`-shaped assignment near the
> host and missed `BASE_URL` on capitalisation alone. It now matches the host itself. A guard that
> passes because its pattern is broken is worse than no guard, and only the mutation found it.
>
> **This is necessary and not sufficient, and the task list should keep saying so.** Every check
> here is an absence assertion, and an absence assertion passes equally where the path exists and
> merely has no caller yet. **T311 is the proof that matters** — it *attempts* the connection and
> observes it refused at the network layer and at Key Vault. Until T311 runs against a deployment,
> the claim rests on code inspection rather than on observed authorization.
>
> **Also still open**: T282, T283 (the `integration_job` grant test — still the top item, still
> unproven by exercise), T298 (queue provisioning), T304–T322.


**Checkpoint**: RagCore holds no connector code and no connector credential. Every relocated adapter passes its suite in its new home. The column-scoped grant refuses a write to a non-result column.

> **Slice stopped here — 2026-09-18 (second slice).** Delivered: **T266–T268, T271–T273** (completing
> Phase 15) and **T284–T288, T293, T305, T306** from Phases 16–17 — the catalogue and registry, the
> access and policy re-check, per-organisation credentials, the ServiceNow connector, result
> normalization, and both synchronous endpoints.
>
> **RagCore now calls the Integrations Service through APIM** via
> `ragcore/src/ragcore/platform_clients/integrations.py`, and **the direct ServiceNow path is gone**:
> `ragcore/src/ragcore/integrations/servicenow/` is deleted, `case_system` is bound to `None`, and
> `check-boundaries.sh` fails the build if either returns — **verified by planting the import**.
>
> Gates: `ruff`, `ruff format`, `mypy --strict`, **34 tests** in `integrations/`; **1247 tests** in
> `ragcore/` including the migration up/down suite against real PostgreSQL; all **six** OpenAPI
> documents publishable.
>
> **Two decisions taken here that were not in the task text**, both recorded because Principle X
> makes an unrecorded decision one that gets re-litigated:
>
> 1. **`vw_tenant_entitlement_v1` and `vw_connector_credential_ref_v1`** (migration `0021`).
>    `tenant_entitlement` was deliberately unpublished because it carries `credential_reference`.
>    That reasoning stands — what changed is that the **access check and the credential lookup are
>    two different questions**, so the first is published without the second, and the credential view
>    is granted to the Integrations principal **alone**. The monolith cannot select from it.
> 2. **RagCore's Key Vault role narrowed from vault-wide to `secret:synthia-ragcore-*`.** While it
>    was vault-wide, RagCore could read every organisation's connector credentials — the exact blast
>    radius ADR-0007 exists to shrink. The role is **withdrawn, not duplicated**.
>
> **Still open in Phases 16–17**, each needing a subsystem this slice does not build: T277–T283
> (`integration_job` and its column-scoped grant — blocked on the ADR-0007 residual), T289–T292
> (Graph, OneLogin, Duo, MCP relocations), T294–T297 (execution leg split and the full RagCore
> connector removal), T298–T304 and T307–T322 (the asynchronous seam and the eight boundary proofs).
>
> **One honest scoping note.** `check-boundaries.sh` currently names **ServiceNow only**. Graph, MCP,
> OneLogin and Duo are still in RagCore because their relocations are not scheduled in this slice;
> listing them now would fail the build on unscheduled work, and a guard that fails for
> work-in-progress is a guard somebody comments out. **Each relocation adds its name in the same
> change that removes its code.**

---

## Phase 17: Golden path C — the Integrations boundary proven *(Stage 17)*

**Goal**: Prove the boundary rather than describe it — spec `FR-DEMO-020`–`FR-DEMO-028`, measured by
`SC-DEMO-015`–`SC-DEMO-023`.

**Every flow is driven through the real deployed path** (`FR-DEMO-019`) and acts only on the inert
reference connector. Configuration review does not substitute for traversal.

### Wiring the two communication paths

- [X] T298 [US6] Provision `synthia-integration-commands` and `synthia-integration-results` as **separate queues**, with role assignments granting RagCore send-on-commands and listen-on-results, and the Integrations Service listen-on-commands and send-on-results — **and nothing more**. `synthia-triggers` is **not** reused: mixing lifecycles makes dead-letter triage ambiguous — Boundary: messaging | Validates: Spec §FR-INTEG-013, Contracts §triggers
- [X] T323 [US6] Write the APIM routing and direct-route proofs in `integrations/tests/security/test_apim_routing.py` — asserted from the committed registry: the gateway fronts this service on the workload audience, its path is strictly longer than RagCore's so the most specific prefix wins, the role check is a **prefix match rather than a substring one**, and **exactly one API points at this backend and it is not client-facing**. Complements the runtime refusal in `test_boundary.py`: that half would pass on a deployment where APIM never routed here, and this half would pass on a service that accepted anything — Boundary: gateway | Validates: Spec §FR-INTEG-011, §FR-INTEG-012, §13.4
- [ ] T324 [US6] Wire the worker **processes** and their container definitions — Service Bus receive loops with lock renewal, settlement and graceful drain for `integrations/workers/command_consumer.py` and `ragcore/workers/integration_result_worker.py`, plus the five pre-existing RagCore workers (`outbox_dispatch`, `resume_worker`, `expiry_sweep`, `retention_sweep`, `ingestion_run`), each with a container app that actually runs it. **All seven `main()` functions currently raise `NotImplementedError` by design** and no manifest runs any of them, so nothing consumes any queue in a deployment. This is a **pre-existing platform-wide gap**, not an Integrations one — Boundary: messaging | Validates: Spec §FR-INTEG-013, §FR-EXEC-006, Constitution §Idempotency and messaging
- [X] T325 [US6] Write the **third** Azure identity enforcer in `integrations/tests/security/test_azure_identity.py` — reads `build/policy/azure-identity.json` rather than restating it, scans `integrations/src` and `integrations/workers` for application-owned credential types, connection-string tokens, DSN passwords and settings fields naming a secret value, and asserts the four resources this service must **never** reach leave no trace in its source. Extend RagCore's parity class from two enforcers to three — Boundary: security | Validates: Spec §FR-INTEG-017, §FR-EXT-016, Constitution P-VIII
- [ ] T326 [US6] Add the migration granting the Integrations principal `INSERT` on `platform.audit_event`, **and only INSERT** — it appends the executing-principal record and must not read, amend or delete another actor's entry. **T307 is blocked on this and no task named it** until the analysis found it (X8): the principal holds no grant on the audit table, so `FR-INTEG-024`'s "one audit store, with the Integrations principal as the executing principal" has no path to satisfy. `test_integration_grants.py` currently asserts the refusal, so closing this must change that test deliberately — Boundary: Audit | Validates: Spec §FR-INTEG-024, Constitution P-VIII

> **Remediation — X5, the unexercised grants (2026-09-18).** Delivered **T283**, the item that had
> been top of this list since the asynchronous seam landed. **T326** is new and records the
> prerequisite X8 exposed.
>
> **No test anywhere referenced `synthia_integrations`.** The grants in migrations 0021–0023 were
> written, applied and described in three documents as the control behind `FR-INTEG-020` — but
> nothing had ever attempted a forbidden write and observed it refused. The claim rested on reading
> DDL. `ragcore/tests/security/test_integration_grants.py` now makes it, in **30 tests against a
> real PostgreSQL**.
>
> **`SET ROLE`, not a second connection**, because migration 0021 creates the role `NOLOGIN` — it
> authenticates as a managed identity, so there is no password to connect with and nothing in the
> repository could hold one. `test_set_role_actually_drops_privilege` proves the mechanism before
> anything relies on it: a `SET ROLE` that silently failed would run every refusal assertion as the
> owner, and an absence assertion would then pass while nothing was restricted.
>
> **Two real defects in my own test, both found by running it rather than reading it:**
>
> | Symptom | Cause |
> |---|---|
> | All 24 refusal tests failed | Asserted on `type(error.orig).__name__ == "InsufficientPrivilege"`. SQLAlchemy's asyncpg dialect reports a privilege refusal, a missing table and a wrong column as the **same** `ProgrammingError`. Now matches SQLSTATE `42501`. |
> | The audit test failed on `42703` | My `INSERT` named `audit_event_id`; the column is `audit_id`. **The SQLSTATE check is what refused to let it pass** — on the class-name check it would have "passed" because the column did not exist, reporting the grant as enforced while checking nothing. |
>
> The second is the more important of the two: it is the exact failure mode this task existed to
> remove, reproduced inside the fix for it.
>
> **Proven by widening the grant**, which is the only proof that counts for a refusal:
>
> | Planted in the migration | Result |
> |---|---|
> | `GRANT UPDATE` widened from four columns to the whole row | **5 failed** |
> | `INSERT, DELETE` added on `integration_job` | **2 failed** |
> | `GRANT SELECT ON ALL TABLES IN SCHEMA platform` | **7 failed** |
> | `CREATE` added on the `integration` schema | **1 failed** |
>
> Clean restore to 30 passing. The mixed-column case matters most: nobody writes
> `SET catalogue_id = ...` alone — the realistic shape is a legitimate result write with one extra
> column smuggled alongside, and column privileges reject the statement **whole**, so the permitted
> part does not land either.
>
> **T283 named `integrations/tests/security/test_job_grants.py`; this is in RagCore's suite
> instead.** Recording the deviation rather than making it quietly. These grants are DDL created by
> RagCore's migrations, and RagCore owns every migration (ADR-0003, one Alembic chain). Applying
> them from the Integrations suite means that suite reaching into `ragcore/` for `alembic.ini` and
> the revision files — the cross-tree test coupling rejected for T325 one commit earlier. Without
> it the test would **skip**, and a skipping grant test is precisely the unexercised control T283
> exists to remove. If the path matters more than the coupling, the file moves and the Integrations
> suite gains an Alembic dependency; that is a deliberate trade, not an oversight.
>
> **The audit gap is now asserted rather than merely noted.** A test records that the principal
> **cannot** write `platform.audit_event`, written explicitly as a *known gap* and not as a
> satisfied requirement — so closing **T326** has to change that test on purpose.
>
> **Gates.** RagCore **1289 passed** (was 1259; +30). Ruff, format and `mypy --strict` clean.
>
> **Still open from the analysis**: **X7** (`build/policy/edge-trust.json` and
> `build/infra/monitoring/gateway-certificate-expiry.json` still instruct "BOTH deployables" for
> certificate rotation — three backends share that certificate, and a backend missed stays green
> while refusing every request, because health probes are provenance-exempt), **X8** (now T326),
> **X9**, **X11**, **X12**.


> **Remediation — X6, the unscanned credential surface (2026-09-18).** Delivered **T325**.
>
> **The one deployable holding every organisation's connector credentials was the one whose source
> nothing scanned.** `ragcore/tests/security/test_azure_identity.py` scans `PRODUCTION_ROOTS =
> (ragcore/src, ragcore/workers, ragcore/migrations)` and config globs over `ragcore/**` and
> `build/**`. `integrations/**` appeared in neither. A `ClientSecretCredential` in
> `integrations/src` would have passed every gate in the repository.
>
> **Being on the workload audience does not cover this, and that was the crux of the exchange.**
> The Integrations API *is* reached with a workload token through APIM — true, and tested by T323.
> That rule governs who may **call** the service. These tests govern what the service's own source
> may **contain**, and a hard-coded client secret is equally a violation on an audience nobody can
> reach. The two rules are unrelated; only one of them existed.
>
> **A third enforcer rather than widening RagCore's globs**, matching the pattern
> `azure-identity.json` already documented: each deployable enforces the shared registry itself and
> scans **only its own tree**. Widening RagCore's roots to `*/src` would have had RagCore's suite
> assert on the Integrations tree — the cross-tree coupling ADR-0001 and ADR-0007 exist to prevent,
> created for the convenience of a test. The parity test asserts the new enforcer reads the registry
> **and** scans its own production source, because an enforcer can parse a policy and scan nothing
> while passing exactly as loudly as one that checked every file.
>
> **Two rules in this service are stronger than RagCore's, because they can be.** It constructs
> **no** Azure credential at all — every client takes an injected one — where RagCore permits
> `DefaultAzureCredential` in one module. And it asserts the four resources it must never reach
> (SignalR, AI Search, Foundry, Redis) leave no trace in its source: withholding the role stops the
> call succeeding, but only a source scan stops the client being written, reviewed and merged.
>
> **Fourteen mutations planted, and the first run found two real defects in my own guard.**
>
> | Planted | First result | Cause |
> |---|---|---|
> | `from azure.search.documents.aio import SearchClient` | **MISSED** | `_names_in` collects the names an import *binds* — `SearchClient` — never the module path, so a marker of `search.documents` could not match. Added `_imported_modules_in`. |
> | `from azure.messaging.signalr import SignalRClient` | **MISSED** | The predicate was `startswith`, and vendors put the product name **last**. Only packages named after their product were ever caught. Now containment. |
>
> Both are exactly the vacuous-pass failure this file exists to prevent, and neither was visible by
> reading. All fourteen are caught now, with a clean restore: five credential shapes, a settings
> field, committed configuration, a deliberately broken scan root, and each of the four forbidden
> resources in both `import` and `from ... import` form.
>
> **Also corrected**: `build/policy/azure-identity.json` said "One registry, two enforcers" and
> named only two. That is **X10**, resolved by the same change — the registry now names all three
> and records why the Integrations one mattered most.
>
> **Gates.** RagCore **1259 passed** (was 1256; +3 parity), Integrations **109 passed** (was 93;
> +16). Ruff, format and `mypy --strict` clean on both.
>
> **Still open from the analysis**: **X5** (no test anywhere references the `synthia_integrations`
> database principal, so the column-scoped grant behind `FR-INTEG-020` remains unexercised — this
> is T283 and it is still the top item), **X7** (`edge-trust.json` and
> `gateway-certificate-expiry.json` still say "BOTH deployables" in the rotation instruction, which
> is the green-but-dead failure mode), **X8** (T307 needs an audit-table grant no task names),
> **X9**, **X11**, **X12**.


> **Remediation — the asynchronous seam, X1–X4 (2026-09-18).** A drift analysis found **four tasks
> marked `[X]` whose deliverables did not exist or were never called**. The behaviour now exists and
> is tested; the runtime half is **T324**, above.
>
> **What was actually wrong** — and all four were on the seam the 2026-09-18 slice reported as
> delivered:
>
> | Task | Was marked | Reality found by the analysis |
> |---|---|---|
> | T302 | `[X]` | `IntegrationDispatcher` had **zero callers**. `self._outbox` was assigned and never used, so **no outbox row was written** — the job row alone is an instruction nobody will ever act on. |
> | T302 | `[X]` | `TriggerKind` had no `integration.execute` member, so `outbox_dispatch` would have raised `ValueError` on such a row; and the dispatcher published to one queue with no routing. **RagCore could not publish a command at all.** |
> | T300 | `[X]` | `integrations/workers/command_consumer.py` **did not exist**. |
> | T303 | `[X]` | **Zero references** to `integration.completed`/`failed` anywhere in RagCore. The result consumer did not exist. |
>
> **These were marked complete by me, and the checkpoint above them said the round trip existed.**
> It did not: three of seven legs were missing. Recording it rather than quietly correcting it,
> because a task marked done on work that was not done is the one failure a task list exists to
> prevent — and the same scepticism is owed to every other `[X]` on that slice.
>
> **`integration.execute` is NOT a `TriggerKind`, and that was the key design finding.**
> `TriggerEnvelope` carries `work_item_id`; a command must carry `job_id`. Adding the integration
> kinds to that enum would have made the envelope constructible with one, producing a message that
> deserialises perfectly and is then **refused by the far side's closed field set** — with the cause
> two modules from the symptom. RagCore now has its own `IntegrationCommandEnvelope` and
> `IntegrationMessageKind`, deliberately duplicating the Integrations Service's three-field contract
> rather than sharing a package (constitution Principle VI).
>
> **One outbox, two queues, one dispatcher.** The retry policy and dead-letter story are not
> duplicated — `envelope_from_row` routes on the kind and the publisher routes to the queue, so
> "how many attempts before a human sees it" is still answered in exactly one place.
>
> **RagCore cannot publish a result, and that is enforced twice.** `_queue_for` raises on a result
> kind, and the identity registry grants RagCore Receiver-not-Sender on the results queue. An
> orchestrator that could publish `integration.completed` could fabricate a successful outcome for
> work that never ran — and pairing that forgery with the database write it would also need is
> already denied by revision 0022's column-scoped grant.
>
> **`concluded_from` takes no `kind` argument**, and the omission is the control: a forged
> `integration.completed` naming a job whose row records nothing concludes `PENDING`, not success.
> There is no `Conclusion` member meaning "retry" and the module exports no publisher, so
> `FR-EXEC-006` is enforced by there being nothing to call.
>
> **Gates.** RagCore **1256 passed** (was 1229), Integrations **93 passed** (was 85). Ruff, format
> and `mypy --strict` clean on both. Boundary, edge-path and contract guards green; the Integrations
> contract re-emits byte-identical.
>
> **Eight mutations, eight caught, clean restore** — including replanting the original X1 defect
> (the unused outbox), routing a command to the trigger queue, permitting a result publication,
> swapping `jobId` for `workItemId` in the body, and dropping a settlement entry so a dead-letter
> would silently complete.
>
> **`mypy --strict` caught two things the tests would not have.** Widening
> `envelope_from_row`'s return type made an existing assertion in `test_outbox_crash.py` unsound
> until it narrowed explicitly; and a local look-alike for `IntegrationResult` could not satisfy a
> concrete dataclass, so the result tests now construct the **production type**, which makes drift
> impossible rather than merely unlikely.
>
> **What is still not true.** No queue is consumed in a deployment — seven `main()` functions raise
> and no manifest runs them. That is **T324** and it predates this work: RagCore's five workers have
> been in the same state throughout. The seam is correct and tested in-process; it is not yet live.


> **Slice checkpoint — contracts and the infrastructure boundary (2026-09-18).** Delivered **T298**
> and **T323**, and made **T274** true rather than merely marked.
>
> **T274 was marked complete while the pipeline it describes did not exist.** Its text says the
> Integrations CI covers "contract emission through all five gates". In fact
> `.github/workflows/contracts.yml` emitted from RagCore and .NET only: nothing generated, validated,
> diffed or staleness-checked `build/contracts/integrations/`. The committed artifact was real and
> correct, but no gate would have caught it drifting. All six documents now pass through one
> validator and one comparator. **Recording this rather than quietly fixing it** — a task marked done
> on work that was not done is the failure mode a task list exists to prevent, and the same mistake
> is worth looking for in T271–T273.
>
> **The emitter had a defect that CI would have hidden.** It took a bare positional argument, so the
> `--out <dir>` invocation every other emitter uses wrote a file literally named `--out` and left the
> document unwritten. Wired into the pipeline as it was, the comparison would have diffed a
> directory against itself and passed unconditionally — the exact failure the pipeline exists to
> prevent, one level up. The CLI now matches RagCore's exactly, with `--out` `required`.
>
> **The APIM role check was a substring match.** `Contains("/integrations")` would also fire on a
> RagCore route merely containing the word, demanding the Integrations role to reach a backend that
> is not this service. That direction fails closed, so it would never have surfaced as a security
> finding — it would have surfaced as a RagCore route returning 403 to a correctly-credentialled
> caller, which is harder to attribute and likelier to be "fixed" by deleting the check. It is now a
> prefix match, and T323 asserts it stays one.
>
> **Four role assignments, each one direction on one queue** (`build/infra/messaging/queues.json`).
> RagCore cannot publish a result; the Integrations Service cannot dispatch work to itself. The
> asymmetry is the control: a compromised orchestrator that could publish `integration.completed`
> could fabricate a successful outcome for work that never ran — and pairing that forgery with the
> database write it would also need is already denied by revision 0022's column-scoped grant.
>
> **Queues were declared only inside role scopes before this.** A queue that exists only as a role
> scope is a queue nobody provisions: the assignment deploys cleanly against a namespace with no
> such queue, and the publisher then fails at first use with what reads as an authorization problem.
>
> **Gates.** All six contracts publishable; guard prover green including a new plant against the
> Integrations document; `check-edge-path.sh` green; `check-boundaries.sh` green. The routing guards
> were **proven by mutation** — a substring role check, a removed role check, a shortened route path
> and a planted client-facing route to the connectors were each caught, with a clean restore.
>
> **What is configuration and not yet proof.** Everything here is committed configuration read by
> structural tests. It holds in CI without an Azure subscription, which is the point, but no
> assertion here observes a deployed APIM refusing a direct call. **T320** (mutation-proving
> `verify-edge-guard.sh` for the third deployable) and **T311** (attempting the bypass against a
> deployment) remain the proofs that close that gap, and neither is claimed.
>
> **Also still open**: T282, T283 (the `integration_job` grant test — still the top item), T304–T322.

- [X] T299 [US6] Implement the transactional outbox and result publisher in `integrations/src/integrations/messaging/` — **the service runs its own outbox**; a result row is durable before publication — Boundary: messaging | Validates: Constitution §Idempotency and messaging
- [X] T300 [US6] Implement the command consumer in `integrations/workers/command_consumer.py` — reads `jobId` from the message, loads the job row, **recovers the organisation from that row and from nothing else**, re-checks via T287, executes via T294, writes the execution record, updates the four result columns, publishes the result — Boundary: messaging | Validates: Spec §FR-INTEG-014, §FR-INTEG-018
- [X] T301 [US6] Implement retry and dead-letter behaviour in `integrations/src/integrations/messaging/deadletter.py` — bounded backoff inside the remaining window for pre-execution transient failure; **no retry of a side-effecting operation**; a message outliving its validity window dead-letters rather than executing; **a dead-lettered message carrying authorized work surfaces as a governance failure** in the approved-but-not-executed list with an alert, and recovery is fresh authorization, never replay — Boundary: resilience | Validates: Spec §FR-INTEG-027, Constitution §Idempotency and messaging
- [X] T302 [US6] Implement job dispatch in RagCore — write the `integration_job` row **in the same transaction as the state change**, with its outbox row, then publish `integration.execute` carrying `jobId`, `correlationId` and `kind` and **nothing else** — Boundary: Agent/RagCore | Validates: Spec §FR-INTEG-014, Contracts §triggers
- [X] T303 [US6] Implement the result consumer in `ragcore/workers/` — consume `integration.completed` / `integration.failed`, read the outcome from durable state, update `operation`'s conclusion, resume the graph. **A failure result MUST NOT cause a re-dispatch** — Boundary: Agent/RagCore | Validates: Spec §FR-EXEC-006, §FR-INTEG-027

### The synchronous path and the reference fixture

- [ ] T304 [US6] Implement the inert reference connector in `integrations/src/integrations/connectors/reference/` plus its deployed stub endpoint — **reachable only from the Integrations Service**, producing no real effect, excluded from production configuration, and **never counted as any of UC-01 through UC-12** — Boundary: fixtures | Validates: Spec §FR-DEMO-020, §FR-DEMO-014, Constitution P-IX
- [X] T305 [US6] Implement `GET /api/workload/v1/integrations/catalogue` in `integrations/src/integrations/api/workload/catalogue.py` — takes an opaque `sessionId` or `workItemId` and **never an organisation**; returns `entitled` and `available` as **separate fields** so entitled-but-unreachable is distinguishable from not-entitled; returns **no treatment, no accepted roles and no risk tier** — Boundary: Tool Execution | Validates: Spec §FR-INTEG-011, §FR-EXT-022, Contracts §integrations-api
- [X] T306 [US6] Implement `POST /api/workload/v1/integrations/case-operations` for the inert case-like operation, bound to an opaque identifier — Boundary: Integration—ServiceNow | Validates: Spec §FR-INTEG-012, Contracts §integrations-api

### Observability, audit and isolation

- [ ] T307 [US6] Emit durable audit for every invocation — the actor chain recording who requested, who approved, **the Integrations principal as the executing principal**, by what means, against which organisation, with what result. **One audit store; audit does not fork** — Boundary: Audit | Validates: Spec §FR-INTEG-024, Constitution P-VIII
- [ ] T308 [US6] [P] Emit connector-invocation metrics — attempts, outcomes and duration per connector — in `integrations/src/integrations/observability/metrics.py` — Boundary: observability | Validates: Spec §FR-DEMO-028
- [ ] T309 [US6] [P] Write a trace-continuity test in `integrations/tests/integration/test_correlation_across_seam.py` following **one** correlation identifier across the gateway hop, both queues and all three deployables — Boundary: observability | Validates: Spec §FR-DEMO-027, §SC-DEMO-021
- [ ] T310 [US6] [P] Write tenant-isolation tests in `integrations/tests/isolation/` asserting no catalogue read, execution or execution-record query returns another organisation's data, and that **no code path can omit the organisation filter** — Boundary: isolation | Validates: Spec §FR-INTEG-018, Constitution P-IV

### The eight acceptance proofs

- [ ] T311 [US6] Write the bypass proof in `ragcore/tests/security/test_no_external_reach.py` — **all three observations required**: a direct connection from RagCore to the reference connector fails at the network layer; a connector-credential resolution from RagCore fails at Key Vault; and T297's architecture check passes. **Attempting it is the point** — an absence assertion passes equally where the path exists and simply has no caller yet — Boundary: security | Validates: Spec §FR-DEMO-021, §SC-DEMO-015
- [ ] T312 [US6] Write the synchronous-path proof in `integrations/tests/e2e/test_sync_via_apim.py` — the catalogue read and the inert case operation succeed through the deployed edge, and **fail** by the service's internal address and **fail** when carrying a well-formed but self-supplied identity contract — Boundary: gateway | Validates: Spec §FR-DEMO-022, §SC-DEMO-016
- [ ] T313 [US6] Write the asynchronous-execution proof in `integrations/tests/e2e/test_async_execution.py` — asserting the command on the queue carries `jobId`, `correlationId` and `kind` and **0 other fields**, and that the capability and parameters were read from the job row — Boundary: messaging | Validates: Spec §FR-DEMO-023, §SC-DEMO-017
- [ ] T314 [US6] Write the duplicate-delivery proofs as **two independent tests** — the atomic claim absorbing a duplicate resume trigger in RagCore, and the derived key absorbing a redelivered command in the Integrations Service, each asserting exactly **1** external effect. **Each test must fail when its own boundary alone is removed.** A single end-to-end test passes whenever either mechanism holds and would stay green on the day one silently broke — Boundary: idempotency | Validates: Spec §FR-DEMO-024, §SC-DEMO-018
- [ ] T315 [US6] Write the untrusted-payload proofs as **two assertions** in `integrations/tests/security/test_payload_organisation.py` — a command carrying an out-of-contract organisation field is **refused and dead-lettered with an alert, never processed**; and separately, a valid command whose payload asserts a *conflicting* organisation produces an effect bound to the organisation on the durable record — Boundary: identity | Validates: Spec §FR-DEMO-025, §SC-DEMO-019
- [ ] T316 [US6] Write the credential-reachability proof in `ragcore/tests/security/test_no_connector_secrets.py` — RagCore's identity resolves **0** connector secrets, and a scan of its source, configuration, environment and image finds **0** — Boundary: secrets | Validates: Spec §FR-DEMO-026, §SC-DEMO-020
- [ ] T317 [US6] Write the result-correlation proof in `integrations/tests/e2e/test_result_correlation.py` — a returned result is matched to the work item that originated it, via the `jobId` and the derived key — Boundary: messaging | Validates: Spec §FR-DEMO-027, §SC-DEMO-021
- [ ] T318 [US6] Write the independent-observability proof in `integrations/tests/observability/test_independent_telemetry.py` — the service is a distinct telemetry source, emits metrics for 100% of connector calls, and its execution records answer *what was attempted, against which connector, with what outcome and how long* **without reading RagCore's telemetry** — Boundary: observability | Validates: Spec §FR-DEMO-028, §SC-DEMO-022
- [ ] T319 [US6] Write the degradation proof in `integrations/tests/e2e/test_degraded_mode.py` — with the Integrations Service stopped, conversation, retrieval and guidance still succeed, and a capability requiring an external effect falls back to manual resolution or escalation **visibly**; **0** are reported to a user as completed — Boundary: resilience | Validates: Spec §FR-INTEG-028, §SC-DEMO-023

### Extending the existing edge guard

- [ ] T320 [US6] Extend `build/scripts/check-edge-path.sh` and `build/scripts/verify-edge-guard.sh` to the **third deployable** — the RagCore → Integrations edge is exactly the shape a bypass takes, and this is the check that currently proves APIM is the trust boundary. **A gate nobody has seen fail is a gate whose failure mode is silence**: plant each violation class and assert the guard rejects it — Boundary: gateway | Validates: Spec §FR-DEMO-004a, §SC-DEMO-003a, §SC-DEMO-003b

### Documentation synchronisation

- [ ] T321 [P] Synchronise documentation with what was built — `README.md` and `build/scripts/check-boundaries.sh` both still assert the deployables meet at *"exactly two places"*; `contracts/read-views.md` must record its third reader; `docs/adr/0005` paths are RagCore-relative and stale; `quickstart.md` V20–V28 must match the delivered flows — Boundary: documentation | Validates: Constitution P-X
- [ ] T322 [P] Record the two ADR-0007 residuals once settled — which system-of-record operations are synchronous (settled in Phase 15, before contract freeze) and the job-row result columns with their `GRANT` (settled in T278) — updating `docs/adr/0007-integration-service-boundary.md` §Unresolved — Boundary: documentation | Validates: Constitution P-X

**Checkpoint — the architecture acceptance gate**: all ten flows pass against a deployed environment; RagCore reaches no external system and holds no connector credential; every message carries three fields; both idempotency boundaries are independently load-bearing; one correlation identifier spans three deployables.

> **Slice stopped here — 2026-09-18 (third slice): the asynchronous execution path.** Delivered
> **T277–T281, T292, T294, T299–T303**. The full round trip exists in code: RagCore writes the job
> and dispatches → Service Bus → the Integrations Service recovers the instruction, re-verifies,
> executes and records → Service Bus → RagCore reads the outcome from its own row.
>
> Gates: `ruff`, `ruff format`, `mypy --strict`, **69 tests** in `integrations/`; **1247 tests** in
> `ragcore/` including **17 migration tests against real PostgreSQL** covering the new schema,
> grants, upgrade and downgrade; `check-boundaries.sh` green.
>
> **The command envelope carries three fields and nothing else**, as instructed. Relaxing the closed
> field set was verified to fail **11 tests** — including the consumer test, where the disposition
> flips from `DEAD_LETTER` to `COMPLETE`, meaning a command carrying an organisation would have
> executed. The organisation, the capability, the parameters and the authority all come from the
> durable `integration_job` row.
>
> **ADR-0007's result-column residual is now settled by implementation.** The four columns are
> `result_status`, `result_verification`, `result_execution_id`, `result_recorded_at`, exactly as
> `data-model.md` names them, with `GRANT UPDATE (…4 columns…)` and no `INSERT` or `DELETE`. **ADR-0007
> §Unresolved should be updated to record this.**
>
> **T283 is deliberately NOT marked done, and it is the top remaining item.** The migration applies
> and the grant is written, but **no test yet asserts PostgreSQL refuses a write to `catalogue_id`,
> `parameters` or `tenant_id`**. That refusal is the control behind `FR-INTEG-020`; until a test
> proves it, the claim rests on reading the DDL rather than on exercising it.
>
> **Also still open**: T282 (operation-instruction view), T289–T291 (Graph, OneLogin, Duo
> relocations), T295–T297 (execution-leg split completion and full RagCore connector removal), T298
> (queue provisioning and role assignments), T304–T322 (the reference connector and the eight
> boundary proofs). The graph *resume* on a returned result is wired as far as reading the outcome;
> driving the LangGraph resume from it belongs with T303's remaining half.

---

## Relocated 2026-09-18 — the Integrations Service boundary

**These tasks stay `[X]`. They were completed, and the code they produced is being moved rather than
rebuilt.** Reopening them would misrepresent what was built; the relocation is new work with new IDs.
**No task ID is reused, here or anywhere.**

| Completed task | Produced | Relocated by | Now lives in |
|---|---|---|---|
| T129 | ServiceNow adapter | **T288** | `integrations/connectors/servicenow/` |
| T130 | Microsoft Graph adapter | **T289** | `integrations/connectors/graph/` |
| T131 | MCP client boundary | **T292** | `integrations/mcp/` |
| T132 | OneLogin and Duo adapters | **T290**, **T291** | `integrations/connectors/{onelogin,duo}/` |
| T133 | Typed HTTP clients, resilience, timeouts | **T266** | `integrations/egress/` |
| T134 | Boundary contract validation | **T293** | `integrations/execution/normalization.py` |
| T135 | Entitled-but-unreachable distinction | **T294** | `integrations/execution/` |
| T136 | Adapter tests | **T288**–**T292** | `integrations/tests/` |
| T137 | No-provider-leak test | **T276**, **T297** | Both trees |
| T224 | Key Vault credential-reference resolution | **T284** | `integrations/credentials/` — RagCore keeps its own for platform secrets |

**Not relocated, and deliberately so:**

| Completed task | Produced | Why it stays in RagCore |
|---|---|---|
| T127, T128 | AI Gateway configuration, model adapter | **Model egress is reasoning, not integration.** The Integrations Service has no model access and reaches no AI Gateway |
| T138 | No-direct-model-call test | Guards `integrations/model/`, which stays |
| T223 | Azure AI Search boundary | Retrieval is RagCore's |
| T225, T225a | Shared Azure credential chain, identity registry | Platform-wide. **T271 removes RagCore's connector-secret role from the registry rather than removing the registry** |

**Nothing is retired by this change.** The 2026-09-16 withdrawal retired T193–T218 for a different
reason — a deferred demonstration — and those IDs remain permanently unavailable.

---

## Withdrawn 2026-09-16 — approval and consent workflow tasks

**Withdrawn from the scaffold, not from the platform.** These task IDs are **permanently retired and
MUST NOT be reused**. The behaviour each covered remains specified in spec.md and is deferred under
`FR-DEMO-016`; `FR-DEMO-017` states that the deferral is of a demonstration rather than of a design.
They return with the stage that implements approval, and are listed so their absence reads as a
decision rather than an omission.

| Retired | Covered | Returns with |
|---|---|---|
| T193–T197 | Approval request use case, interrupt node, verdict endpoint, first-valid-verdict-wins, decision notifications | The approval stage |
| T198–T201 | Approvals and Work read modules, staff queue endpoints and UI | The approval stage |
| T202–T204 | Consent interrupt node, consent endpoint, consent prompt UI | The consent stage |
| T205–T207 | Consent-is-not-chat, consent authority, consent golden path | The consent stage |
| T212–T215 | Approval role matrix, checkpoint/resume, expiry, no-refire | The approval stage |
| T217–T218 | Staff verdict contract test, staff approval golden path | The approval stage |

**`FR-DEMO-018` covers the gap in the meantime**: where the gate is unexercised, an operation
requiring a human decision is refused or routed to manual fallback — **never auto-approved**. T256a
below asserts it.

- [X] T256a [P] Write a fail-closed test in `ragcore/tests/governance/test_unexercised_gate_refuses.py` asserting an operation classified `STAFF_APPROVAL` or `END_USER_APPROVAL` is refused or routed to manual fallback and **never auto-approved** while the workflow is unbuilt — Boundary: Governance | Validates: Spec §FR-DEMO-018, §SC-DEMO-014

---

## Deferred — not covered by the two golden paths

Recorded so the omissions are visible rather than assumed. **No tasks are generated for these.**

| Behaviour | Why deferred | Blocked on |
|---|---|---|
| **Desktop script execution** | ADR-0004 open items — script signing and the destructive taxonomy — are unresolved, and §35.4 forbids shipping elevated or destructive endpoint execution until then | ADR-0004 resolution |
| **UC-01 through UC-12** | Stage 14, gated behind both golden paths; no product definitions exist | Product definitions |
| **Ingestion behaviour** | Scaffolded in T077 and T100 as the twelfth context and its worker entry point; no acquisition behaviour is specified in spec.md | A behavioural requirement for Ingestion |

---

## Dependencies & Execution Order

### Phase dependencies

```text
Phase 1 (tooling)
  └─> Phase 2 (contracts + architecture tests)
        ├─> Phase 3 (Angular) ──> Phase 4 (Electron)
        ├─> Phase 5 (.NET)  ─┐
        └─> Phase 6 (RagCore)┴─> Phase 7 (persistence)
                                   └─> Phase 8 (messaging/realtime)
                                         └─> Phase 9 (integrations)
                                               └─> Phase 10 (observability/containers)
                                                     └─> Phase 11 (test foundation)
                                                           └─> Phase 12 (golden path A)
                                                                 └─> Phase 13 (golden path B)
                                                                       └─> Phase 15 (Integrations foundation)
                                                                             └─> Phase 16 (connector migration)
                                                                                   └─> Phase 17 (golden path C)
                                                                                         └─> Phase 14 (use cases, gated)

Phase 10 (edge: T226-T230a) ═════════════════════════════════════╝
  provisioned edge gates Phase 13 AND Phase 17 ACCEPTANCE, not their implementation
```

**Execution order is `1 … 13 → 15 → 16 → 17 → 14`.** Phase and task numbers are append-only and never
reused, so the order is stated rather than inferred from the integer.

**Phase 15 needs only Phases 1–2, 7 and 10** — tooling and boundary checks, PostgreSQL, and the
observability and container baseline. It is **independent of Phases 3–6 and 8**, so it can start as
soon as Phase 10 is done rather than waiting for Phase 13.

### The two communication paths, as task dependencies

```text
SYNCHRONOUS — RagCore → APIM → Integrations
  T272 (APIM backend + routing)
    └─> T273 (distinct app role)
          └─> T305 (catalogue endpoint) ──┐
          └─> T306 (case-operations)    ──┴─> T312 (proof: succeeds via edge,
                                                     fails direct and fails on a
                                                     self-supplied identity contract)

ASYNCHRONOUS — RagCore → Service Bus → Integrations → Service Bus → RagCore
  T277/T278 (integration_job + column-scoped grant)
    └─> T298 (two queues + role assignments)
          ├─> T302 (RagCore writes the job, publishes jobId only)
          │     └─> T300 (Integrations consumes, recovers org from the row, re-checks, executes)
          │           └─> T299 (Integrations outbox publishes the result)
          │                 └─> T303 (RagCore consumes the result; never re-dispatches)
          └─> T301 (retry / dead-letter posture)

NEGATIVE — RagCore MUST NEVER reach an external system
  T271 (Key Vault role REMOVED from RagCore)  ─┐
  T296 (connector code removed from RagCore)  ─┼─> T311 (bypass attempted, observed to fail)
  T297 (architecture test)                    ─┘   T316 (0 connector secrets resolvable)
```

**T271 is deliberately in Phase 15, not Phase 16.** Withdrawing RagCore's connector-secret role
*before* the connectors move means nothing can quietly come to depend on it in the interval.

### Critical path inside the scaffold

```text
T027 (ports) → T103 (repositories) → T114 (outbox) → T117 (resume worker)
T082 → T083 → T084 (durable checkpointer) → T085..T099 (tables) → T101 (views) → T102 (grants)
                                                               → T109/T110 (migration tests)
T105 (retention from terminal state) → T106 (retention sweeper) → T107 (erasure) → T113 (retention tests)
T127 (AI Gateway) → T128 (model adapter) → T174 (content safety)
T153 → T154 → T155 (catalogue → gate → fixtures)
```

**T155 is a hard prerequisite for both golden paths** — without the reference operations there is no
operation to propose, and Phases 12–13 cannot be demonstrated.

**T226–T230a are hard prerequisites for Phase 13** *(added 2026-09-16)*. Spec `FR-DEMO-019` makes edge
traversal part of acceptance, so no Phase 13 task can be *accepted* until Front Door, WAF and APIM are
provisioned and APIM derives identity. Every flow will pass against the deployables long before that —
which is exactly why this is stated rather than assumed. **Start the edge provisioning early.**

**T084 is a hard prerequisite for Phase 13** — until the graph is compiled with the PostgreSQL
checkpointer it suspends only in memory, so no suspension survives a restart and neither
`STAFF_APPROVAL` nor `END_USER_APPROVAL` can be proven durable.

### Critical path through Phases 15–17 *(added 2026-09-18)*

```text
T257 (project) → T258 (skeleton) → T259 (settings) → T265 (composition root)
                                                       → T268 (contract emission)
T269 (Dockerfile) → T270 (container app) → T272 (APIM) → T274 (CI)
T277 → T278 (job table + COLUMN-SCOPED GRANT) → T281 (principal) → T283 (grant test)
                    └─> T298 (queues) → T302 → T300 → T299 → T303   (the async round trip)
T284 (credentials) → T285 (catalogue) → T286 (registry) → T287 (policy re-check) → T294 (executor)
T271 (role removed) → T296 (code removed) → T297 (arch test) → T311 (bypass proof)
```

**T278 is the single most load-bearing task in the three phases.** The column-scoped grant is what
stops the Integrations Service rewriting the instruction it was given; without it, `FR-INTEG-020` and
`FR-DEMO-025` are unprovable, because the protection lives at the database permission boundary rather
than in application code. It is also the task whose exact column list ADR-0007 leaves unresolved, so
**it is blocked on that decision** and should be scheduled first for that reason.

**T287 blocks every execution task.** Nothing may invoke a connector before the execution-time
re-check exists, or the first thing the scaffold proves is an ungoverned call.

### Parallel opportunities

- Phase 1: T002–T006, T008–T012, T014–T016, T018–T021 run in parallel
- Phase 2: T023–T026, T028–T031, T034–T037 run in parallel
- Phases 3 and 4 (clients) are fully parallel with Phases 5 and 6 (backends) once Phase 2 completes
- Phase 7: the table migrations T085–T099 are parallel; T101 and T102 are not
- Phase 7: T106 and T107 (retention, erasure) are sequential; T111 and T113 (their tests) are parallel
- Phase 12: T169–T172 (retrieval pipeline), T180–T183 and T185–T188 are parallel; T184 (feedback
  endpoint) precedes T185 and T186
- Phase 13: T239 and T240 first (fixtures and the inertness guard). The three flow groups — customer
  (T241, T242), staff (T243, T244) and workload (T245) — are parallel. T246 and T247 depend on the
  edge tasks T226–T230a. T248 depends on Phase 8. The cross-cutting proofs T254–T256 depend on all
  three flows. T208–T211 and T216 are parallel throughout and depend on nothing in this phase
  are sequential, then T204–T206 are parallel and T207 is last
- **Phase 15**: T259–T262, T264, T266, T267 are parallel once T258 lands. T269/T270 (containers),
  T271/T272/T273 (Azure and gateway) and T274 (CI) are three independent tracks. T275 and T276
  (guards) are parallel and depend only on T258
- **Phase 16**: T279 and T280 are parallel with each other and with T277/T278. The five connector
  relocations **T288–T292 are fully parallel** — each is a self-contained move of an existing adapter.
  T284–T287 are sequential (credentials → catalogue → registry → policy). T296 and T297 must follow
  every relocation, or the architecture test fails on code that has simply not moved yet
- **Phase 17**: the eight acceptance proofs T311–T318 are **parallel with one another** once the
  wiring (T298–T306) lands, because each observes a different property. T319 (degradation) needs the
  service stoppable, so it runs last. T321/T322 (documentation) are parallel with everything

**The widest parallel front is Phase 16's connector relocations.** Five adapters, five independent
moves, no shared state between them — and each has an existing test suite that travels with it.

---

## Parallel Example: Phase 7 table migrations

```bash
Task: "tenant_mapping migration in ragcore/migrations/versions/"
Task: "chat_session migration in ragcore/migrations/versions/"
Task: "message migration in ragcore/migrations/versions/"
Task: "feedback migration in ragcore/migrations/versions/"
Task: "operation migration in ragcore/migrations/versions/"
Task: "outbox_message migration in ragcore/migrations/versions/"
Task: "idempotency_record migration in ragcore/migrations/versions/"
Task: "ingestion_run migration in ragcore/migrations/versions/"
```

---

## Implementation Strategy

### Scaffold first (Phases 1–11)

166 tasks producing a system that starts, enforces every boundary, and demonstrates nothing. That is
the intent: **Phase 11 ends with a complete enforcement surface and zero product behaviour.** The value
is that every guarantee the platform later depends on is already tested before the first behaviour is
written — including the two the scaffold would otherwise leave to the golden paths to discover: durable
orchestration state (T084) and the removal of data past its retention window (T106, T107).

### Then the golden paths (Phases 12–13)

Golden path A proves the synchronous machine works without a human, and that the gate refuses what it
must. Golden path B proves the seams underneath it — the transaction boundary between a state change
and the message announcing it, the deployable boundary, the organisation binding surviving a hop that
carries no tenant, and the duplicate delivery that at-least-once guarantees will arrive. Together they
demonstrate that the **platform** holds.

*Revised 2026-09-16.* Golden path B previously proved a governed human decision. It no longer does, and
the claim that the two paths exercise all four execution treatments is withdrawn with it: the catalogue
carries all four and classification is deterministic (`SC-SCOPE-002`, amended), but the two
human-decided treatments are not exercised (`FR-DEMO-016`). `FR-DEMO-018` is what stops that gap being
a permission grant — an unexercised gate refuses rather than permits, and T256a asserts it.

### Only then, use cases

Stage 14 remains gated. UC-01 through UC-12 have no definitions, and nothing about them is designed in
this task list.

---

## Notes

- Tests are required, not optional. Write them before the implementation they cover.
- [P] means different files with no incomplete dependency.
- Every task names the architectural boundary it sits on and the requirement it validates.
- No task introduces infrastructure absent from `Synthia-Platform-Specification.md` §9.3.
- The scaffold resolves no use case. Every action-requiring request escalating to manual resolution is
  the expected outcome, not a defect.
- No task in this list is gated on a performance figure.
