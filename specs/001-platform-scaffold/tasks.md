# Tasks: Synthia Platform Engineering Scaffold

**Input**: Design documents from `/specs/001-platform-scaffold/`

**Prerequisites**: [plan.md](./plan.md) (14 stages), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), constitution v3.1.0

**Tests**: REQUIRED. The constitution mandates fifteen test categories and makes them a merge gate.

**Organization**: Phases mirror the plan's stages, in dependency order. **Phases 1–11 are scaffold** and
carry no story label — they are setup and foundational work. **Phases 12–13 are the two architectural
golden paths** and carry story labels. Between them they demonstrate **all four execution treatments**:
`AUTO` and `NOT_ALLOWED` in Phase 12, `STAFF_APPROVAL` and `END_USER_APPROVAL` in Phase 13 — which is
what `SC-SCOPE-002` requires. The twelve business use cases are **not here**; they are Stage 14, gated
behind both golden paths.

## Format: `[ID] [P?] [Story] Description — Boundary: … | Validates: …`

- **[P]**: parallelizable — different files, no incomplete dependency
- **[Story]**: US1–US5 from spec.md, on golden-path phases only
- **Boundary**: the architectural boundary the task sits on or guards
- **Validates**: the requirement, principle or gate the task must satisfy

## Path Conventions

Per plan.md: `apps/web/`, `apps/desktop/`, `dotnet/`, `ragcore/`, `build/`, `docs/`.

---

## Phase 1: Repository and tooling foundation *(Stage 1)*

**Goal**: A monorepo skeleton with both toolchains, CI and boundary enforcement. Nothing runs yet.

- [ ] T001 Create the monorepo skeleton per plan.md in the repository root: `apps/web/`, `apps/desktop/`, `dotnet/`, `ragcore/`, `build/{docker,infra/ai-gateway,scripts}/` — Boundary: repository | Validates: Plan §Project Structure
- [ ] T002 [P] Write root `README.md` describing the two deployables and the no-dependency rule — Boundary: repository | Validates: Constitution P-X
- [ ] T003 [P] Create `docs/adr/README.md` indexing ADR-0001 through ADR-0005 with status — Boundary: documentation | Validates: Constitution P-X
- [ ] T004 [P] Create `dotnet/Directory.Build.props` with `Nullable=enable`, `TreatWarningsAsErrors=true`, `EnableNETAnalyzers=true`, `AnalysisLevel=latest-Recommended`, `EnforceCodeStyleInBuild=true`, `Deterministic=true`, `InvariantGlobalization=true` — Boundary: .NET build | Validates: Constitution §.NET baseline
- [ ] T005 [P] Create `dotnet/Directory.Packages.props` with `ManagePackageVersionsCentrally=true`, pinning EF Core 10, Npgsql, OpenTelemetry, `Http.Resilience`, xUnit, NetArchTest, Testcontainers — Boundary: .NET build | Validates: Constitution §.NET baseline
- [ ] T006 [P] Create `dotnet/.editorconfig` setting IDE0055 and IDE1006 to `error` — Boundary: .NET build | Validates: Constitution §.NET baseline
- [ ] T007 Create `dotnet/Synthia.sln` with stubs for the 11 projects in plan.md — Boundary: .NET solution | Validates: Plan §Complexity Tracking
- [ ] T008 [P] Create `ragcore/pyproject.toml` (PEP 621) with `requires-python >=3.12`, ruff select `["E","F","B","I","UP","S","PTH","SIM","ASYNC","DTZ","N"]`, ruff format authoritative, `[tool.mypy] strict = true` — Boundary: Python build | Validates: Constitution §Python baseline
- [ ] T009 [P] Generate and commit `ragcore/uv.lock` pinning FastAPI, Pydantic, Pydantic Settings, LangGraph, langgraph-checkpoint-postgres, SQLAlchemy, asyncpg, Alembic, alembic_utils, azure-servicebus, azure-identity, httpx — Boundary: Python build | Validates: Constitution §Python baseline
- [ ] T010 [P] Initialise the Angular workspace in `apps/web/` with `tsconfig.base.json` setting `strict`, `strictTemplates`, `noUncheckedIndexedAccess`, `noImplicitOverride` — Boundary: web build | Validates: Constitution §Angular
- [ ] T011 [P] Create `apps/web/eslint.config.js` with library boundary rules: `customer-features` may not import `staff-features` or any application; `design-system` may not import business logic — Boundary: Angular libraries | Validates: Plan Stage 3
- [ ] T012 [P] Initialise the Electron host in `apps/desktop/package.json` with main/preload/renderer builds and strict TypeScript — Boundary: desktop host | Validates: Constitution P-VII
- [ ] T013 Create `build/scripts/check-boundaries.sh` failing on any cross-deployable reference: a `ragcore` string in any `.csproj`, a `Synthia` import in `ragcore/`, or an HTTP client in either targeting the other — Boundary: cross-deployable | Validates: Constitution P-V, ADR-0001
- [ ] T014 [P] Create `.github/workflows/dotnet.yml` running restore, `dotnet build -warnaserror` and every `dotnet/tests/` suite — Boundary: CI | Validates: Constitution §Quality gate
- [ ] T015 [P] Create `.github/workflows/ragcore.yml` running `ruff check`, `ruff format --check`, `mypy --strict src/` and pytest as failing steps — Boundary: CI | Validates: Constitution §Python baseline
- [ ] T016 [P] Create `.github/workflows/web.yml` running lint, type-check, unit tests and the accessibility sweep — Boundary: CI | Validates: Constitution §Angular
- [ ] T017 Create `.github/workflows/boundaries.yml` invoking `build/scripts/check-boundaries.sh` as a required check — Boundary: cross-deployable | Validates: Constitution P-V
- [ ] T018 [P] Create `.github/workflows/migrations.yml` running `pytest --test-alembic` in `ragcore/` — Boundary: schema | Validates: ADR-0003
- [ ] T019 [P] Add secret scanning to CI and a `.gitignore` excluding build artifacts in the repository root — Boundary: repository | Validates: Constitution §Secrets, §Commits
- [ ] T020 [P] Create unit test projects `dotnet/tests/Synthia.SharedKernel.Tests/` and `dotnet/tests/Synthia.Modules.<Name>.Tests/` for all six modules, added to the solution — Boundary: .NET test | Validates: Constitution §Required test categories
- [ ] T021 [P] Create the RagCore unit test structure in `ragcore/tests/unit/` mirroring `src/ragcore/` packages — Boundary: Python test | Validates: Constitution §Required test categories
- [ ] T022 Plant a deliberate cross-tree reference and confirm `build/scripts/check-boundaries.sh` fails, then remove it — Boundary: cross-deployable | Validates: Stage 1 gate (the guard must demonstrably fail)

**Checkpoint**: All five workflows green on an empty repository; the boundary script provably fails a violation.

---

## Phase 2: Shared contracts and architecture boundaries *(Stage 2)*

**Goal**: Dependency direction and the tests that guard it, before any feature code exists.

- [ ] T023 [P] Implement `TenantId`, `CorrelationId` and `StaffRole` in `dotnet/src/Synthia.SharedKernel/` as explicit domain types, with **no comparison or ordering operator on roles** — Boundary: shared kernel | Validates: Spec §FR-AUTHZ-003
- [ ] T024 [P] Implement set-intersection authorization in `dotnet/src/Synthia.SharedKernel/Authorization/RoleIntersection.cs` — empty intersection denies — Boundary: authorization | Validates: Spec §FR-AUTHZ-004, §FR-AUTHZ-010
- [ ] T025 [P] Implement the pure domain model in `ragcore/src/ragcore/domain/` — work item, operation, execution treatment, staff role — importing nothing outside the standard library — Boundary: domain | Validates: Constitution P-V (dependency inward)
- [ ] T026 [P] Implement set-intersection role evaluation in `ragcore/src/ragcore/domain/roles.py`, mirroring T024 with no ordering — Boundary: authorization | Validates: Spec §FR-AUTHZ-003
- [ ] T027 Declare application ports as Protocols in `ragcore/src/ragcore/application/ports.py` for retrieval, model, notification, messaging, tool execution, ingestion and each integration — Boundary: ports | Validates: Constitution P-V (ports belong to the consumer)
- [ ] T028 [P] Define cross-module abstractions and DTOs in `dotnet/src/Synthia.Contracts/` with no implementation — Boundary: module contracts | Validates: Constitution P-V
- [ ] T029 [P] Define typed IPC channel contracts with schema validators in `apps/desktop/src/ipc-contracts/` — Boundary: IPC | Validates: Constitution P-VII
- [ ] T030 [P] Unit tests for set intersection in `ragcore/tests/unit/test_roles.py` asserting no ordering exists, no role implies another, and an empty intersection denies — Boundary: authorization | Validates: Spec §FR-AUTHZ-003, §FR-AUTHZ-006
- [ ] T031 [P] Unit tests for set intersection in `dotnet/tests/Synthia.SharedKernel.Tests/RoleIntersectionTests.cs`, mirroring T030 so both stacks are proven independently — Boundary: authorization | Validates: Spec §FR-AUTHZ-004
- [ ] T032 Write architecture tests in `dotnet/tests/Synthia.ArchitectureTests/ModuleIsolationTests.cs` asserting no module project references another — Boundary: module | Validates: Constitution P-V
- [ ] T033 Write architecture tests in `dotnet/tests/Synthia.ArchitectureTests/NoRagCoreDependencyTests.cs` asserting no assembly reference, type or configured `HttpClient` base address resolves to RagCore — Boundary: cross-deployable | Validates: ADR-0001
- [ ] T034 [P] Write architecture tests in `dotnet/tests/Synthia.ArchitectureTests/BannedApiTests.cs` for `DateTime.Now`, `Thread.Sleep` in async paths, `.Result`, `.Wait()`, `GetAwaiter().GetResult()`, and `catch (Exception)` without rethrow — Boundary: .NET | Validates: Constitution §.NET baseline
- [ ] T035 [P] Write architecture tests in `dotnet/tests/Synthia.ArchitectureTests/CompositionRootTests.cs` asserting no Service Locator usage and no `BuildServiceProvider` call during configuration — Boundary: composition root | Validates: Constitution §Dependency injection
- [ ] T036 [P] Write import-boundary tests in `ragcore/tests/architecture/test_layering.py` asserting `domain/` imports nothing outside the standard library and no adapter type appears in `domain/` or `application/` — Boundary: layering | Validates: Constitution P-V
- [ ] T037 [P] Write a test in `ragcore/tests/architecture/test_no_dotnet.py` asserting no import, package or HTTP client targets the monolith — Boundary: cross-deployable | Validates: ADR-0001

**Checkpoint**: Every architecture test fails when its violation is planted and passes otherwise.

---

## Phase 3: Angular scaffold *(Stage 3)*

**Goal**: Three applications and four libraries that build and render, with shared infrastructure centralized.

- [ ] T038 [P] Implement `apps/web/projects/design-system/` accessible primitives — focus management, live regions, state conveyed by more than colour — Boundary: presentation | Validates: Spec §FR-SURF-010, §FR-SURF-013
- [ ] T039 [P] Implement loading, empty and partial-failure states in `apps/web/projects/design-system/states/` so no failure renders as an empty result — Boundary: presentation | Validates: Spec §FR-SURF-016
- [ ] T040 Implement `apps/web/projects/platform-core/` with typed API clients for both backends, auth/token handling, correlation propagation and RFC 9457 problem-details handling — Boundary: client infrastructure | Validates: Constitution §Angular (centralized infrastructure)
- [ ] T041 [P] Implement the realtime client in `apps/web/projects/platform-core/realtime/` that rebuilds state from the API on reconnect rather than from missed notifications — Boundary: realtime | Validates: Spec §FR-SESS-019
- [ ] T042 [P] Scaffold `apps/web/projects/customer-features/` shells for chat, session, consent and handoff with no behaviour — Boundary: presentation | Validates: Constitution P-IX (scaffold honestly)
- [ ] T043 [P] Scaffold `apps/web/projects/staff-features/` shells for the queue, take-over and reporting — Boundary: presentation | Validates: Constitution P-IX
- [ ] T044 Compose `apps/web/projects/customer-portal/` from `customer-features` and `platform-core` — Boundary: customer surface | Validates: Spec §FR-SURF-001
- [ ] T045 Compose `apps/web/projects/staff-portal/` with module visibility by role and **no session-origination route** — Boundary: staff surface | Validates: Spec §FR-SURF-006
- [ ] T046 Compose `apps/web/projects/desktop-renderer/` reusing `customer-features`, adding only the desktop bridge service — Boundary: desktop surface | Validates: Plan Stage 3
- [ ] T047 [P] Write a test in `apps/web/projects/platform-core/no-authz.spec.ts` asserting no presentation component makes an authorization decision — Boundary: presentation | Validates: Spec §FR-SURF-004
- [ ] T048 [P] Configure the plan Stage 3 CSP baseline as a **response header** (never a meta tag) and the Angular sanitization policy in `apps/web/projects/platform-core/security/`, with `bypassSecurityTrust*` absent and no unsafe-inline or unsafe-eval in script-src — Boundary: browser security | Validates: Constitution P-VII
- [ ] T049 [P] Write the axe-core accessibility sweep in `apps/web/e2e/a11y-scaffold.spec.ts` across all three surfaces — Boundary: presentation | Validates: Spec §SC-SURF-002

**Checkpoint**: All three apps build under strict TypeScript; zero Level A/AA failures; boundary lint fails a cross-library import.

---

## Phase 4: Electron scaffold *(Stage 4)*

**Goal**: A thin, hardened host that renders the renderer and decides nothing.

- [ ] T050 Implement main-process window creation in `apps/desktop/src/main/window.ts` with `nodeIntegration=false`, `contextIsolation=true`, `sandbox=true` **unconditionally** (plan Stage 4 resolves "where compatible"; disabling it requires an ADR) — Boundary: desktop host | Validates: Constitution P-VII
- [ ] T051 Implement the narrow typed `contextBridge` surface in `apps/desktop/src/preload/bridge.ts`, never exposing raw `ipcRenderer` or broad Electron/Node APIs — Boundary: IPC | Validates: Constitution P-VII
- [ ] T052 Implement IPC **sender** validation and **argument** validation as two distinct checks in `apps/desktop/src/main/ipc-guard.ts` — Boundary: IPC | Validates: Constitution P-VII
- [ ] T053 [P] Implement the navigation and new-window allow-list in `apps/desktop/src/main/navigation.ts` permitting **only** the renderer bundle origin, the single gateway origin and the Entra authority (plan Stage 4 names the complete set); the window-open handler denies every destination without exception; exact scheme match on HTTPS/WSS only; `webSecurity` never disabled — Boundary: desktop host | Validates: Constitution P-VII, Spec §FR-SURF-017
- [ ] T054 [P] Implement the plan Stage 3 CSP baseline for the renderer in `apps/desktop/src/main/csp.ts`, applied from the main process on received headers so the renderer cannot weaken it, with connect-src narrowed to the gateway, SignalR and Entra origins — Boundary: desktop host | Validates: Constitution P-VII
- [ ] T055 [P] Write the Electron security suite in `apps/desktop/tests/security.spec.ts` asserting each switch, that IPC rejects an unvalidated sender and an unvalidated argument, and that navigation outside the allow-list is blocked — Boundary: desktop host | Validates: Stage 4 gate
- [ ] T056 [P] Write a test in `apps/desktop/tests/no-policy.spec.ts` asserting no business authorization decision exists in the renderer **or** the main process — Boundary: desktop host | Validates: Constitution P-VII

**Checkpoint**: The security suite passes, and fails correctly when a setting is flipped.

---

## Phase 5: .NET scaffold *(Stage 5)*

**Goal**: A read-only modular monolith that starts and serves versioned APIs with no data behind it.

- [ ] T057 Implement the Gateway-derived identity header contract in `dotnet/src/Synthia.Api/Middleware/IdentityContextMiddleware.cs` — no token parsing; reject any request supplying tenant or role — Boundary: identity | Validates: Spec §FR-IDENT-002
- [ ] T058 [P] Implement correlation middleware in `dotnet/src/Synthia.Api/Middleware/CorrelationMiddleware.cs` accepting `X-Correlation-Id` only when well formed, generating when absent, echoing in responses — Boundary: observability | Validates: Spec §FR-OPS-001
- [ ] T059 [P] Configure `IExceptionHandler` with RFC 9457 ProblemDetails in `dotnet/src/Synthia.Api/Errors/`, never exposing internal detail — Boundary: API | Validates: Constitution §.NET validation and errors
- [ ] T060 Configure Minimal API routing in `dotnet/src/Synthia.Api/Program.cs` — URI-segment versioning under `/api/{audience}/v1/views/...`, plural nouns, kebab-case multi-word segments, camelCase JSON, built-in OpenAPI — Boundary: API | Validates: Constitution §.NET APIs
- [ ] T061 [P] Implement keyset pagination with **opaque** cursors in `dotnet/src/Synthia.Api/Paging/` — Boundary: API | Validates: Contracts §README
- [ ] T062 [P] Implement typed filter binding and a whitelisted sort resolver in `dotnet/src/Synthia.Api/Querying/` against the **per-resource field sets enumerated in `contracts/README.md`**, defaulting to `-createdAt` (`-occurredAt` for audit) so keyset pagination has a deterministic order, and rejecting an unknown field with 400 — Boundary: API | Validates: Contracts §README
- [ ] T063 [P] Scaffold the six module projects under `dotnet/src/Modules/` — Sessions, Work, Approvals, Governance, Audit, Tenancy — each with a registration extension and no reference to another module — Boundary: module | Validates: Constitution P-V
- [ ] T064 Wire module registration from the single composition root in `dotnet/src/Synthia.Api/Program.cs` using constructor injection only — Boundary: composition root | Validates: Constitution §Dependency injection
- [ ] T065 [P] Add liveness `/health/live` (process-only, no dependency checks) in `dotnet/src/Synthia.Api/Health/` — Boundary: runtime | Validates: Constitution §Health
- [ ] T066 [P] Write contract tests in `dotnet/tests/Synthia.ContractTests/ApiConventionTests.cs` for camelCase, cursor shape, versioning, kebab-case segments and problem-details — Boundary: API | Validates: Stage 5 gate
- [ ] T067 [P] Write an architecture test in `dotnet/tests/Synthia.ArchitectureTests/NoWriteEndpointTests.cs` asserting the monolith exposes no state-changing endpoint — Boundary: read-only | Validates: Spec §FR-SURF-004, ADR-0001
- [ ] T068 [P] Write an architecture test in `dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs` asserting `Database.Migrate()`, `EnsureCreated()` and EF migration files are absent — Boundary: schema ownership | Validates: ADR-0003

**Checkpoint**: The app starts, `/health/live` responds, OpenAPI generates, contract tests pass.

---

## Phase 6: RagCore scaffold *(Stage 6)*

**Goal**: A FastAPI application and LangGraph skeleton with the three interrupts, ports declared, adapters absent.

- [ ] T069 Implement typed settings in `ragcore/src/ragcore/config/settings.py` using Pydantic Settings, resolving secrets from Key Vault via managed identity, with no scattered environment reads — Boundary: configuration | Validates: Constitution §Python (Pydantic Settings)
- [ ] T070 Implement the identity header middleware in `ragcore/src/ragcore/api/middleware/identity.py` — no token parsing; reject any request supplying tenant or role — Boundary: identity | Validates: Spec §FR-IDENT-002
- [ ] T071 [P] Implement correlation middleware in `ragcore/src/ragcore/api/middleware/correlation.py` binding the identifier to the logging context — Boundary: observability | Validates: Spec §FR-OPS-001
- [ ] T072 [P] Implement RFC 9457 problem-details handling in `ragcore/src/ragcore/api/middleware/problems.py` matching the .NET shape — Boundary: API | Validates: Contracts §README
- [ ] T073 Scaffold the customer, staff and workload routers in `ragcore/src/ragcore/api/{customer,staff,workload}/` with explicit Pydantic request/response schemas and **no business policy in endpoints** — Boundary: API | Validates: Constitution §FastAPI
- [ ] T074 Wire dependency injection via FastAPI `Depends` at HTTP boundaries only in `ragcore/src/ragcore/api/deps.py` — Boundary: composition root | Validates: Constitution §Dependency injection
- [ ] T075 Implement the LangGraph state and builder in `ragcore/src/ragcore/graph/{state.py,builder.py}` with the three interrupt points: clarification, consent, approval — Boundary: orchestration | Validates: Spec §FR-INTR-001
- [ ] T076 [P] Implement the session state machine in `ragcore/src/ragcore/domain/session_state.py` covering the nine states, with the three `awaiting_*` states persisting indefinitely — Boundary: domain | Validates: Spec §FR-SESS-015, §FR-SESS-016
- [ ] T077 [P] Scaffold `ragcore/src/ragcore/ingestion/` — the twelfth bounded context: acquisition, normalisation, chunking, embedding, indexing — with no behaviour — Boundary: Ingestion context | Validates: Plan §Project Structure, research R-021
- [ ] T078 [P] Implement the SSE streaming envelope in `ragcore/src/ragcore/api/customer/streaming.py` with event kinds `token`, `step`, `interrupt`, `done`, `error` — Boundary: API | Validates: Contracts §customer-api
- [ ] T079 [P] Write contract tests in `ragcore/tests/contracts/test_api_surface.py` for the three audiences and the SSE envelope — Boundary: API | Validates: Stage 6 gate
- [ ] T080 [P] Write async cancellation tests in `ragcore/tests/unit/test_cancellation.py` asserting `asyncio.CancelledError` propagates and is never swallowed — Boundary: async | Validates: Constitution §Python (cancellation)
- [ ] T081 [P] Write a test in `ragcore/tests/unit/test_graph_interrupts.py` asserting the graph suspends and resumes in memory at all three interrupt points — Boundary: orchestration | Validates: Stage 6 gate

**Checkpoint**: `mypy --strict` and `ruff` clean; the graph suspends and resumes in memory.

---

## Phase 7: PostgreSQL and persistence scaffold *(Stage 7)*

**Goal**: The authoritative durable store, migration discipline, and the read-view contract.

- [ ] T082 Initialise Alembic in `ragcore/` with the async template; configure `ragcore/migrations/env.py` with `async_engine_from_config`, `NullPool` and `connection.run_sync` — Boundary: schema | Validates: ADR-0003
- [ ] T083 Configure `ragcore/migrations/env.py` to exclude the `langgraph` schema from autogenerate via `include_schemas`/`include_object` — Boundary: schema | Validates: research R-004
- [ ] T084 Configure the durable LangGraph checkpointer in `ragcore/src/ragcore/graph/checkpointer.py` using `langgraph-checkpoint-postgres` against the `langgraph` schema, compile the graph with it in place of the in-memory saver, and run the checkpointer's own `setup()` from the migration job — never at application startup — Boundary: orchestration | Validates: Constitution P-IV (one checkpoint store), research R-004
- [ ] T085 [P] Create the `tenant_mapping` migration in `ragcore/migrations/versions/` — `tenant_id` uuid PK, `entra_tid` uuid unique not null, `display_name` text not null, `status` enum (`active`, `suspended`, `offboarded`) not null, `retention_overrides` jsonb null, `version` int not null — Boundary: Tenant & Configuration | Validates: data-model.md
- [ ] T086 [P] Create the `chat_session` migration in `ragcore/migrations/versions/` — `state` enum (`conversational`, `resolving`, `awaiting_user`, `awaiting_consent`, `awaiting_approval`, `staff_controlled`, `resolved`, `escalated`, `closed_declined`) not null, `content_expires_at` timestamptz **null while active**, `version` int not null — Boundary: Session | Validates: Spec §FR-SESS-015, §FR-SESS-020
- [ ] T087 [P] Create the `message` migration in `ragcore/migrations/versions/` — `tenant_id` uuid not null (denormalised for non-bypassable filtering), `sender_kind` enum (`end_user`, `agent`, `staff`) not null — Boundary: Session | Validates: data-model.md
- [ ] T088 [P] Create the `feedback` migration in `ragcore/migrations/versions/` — `signal` enum (`positive`, `negative`) not null, **unique on (`message_id`, `given_by_oid`)** so a revision updates rather than inserts — Boundary: Session | Validates: Spec §FR-SESS-010
- [ ] T089 Create the `work_item` migration in `ragcore/migrations/versions/` with `state` enum (`open`, `awaiting_decision`, `authorized`, `claimed`, `executed`, `failed`, `expired`, `cancelled`, `escalated`) and `approval_state` enum (`none`, `pending`, `approved`, `rejected`, `expired`), plus `version` int not null — Boundary: Work | Validates: data-model.md
- [ ] T090 Add a database-level immutability guard on `work_item` authority fields (`tenant_id`, `requested_by_oid`, `case_reference`, `governed_action`, `target`) via trigger or column grant in `ragcore/migrations/versions/` — Boundary: Work | Validates: Spec §FR-EXEC-008
- [ ] T091 [P] Create the `operation` migration in `ragcore/migrations/versions/` — `treatment` enum (`AUTO`, `END_USER_APPROVAL`, `STAFF_APPROVAL`, `NOT_ALLOWED`), `verification` enum (`server_confirmed`, `client_attested`, `contradicted`) null — Boundary: Governance | Validates: data-model.md
- [ ] T092 [P] Create the `governance_record` migration in `ragcore/migrations/versions/` — composite PK (`catalogue_id`, `version`), `accepted_roles` text[] not null, `is_reference_fixture` bool not null, `requires_elevation` bool not null **with a CHECK constraint enforcing false** — Boundary: Governance | Validates: ADR-0004
- [ ] T093 [P] Create the `tenant_entitlement` migration in `ragcore/migrations/versions/` — `credential_reference` text null (a Key Vault reference, **never a secret value**) — Boundary: Tool Execution | Validates: Spec §FR-EXT-016
- [ ] T094 [P] Create the `approval` migration in `ragcore/migrations/versions/` — `work_item_id` uuid FK **unique** not null (at most one approval per case), `decided_by_roles` text[] null, `expires_at` timestamptz null — Boundary: Approval | Validates: Spec §FR-INTR-010
- [ ] T095 [P] Create the `consent` migration in `ragcore/migrations/versions/` — `consented_by_oid` uuid not null, `verdict` enum (`granted`, `refused`) not null — Boundary: Approval | Validates: Spec §FR-INTR-005
- [ ] T096 [P] Create the `audit_event` migration in `ragcore/migrations/versions/` with the full actor chain, `execution_method` enum (`workload`, `desktop_script`, `none`), `correlation_id` text not null, `retain_until` timestamptz not null, append-only with no update or delete grant — Boundary: Audit | Validates: Spec §FR-AUDIT-001
- [ ] T097 [P] Create the `outbox_message` migration in `ragcore/migrations/versions/` — `payload` jsonb carrying opaque identifiers and correlation only, `dispatched_at` timestamptz null, `attempts` int, `version` int — Boundary: messaging | Validates: research R-017
- [ ] T098 [P] Create the `idempotency_record` migration in `ragcore/migrations/versions/` — `idempotency_key` text PK, `outcome` jsonb null replayed on repeat, and **no `version` column**: this is the single named exemption from the optimistic-concurrency convention (data-model.md §Conventions) — Boundary: Tool Execution | Validates: data-model.md
- [ ] T099 [P] Create the `ingestion_run` migration in `ragcore/migrations/versions/` — `watermark` text null, `state` enum (`running`, `completed`, `failed`), tenant-stamped — Boundary: Ingestion | Validates: research R-021
- [ ] T100 [P] Scaffold the ingestion worker entry point in `ragcore/workers/ingestion_run.py` opening an `ingestion_run` row and recording its watermark and terminal state, with **no acquisition, chunking or embedding behaviour** — Boundary: Ingestion | Validates: Plan §Project Structure, Constitution P-IX
- [ ] T101 Create the published-view migration in `ragcore/migrations/versions/` using `alembic_utils` defining all eleven `vw_*_v1` views, each carrying `tenant_id`, none exposing credential material, each respecting retention and excluding soft-deleted rows — Boundary: read contract | Validates: Contracts §read-views
- [ ] T102 Grant separated database principals in `ragcore/migrations/versions/`: migration job DDL, RagCore runtime DML+SELECT, monolith runtime SELECT on published views only — Boundary: schema ownership | Validates: ADR-0003
- [ ] T103 Implement SQLAlchemy models and repositories in `ragcore/src/ragcore/persistence/` where **every** query applies `tenant_id` and no method omits it — Boundary: tenant isolation | Validates: Spec §FR-IDENT-008
- [ ] T104 [P] Implement optimistic concurrency in `ragcore/src/ragcore/persistence/concurrency.py` using the `version` column on every table except the named `idempotency_record` exemption, with **no distributed lock anywhere**, **no Serializable transaction** and **no `deleted_at` column on any scaffold entity** — all three positions stated in data-model.md §Conventions — Boundary: persistence | Validates: research R-018
- [ ] T105 [P] Implement retention-from-terminal-state in `ragcore/src/ragcore/persistence/retention.py` so `content_expires_at` is set only on a terminal transition — Boundary: Session | Validates: Spec §FR-SESS-020
- [ ] T106 Implement the retention sweeper in `ragcore/workers/retention_sweep.py` removing data past its window for every class in data-model.md §Retention summary — chat content 90 days from terminal state, graph checkpoints 30 days after the work completes, audit events 7 years — resolving each window from `tenant_mapping.retention_overrides` and falling back to the platform default wherever no override is configured — Boundary: retention | Validates: Spec §FR-SESS-007, §FR-SESS-008, §FR-AUDIT-004, §FR-AUDIT-005
- [ ] T107 Implement per-organisation erasure in `ragcore/src/ragcore/persistence/erasure.py` removing that organisation's records, their derived representations and any cached copies — Boundary: Tenant & Configuration | Validates: Spec §FR-AUDIT-006
- [ ] T108 Configure EF Core read contexts in `dotnet/src/Synthia.Persistence/` mapped to `vw_*_v1` views with `AsNoTracking` default, parameterized queries, and a mandatory tenant filter with no unfiltered path — Boundary: read contract | Validates: Constitution §.NET data access
- [ ] T109 [P] Write migration tests in `ragcore/tests/migrations/test_migrations.py` importing pytest-alembic's `test_single_head_revision`, `test_upgrade`, `test_model_definitions_match_ddl`, `test_up_down_consistency` — Boundary: schema | Validates: ADR-0003
- [ ] T110 [P] Write a test in `ragcore/tests/migrations/test_schema_isolation.py` asserting autogenerate never proposes a change inside the `langgraph` schema — Boundary: schema | Validates: research R-004
- [ ] T111 [P] Write a test in `ragcore/tests/checkpoint/test_durable_checkpointer.py` asserting the compiled graph carries the PostgreSQL saver, that no in-memory saver reaches a non-test path, and that no second durable checkpoint store exists — Boundary: orchestration | Validates: Constitution P-IV
- [ ] T112 [P] Write concurrency tests in `ragcore/tests/concurrency/test_optimistic.py` asserting a losing writer sees a version conflict and re-reads rather than blocking — Boundary: persistence | Validates: research R-018
- [ ] T113 [P] Write retention tests in `ragcore/tests/retention/test_retention_classes.py` verifying removal independently for each class and asserting that expiring chat content leaves its audit records intact and complete — Boundary: retention | Validates: Spec §SC-AUDIT-002, §SC-AUDIT-003

**Checkpoint**: Migrations run as a gated job, never at startup; every downgrade succeeds; no unfiltered query path exists; the graph is backed by the durable PostgreSQL checkpointer and every retention class is removable.

---

## Phase 8: Messaging and realtime scaffold *(Stage 8)*

**Goal**: Transactional outbox, opaque triggers, at-least-once consumption, notification-only realtime.

- [ ] T114 Implement the outbox writer in `ragcore/src/ragcore/messaging/outbox.py` so the outbox row commits **in the same transaction** as the state change it describes — Boundary: messaging | Validates: research R-017
- [ ] T115 Implement the outbox dispatcher worker in `ragcore/workers/outbox_dispatch.py` publishing to Service Bus and setting `dispatched_at`, with exponential backoff and jitter to a **ceiling of 10 attempts**, after which the row is marked undispatchable, left in place and never auto-retried — and, for a `granted` kind, surfaced as approved-but-not-executed with an operational alert; a blocked row never blocks another — Boundary: messaging | Validates: Contracts §triggers, research R-017
- [ ] T116 [P] Implement the Service Bus publisher in `ragcore/src/ragcore/messaging/publisher.py` emitting only `workItemId`, `correlationId` and a `kind` drawn from the closed set in `contracts/triggers.md` — Boundary: trigger contract | Validates: Contracts §triggers
- [ ] T117 Implement the resume consumer in `ragcore/workers/resume_worker.py` performing load, verify, atomic claim, resume, execute, record — dispatching on `kind` for all four trigger kinds while reading authority only from the work record, and routing the two refusal kinds to closure without execution — Boundary: Work | Validates: ADR-0002, Contracts §triggers
- [ ] T118 [P] Implement the atomic claim in `ragcore/src/ragcore/execution/claim.py` as a conditional update on `claimed_at IS NULL` — idempotency boundary 1 — Boundary: Work | Validates: Spec §FR-EXEC-004
- [ ] T119 [P] Implement idempotency-key generation and the replay path in `ragcore/src/ragcore/execution/idempotency.py` — idempotency boundary 2 — Boundary: Tool Execution | Validates: Spec §FR-EXEC-005
- [ ] T120 [P] Implement bounded pre-claim retry with jitter in `ragcore/src/ragcore/messaging/retry.py`, and **no post-claim retry** — Boundary: execution | Validates: Spec §FR-EXEC-006
- [ ] T121 [P] Implement the expiry sweeper in `ragcore/workers/expiry_sweep.py` marking work non-executable once the window passes with no claim — Boundary: Work | Validates: Spec §FR-EXEC-001
- [ ] T122 [P] Implement dead-letter handling in `ragcore/src/ragcore/messaging/deadletter.py` raising an operational alert with no automatic replay — Boundary: messaging | Validates: Spec §FR-EXEC-007
- [ ] T123 Implement the SignalR data-plane REST client in `ragcore/src/ragcore/notifications/signalr.py` using an Entra token (scope `https://signalr.azure.com/.default`) via managed identity — Boundary: realtime | Validates: research R-002
- [ ] T124 [P] Implement connection negotiation and group derivation in `ragcore/src/ragcore/api/customer/negotiate.py` — group membership derived from trusted identity, never requested by the client — Boundary: realtime | Validates: Contracts §notifications
- [ ] T125 [P] Write idempotency tests in `ragcore/tests/idempotency/test_duplicate_trigger.py` asserting a duplicate trigger produces exactly one execution and one external effect — Boundary: messaging | Validates: Stage 8 gate
- [ ] T126 [P] Write an outbox crash test in `ragcore/tests/integration/test_outbox_crash.py` asserting a crash between commit and publish loses nothing and duplicates nothing — Boundary: messaging | Validates: quickstart V16

**Checkpoint**: Duplicate delivery absorbed by the claim; expired messages dead-letter rather than executing.

---

## Phase 9: Integration adapter scaffold *(Stage 9)*

**Goal**: Every external system behind a port, with no provider type reaching inward.

- [ ] T127 Configure the AI Gateway in `build/infra/ai-gateway/` as the sole model egress — provider routing, provider-normalised token metering per organisation, budgets and throttles, semantic cache, bidirectional content safety — Boundary: model egress | Validates: Constitution §Model access
- [ ] T128 Implement the model adapter in `ragcore/src/ragcore/integrations/model/` behind the port from T027, routed exclusively through the AI Gateway — Boundary: model | Validates: Spec §FR-OPS-007
- [ ] T129 [P] Implement the ServiceNow adapter in `ragcore/src/ragcore/integrations/servicenow/` as the sole path to the system of record, with idempotent write-backs and queue-and-replay on outage — Boundary: Integration—ServiceNow | Validates: Spec §FR-EXT-004, §FR-EXT-007
- [ ] T130 [P] Implement the Microsoft Graph adapter in `ragcore/src/ragcore/integrations/graph/` behind its port — Boundary: Integration—Graph | Validates: Spec §FR-EXT-008
- [ ] T131 [P] Implement the MCP client boundary in `ragcore/src/ragcore/integrations/mcp/client.py` where discovery never confers entitlement — Boundary: Tool Execution | Validates: Spec §FR-EXT-014
- [ ] T132 [P] Implement the OneLogin and Duo adapters in `ragcore/src/ragcore/integrations/{onelogin,duo}/` as MCP-backed target systems — Boundary: Tool Execution | Validates: ADR-0005
- [ ] T133 Implement typed HTTP clients with pooled lifetime management, a shared resilience policy distinguishing transient from non-transient failure, and an **explicit timeout on every outbound call** in `ragcore/src/ragcore/integrations/http.py` — Boundary: egress | Validates: research R-020
- [ ] T134 [P] Implement boundary contract validation in `ragcore/src/ragcore/integrations/validation.py` rejecting malformed, oversized or contract-violating provider output before it reaches the agent loop — Boundary: integration | Validates: Spec §FR-EXT-021
- [ ] T135 [P] Implement the entitled-but-unreachable distinction in `ragcore/src/ragcore/execution/availability.py`, reported separately from not-entitled and never as a user request failure — Boundary: Tool Execution | Validates: Spec §FR-EXT-022
- [ ] T136 [P] Write adapter tests in `ragcore/tests/integrations/test_adapters.py` exercising each adapter against a fake honouring its contract — Boundary: integration | Validates: Constitution §Required test categories
- [ ] T137 [P] Write a test in `ragcore/tests/integrations/test_no_provider_leak.py` asserting no provider SDK or model type appears in `domain/` or `application/` — Boundary: layering | Validates: Spec §FR-EXT-011
- [ ] T138 [P] Write a test in `ragcore/tests/architecture/test_no_direct_model_call.py` asserting no module holds a provider endpoint outside `integrations/model/` — Boundary: model egress | Validates: Constitution §Model access

**Checkpoint**: No provider type reaches inward; no direct model access exists; every outbound call has a timeout.

---

## Phase 10: Observability, configuration and container scaffold *(Stage 10)*

**Goal**: Traces, correlation, validated configuration and hardened images.

- [ ] T139 Configure OpenTelemetry tracing, metrics and structured logging in `dotnet/src/Synthia.Observability/` with constant message templates and PascalCase placeholders, exporting to Application Insights — Boundary: observability | Validates: Spec §FR-OPS-002
- [ ] T140 [P] Configure OpenTelemetry and structured logging in `ragcore/src/ragcore/observability/` tagged with the owning organisation from trusted context, never from a header or message content — Boundary: observability | Validates: Spec §FR-OPS-002
- [ ] T141 Ensure W3C Trace Context propagation across both deployables and onto every trigger, notification and audit record in `ragcore/src/ragcore/observability/propagation.py` — Boundary: observability | Validates: Spec §FR-OPS-001
- [ ] T142 [P] Emit agent-specific signals in `ragcore/src/ragcore/observability/agent_metrics.py` — token usage per organisation, cache-hit ratio, guardrail actions, gate-outcome distribution, retrieval confidence — Boundary: observability | Validates: Spec §FR-OPS-003
- [ ] T142a [P] Configure telemetry retention at 30 days and **tail-based sampling keyed on the correlation identifier** in the exporter and Container Apps configuration, so a suspended-and-resumed journey is sampled as one unit and every trace carrying an error, a governance denial or an approval is retained regardless; head sampling is prohibited — Boundary: observability | Validates: Spec §FR-OPS-011, §FR-OPS-012
- [ ] T143 [P] Configure typed Options in `dotnet/src/Synthia.Api/Configuration/` using `AddOptions<T>()`, `BindConfiguration`, `ValidateDataAnnotations()` and `ValidateOnStart()`, with no `Configuration["..."]` in application code — Boundary: configuration | Validates: research R-019
- [ ] T144 [P] Add readiness `/health/ready` in `dotnet/src/Synthia.Api/Health/` covering database and critical dependency readiness, distinct from liveness — Boundary: runtime | Validates: Constitution §Health
- [ ] T145 [P] Add liveness and readiness endpoints in `ragcore/src/ragcore/api/health.py` with the same semantics — Boundary: runtime | Validates: Constitution §Health
- [ ] T146 Create `build/docker/dotnet.Dockerfile` — multi-stage SDK → `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled`, **digest-pinned**, non-root UID 1654, shell-less, no package manager, read-only root filesystem — Boundary: runtime | Validates: Constitution §Containers, research R-011
- [ ] T147 [P] Create `build/docker/ragcore.Dockerfile` — multi-stage slim Python 3.12, **digest-pinned** in production, non-root under a fixed documented UID, install from `uv.lock` only, no build toolchain and no package-manager cache in the final layer, read-only root filesystem with every writable path named — Boundary: runtime | Validates: research R-012, Constitution §Containers
- [ ] T148 [P] Define Container Apps configuration in `build/docker/containerapps/` with HTTP health probes, explicit resource limits per deployable and a 25-second drain, documenting that drain is a grace period: a post-claim execution outliving it surfaces as approved-but-not-executed and is **never** re-fired (plan Stage 10) — Boundary: runtime | Validates: Constitution §Containers, Spec §FR-EXEC-006
- [ ] T148a [P] Create the scheduled digest-update workflow in `.github/workflows/base-image-digests.yml` — resolves the current digest per tracked tag monthly and on a High or Critical CVE, opens a PR carrying the vulnerability diff, and gates it on the full suite plus a clean image scan — Boundary: supply chain | Validates: Constitution §Containers, Plan Stage 10
- [ ] T149 Create the migration job definition in `build/docker/migrate.job.yaml` running Alembic **and the checkpointer's own `setup()`** before revision activation, never at startup — Boundary: schema ownership | Validates: ADR-0003
- [ ] T150 [P] Write configuration-validation tests in `dotnet/tests/Synthia.ContractTests/ConfigurationValidationTests.cs` and `ragcore/tests/unit/test_settings.py` asserting a missing required setting fails the process at start — Boundary: configuration | Validates: quickstart V17
- [ ] T151 [P] Write security tests in `ragcore/tests/security/test_no_leakage.py` asserting no secret, token, authorization header, sensitive payload or cross-tenant value reaches a log sink — Boundary: observability | Validates: Spec §FR-OPS-002
- [ ] T152 [P] Write a trace test in `ragcore/tests/integration/test_trace_continuity.py` following one request across suspension and resume via a single correlation identifier — Boundary: observability | Validates: quickstart V18

**Checkpoint**: Configuration fails fast; images are digest-pinned, non-root and read-only.

---

## Phase 11: Architecture and security test foundation *(Stage 11)*

**Goal**: Complete the enforcement surface and seed the inert reference operations.

- [ ] T153 Implement the governance catalogue and deterministic treatment policy in `ragcore/src/ragcore/governance/catalogue.py` — treatment assigned from the catalogue, **never** from model output — Boundary: Governance | Validates: Spec §FR-AGENT-004
- [ ] T154 Implement the control gate in `ragcore/src/ragcore/governance/gate.py` evaluating Knowledge, Ability and Security as independent conditions where none averages away another and Knowledge may withhold but never authorize — Boundary: Governance | Validates: Spec §FR-AGENT-005
- [ ] T155 Seed the four inert reference operations in `ragcore/src/ragcore/governance/fixtures.py` — one per treatment, `is_reference_fixture=true`, no external effect, excluded from production configuration — Boundary: Governance | Validates: Spec §FR-SCOPE-004, §FR-SCOPE-006
- [ ] T156 [P] Unit tests for the treatment policy in `ragcore/tests/unit/test_treatment_policy.py` asserting treatment comes from the catalogue entry and is unaffected by any model-supplied value — Boundary: Governance | Validates: Spec §FR-AGENT-004
- [ ] T157 [P] Unit tests for the atomic claim and idempotency key in `ragcore/tests/unit/test_claim.py` covering first-claim-wins, already-claimed, expired and cancelled — Boundary: Work | Validates: Spec §FR-EXEC-004
- [ ] T158 Write the full authorization matrix test in `dotnet/tests/Synthia.AuthorizationTests/RoleMatrixTests.cs` covering every role combination against every operation, including the empty intersection — Boundary: authorization | Validates: Spec §SC-AUTHZ-001
- [ ] T159 [P] Write a test in `dotnet/tests/Synthia.AuthorizationTests/NoImpliedPrivilegeTests.cs` asserting `administrator` never implies `technician` — Boundary: authorization | Validates: Spec §FR-AUTHZ-003
- [ ] T160 [P] Write a test in `ragcore/tests/authorization/test_role_change_midflight.py` asserting a role change neither rewrites a recorded decision nor cancels authorized work — Boundary: authorization | Validates: Spec §FR-AUTHZ-011
- [ ] T161 [P] Write tenant isolation tests in `dotnet/tests/Synthia.TenantIsolationTests/` asserting no read path returns another organisation's data and a foreign resource returns 404 — Boundary: tenant isolation | Validates: Spec §SC-IDENT-002
- [ ] T162 [P] Write an aggregate leakage test in `dotnet/tests/Synthia.TenantIsolationTests/AggregateLeakageTests.cs` asserting no count, ranking or distribution reveals a single organisation's contribution — Boundary: tenant isolation | Validates: Spec §FR-IDENT-010
- [ ] T163 [P] Write adversarial retrieval tests in `ragcore/tests/isolation/test_cross_tenant_retrieval.py` asserting the tenant filter cannot be evaded by crafted input — Boundary: Retrieval | Validates: Spec §FR-IDENT-009
- [ ] T164 [P] Write a test in `ragcore/tests/governance/test_no_elevation.py` asserting no catalogue entry can be created or activated with `requires_elevation = true` — Boundary: Governance | Validates: ADR-0004
- [ ] T165 [P] Write a test in `ragcore/tests/governance/test_fixtures_excluded.py` asserting reference fixtures are absent from production configuration and never counted as UC-01..UC-12 — Boundary: scaffold scope | Validates: Spec §FR-SCOPE-007
- [ ] T166 Write hard-failure tests in `ragcore/tests/security/test_hard_failures.py` — one per item in Principle VIII, each failing when its protection is removed — Boundary: cross-cutting | Validates: Stage 11 gate

**Checkpoint**: Every hard failure has a test that fails when its protection is removed. **Scaffold complete.**

---

## Phase 12: Golden path A — `AUTO` execution *(Stage 12)*

**Goal**: Prove the full machine end to end with no human in the loop: propose → gate → execute → verify → audit — and prove the gate also refuses, by demonstrating `NOT_ALLOWED`.

**Independent test**: Drive the `AUTO` reference operation from a chat turn to a verified outcome with a complete actor chain, and drive the `NOT_ALLOWED` reference operation to a recorded refusal.

- [ ] T167 [P] [US1] Implement the session lifecycle use case in `ragcore/src/ragcore/application/sessions.py` including the triage gate — a work record commits only when a genuine problem is articulated — Boundary: Session | Validates: Spec §FR-SESS-003
- [ ] T168 [US1] Implement case creation at the triage gate in `ragcore/src/ragcore/application/cases.py`, anchoring each session to exactly one case — Boundary: Integration—ServiceNow | Validates: Spec §FR-EXT-002
- [ ] T169 [P] [US1] Implement hybrid retrieval in `ragcore/src/ragcore/retrieval/hybrid.py` combining a dense leg with a weighted, load-bearing sparse lexical leg — Boundary: Retrieval | Validates: Plan Stage 12
- [ ] T170 [P] [US1] Implement cost-gated rerank in `ragcore/src/ragcore/retrieval/rerank.py` reranking a small top-k above a minimum floor — Boundary: Retrieval | Validates: Plan Stage 12
- [ ] T171 [P] [US1] Implement confidence and margin in `ragcore/src/ragcore/retrieval/confidence.py` using absolute score plus top-1-minus-top-2, thresholds as global constants defined **only in this module**, with both comparisons `>=` so a value exactly equal to its threshold passes (plan Stage 12), plus unit tests asserting the boundary in both directions — Boundary: Retrieval | Validates: Spec §FR-AGENT-014, §FR-AGENT-015
- [ ] T172 [P] [US1] Implement the embedding path in `ragcore/src/ragcore/retrieval/embedding.py` embedding the symptom or description field only — Boundary: Retrieval | Validates: Plan Stage 9
- [ ] T173 [US1] Implement graph nodes for intake, classify and ground in `ragcore/src/ragcore/graph/nodes/` where classification never authorizes — Boundary: Agent/RagCore | Validates: Spec §FR-AGENT-002
- [ ] T174 [US1] Implement content safety in `ragcore/src/ragcore/integrations/model/safety.py` — inbound before the model, outbound before a response returns, every decision logged with its correlation identifier — Boundary: model egress | Validates: Spec §FR-AGENT-010, §FR-AGENT-013
- [ ] T175 [US1] Implement the scope guardrail in `ragcore/src/ragcore/graph/nodes/guardrail.py` declining non-ITSM requests and routing unanswered IT questions to vendor fallback — Boundary: Agent/RagCore | Validates: Spec §FR-SCOPE-009, §FR-SCOPE-010
- [ ] T176 [US1] Implement `POST /api/customer/v1/sessions` and `.../messages` with SSE streaming in `ragcore/src/ragcore/api/customer/sessions.py` — Boundary: Customer API | Validates: Contracts §customer-api
- [ ] T177 [US1] Implement the execution leg and verification stage in `ragcore/src/ragcore/execution/executor.py` recording `server_confirmed`, `client_attested` or `contradicted` — Boundary: Tool Execution | Validates: Spec §FR-AGENT-008
- [ ] T178 [US1] Implement audit writing in `ragcore/src/ragcore/application/audit.py` capturing requester, approver, executor, method, organisation and result — Boundary: Audit | Validates: Spec §FR-AUDIT-001
- [ ] T179 [US1] Implement the escalation path in `ragcore/src/ragcore/application/escalation.py` placing the request on the ServiceNow queue with transcript, candidates and reason, and telling the user **why** — Boundary: Integration—ServiceNow | Validates: Spec §FR-FALL-002, §FR-FALL-010
- [ ] T180 [P] [US1] Implement the Sessions read module in `dotnet/src/Modules/Synthia.Modules.Sessions/` over `vw_session_summary_v1`, `vw_session_message_v1`, `vw_session_step_v1` — Boundary: Session (read) | Validates: Contracts §read-views
- [ ] T181 [P] [US1] Implement customer view endpoints in `dotnet/src/Synthia.Api/Endpoints/CustomerViews.cs` with cursor pagination and whitelisted sort — Boundary: Customer API | Validates: Contracts §customer-api
- [ ] T182 [P] [US1] Implement the chat feature in `apps/web/projects/customer-features/chat/` consuming the SSE stream with accessible live-region announcement — Boundary: presentation | Validates: Spec §FR-SURF-011
- [ ] T183 [P] [US1] Implement the handoff notice in `apps/web/projects/customer-features/handoff/` stating plainly that a human will take the request — Boundary: presentation | Validates: Spec §FR-FALL-007
- [ ] T184 [US1] Implement `PUT` and `DELETE /api/customer/v1/messages/{messageId}/feedback` in `ragcore/src/ragcore/api/customer/feedback.py` — an idempotent replace of the signal, owner-scoped so only the session's own user may record against an agent-authored message — Boundary: Customer API | Validates: Spec §FR-SESS-009, §FR-SESS-010, §FR-SESS-011
- [ ] T185 [P] [US1] Implement the feedback read path in `dotnet/src/Modules/Synthia.Modules.Sessions/` over `vw_message_feedback_v1`, exposing aggregate figures retained independently of the underlying signals — Boundary: Session (read) | Validates: Spec §FR-SESS-012, §FR-SESS-014
- [ ] T186 [P] [US1] Implement the feedback control in `apps/web/projects/customer-features/chat/feedback/` as a keyboard-operable binary signal announced to assistive technology, with the current state visible — Boundary: presentation | Validates: Spec §FR-SESS-009, §SC-SESS-003
- [ ] T187 [P] [US1] Write a test in `ragcore/tests/governance/test_feedback_no_influence.py` asserting feedback reaches no authorization, governance treatment, retrieval scope or execution path — Boundary: Governance | Validates: Spec §FR-SESS-013
- [ ] T188 [P] [US4] Implement the clarification interrupt node and `POST .../answers` in `ragcore/src/ragcore/graph/nodes/clarification_interrupt.py` and `api/customer/answers.py` — Boundary: Agent/RagCore | Validates: Spec §FR-INTR-004
- [ ] T189 [P] [US1] Governance test in `ragcore/tests/governance/test_auto_path.py` asserting the `AUTO` reference operation reaches execution without any human gate and with treatment from the catalogue — Boundary: Governance | Validates: Stage 12 gate
- [ ] T190 [P] [US1] Governance test in `ragcore/tests/governance/test_not_allowed_path.py` asserting the `NOT_ALLOWED` reference operation is refused at the gate, never surfaced to a human as an approvable proposal, and recorded as a denial in audit — Boundary: Governance | Validates: Spec §SC-SCOPE-002, §FR-AUDIT-003
- [ ] T191 [P] [US1] Injection containment test in `ragcore/tests/integration/test_injection_containment.py` asserting injected instructions in retrieved content produce at most a proposal and never reach execution — Boundary: Agent/RagCore | Validates: Stage 12 gate
- [ ] T192 [P] [US1] End-to-end golden path test in `ragcore/tests/e2e/test_auto_golden_path.py` asserting a verified outcome and a complete actor chain — Boundary: cross-cutting | Validates: Stage 12 gate

**Checkpoint**: Golden path A validated — the machine works end to end without a human, and refuses what it must. `AUTO` and `NOT_ALLOWED` demonstrated.

---

## Phase 13: Golden path B — governed human decision: `STAFF_APPROVAL` and `END_USER_APPROVAL` *(Stage 13)*

**Goal**: Prove durable suspension, an authenticated human decision, and execution surviving the requester's
absence. Both treatments share one machine — suspend → verdict → outbox → trigger → resume → claim →
execute — and differ only in **who may decide** and **on which surface**, so both are proven here rather
than duplicating the path.

**Independent test**: Two runs. (a) Drive the `STAFF_APPROVAL` reference operation to an interrupt,
**close the customer client entirely**, approve from the staff portal, and confirm the work completes.
(b) Drive the `END_USER_APPROVAL` reference operation to the consent interrupt, type an affirmative
message in the chat and confirm **nothing happens**, then submit the explicit consent action and confirm
the work resumes.

- [ ] T193 [US2] Implement the approval request use case in `ragcore/src/ragcore/application/approvals.py` binding approver, tenant, work item, operation, target, version, expiry and audit, and disclosing every command — Boundary: Approval | Validates: Spec §FR-INTR-009, Constitution P-III
- [ ] T194 [US2] Implement the approval interrupt node in `ragcore/src/ragcore/graph/nodes/approval_interrupt.py` suspending the graph durably — Boundary: Agent/RagCore | Validates: Spec §FR-INTR-002
- [ ] T195 [US2] Implement `POST /api/staff/v1/approvals/{approvalId}/verdict` in `ragcore/src/ragcore/api/staff/approvals.py` — sets `expires_at` to now + 15 minutes, writes the outbox row carrying `approval.granted` or `approval.rejected` in the same transaction, and **returns before execution runs** — Boundary: Staff API | Validates: ADR-0002, Spec §FR-EXEC-001
- [ ] T196 [P] [US2] Implement first-valid-verdict-wins in `ragcore/src/ragcore/application/approvals.py` so a later verdict is recorded without changing the outcome — Boundary: Approval | Validates: Spec §FR-INTR-010
- [ ] T197 [P] [US2] Implement `interrupt.pending` and `approval.decided` notification publication in `ragcore/src/ragcore/notifications/events.py` carrying no authority-bearing value — Boundary: realtime | Validates: Contracts §notifications
- [ ] T198 [P] [US2] Implement the Approvals read module in `dotnet/src/Modules/Synthia.Modules.Approvals/` over `vw_approval_queue_v1` and `vw_approval_unexecuted_v1` — Boundary: Approval (read) | Validates: Contracts §read-views
- [ ] T199 [P] [US2] Implement the Work read module in `dotnet/src/Modules/Synthia.Modules.Work/` over `vw_work_item_v1` — Boundary: Work (read) | Validates: Contracts §read-views
- [ ] T200 [P] [US2] Implement staff approval queue endpoints in `dotnet/src/Synthia.Api/Endpoints/StaffViews.cs` including the approved-but-not-executed surface — Boundary: Staff API | Validates: Spec §FR-EXEC-007
- [ ] T201 [P] [US2] Implement the approval queue UI in `apps/web/projects/staff-features/approvals/` showing the fully disclosed command set before a decision — Boundary: presentation | Validates: Spec §FR-INTR-009
- [ ] T202 [US3] Implement the consent interrupt node in `ragcore/src/ragcore/graph/nodes/consent_interrupt.py` suspending the graph durably and rendering the consent prompt in the conversation — Boundary: Agent/RagCore | Validates: Spec §FR-INTR-002
- [ ] T203 [US3] Implement `POST /api/customer/v1/work/{workItemId}/consent` in `ragcore/src/ragcore/api/customer/consent.py` — an explicit authenticated action bound to the work, accepted only from the work item's `requested_by_oid` and rejected with 403 otherwise, writing the outbox row carrying `consent.granted` or `consent.refused` in the same transaction — Boundary: Customer API | Validates: Spec §FR-INTR-005, §FR-INTR-006
- [ ] T204 [P] [US3] Implement the consent prompt in `apps/web/projects/customer-features/consent/` disclosing exactly what will happen, fully operable by keyboard and conveyed to assistive technology — Boundary: presentation | Validates: Spec §FR-SURF-012
- [ ] T205 [P] [US3] Write a test in `ragcore/tests/governance/test_consent_not_chat.py` asserting an affirmative chat message confers no authority and leaves the work suspended — Boundary: Governance | Validates: Spec §FR-INTR-006, Constitution P-I
- [ ] T206 [P] [US3] Write a test in `ragcore/tests/authorization/test_consent_authority.py` asserting consent from anyone but the requester is rejected, and that consent never satisfies a `STAFF_APPROVAL` requirement — Boundary: authorization | Validates: Spec §FR-INTR-005, §FR-INTR-007
- [ ] T207 [US3] End-to-end golden path test in `ragcore/tests/e2e/test_consent_golden_path.py` driving the `END_USER_APPROVAL` reference operation to the consent interrupt, confirming an affirmative message changes nothing, then submitting the explicit action and asserting the work resumes and completes — Boundary: cross-cutting | Validates: Spec §SC-SCOPE-002, §SC-IDENT-001
- [ ] T208 [P] [US5] Implement take-over in `ragcore/src/ragcore/application/takeover.py` as an authenticated state transition resolving concurrently to a single owner — Boundary: Session | Validates: Spec §FR-INTR-013
- [ ] T209 [P] [US5] Implement `POST /api/staff/v1/work/{workItemId}/cancel` in `ragcore/src/ragcore/api/staff/work.py`, permitted at every suspension point before claim — Boundary: Work | Validates: Spec §FR-INTR-014
- [ ] T210 [P] [US5] Implement the Audit, Governance and Tenancy read modules in `dotnet/src/Modules/` over `vw_audit_event_v1`, `vw_governance_catalogue_v1`, `vw_tenant_v1` and the reporting rollup — Boundary: read contract | Validates: Contracts §read-views
- [ ] T211 [P] [US5] Implement Mission Control and Synthia Admin in `apps/web/projects/staff-features/{mission-control,admin}/` with module visibility by role — Boundary: presentation | Validates: Spec §FR-SURF-003
- [ ] T212 [P] [US2] Approval authorization test in `ragcore/tests/authorization/test_approval_roles.py` asserting `technician` may approve, `administrator` may not, and an empty intersection denies — Boundary: authorization | Validates: Spec §FR-AUTHZ-007
- [ ] T213 [P] [US2] Checkpoint/resume test in `ragcore/tests/checkpoint/test_suspend_resume.py` asserting suspension survives with no client connected and resumes only under valid authority — Boundary: Agent/RagCore | Validates: Spec §SC-INTR-001
- [ ] T214 [P] [US2] Expiry test in `ragcore/tests/integration/test_expiry.py` asserting the window elapsing makes work non-executable, is not an error, and surfaces as approved-but-not-executed — Boundary: Work | Validates: Spec §FR-EXEC-001
- [ ] T215 [P] [US2] No-refire test in `ragcore/tests/integration/test_no_refire.py` asserting a failed authorized action does not retry and requires fresh authorization — Boundary: execution | Validates: Spec §FR-EXEC-006
- [ ] T216 [P] [US5] Concurrency test in `ragcore/tests/concurrency/test_concurrent_takeover.py` asserting two simultaneous take-overs resolve to one owner — Boundary: Session | Validates: Spec §FR-INTR-013
- [ ] T217 [P] [US2] Contract test in `ragcore/tests/contracts/test_staff_verdict.py` asserting the verdict endpoint returns before execution and records the role set held at decision time — Boundary: Staff API | Validates: Spec §FR-AUTHZ-011
- [ ] T218 [US2] End-to-end golden path test in `ragcore/tests/e2e/test_staff_approval_golden_path.py` driving the interrupt, **closing the customer client entirely**, approving, and asserting the work completes — Boundary: cross-cutting | Validates: Stage 13 gate, Spec §SC-EXEC-001

**Checkpoint**: Golden path B validated — approved work survives the client, and consent is an action rather than a sentence. **Both golden paths complete; all four execution treatments demonstrated.**

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
```

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

**T084 is a hard prerequisite for Phase 13** — until the graph is compiled with the PostgreSQL
checkpointer it suspends only in memory, so no suspension survives a restart and neither
`STAFF_APPROVAL` nor `END_USER_APPROVAL` can be proven durable.

### Parallel opportunities

- Phase 1: T002–T006, T008–T012, T014–T016, T018–T021 run in parallel
- Phase 2: T023–T026, T028–T031, T034–T037 run in parallel
- Phases 3 and 4 (clients) are fully parallel with Phases 5 and 6 (backends) once Phase 2 completes
- Phase 7: the table migrations T085–T099 are parallel; T101 and T102 are not
- Phase 7: T106 and T107 (retention, erasure) are sequential; T111 and T113 (their tests) are parallel
- Phase 12: T169–T172 (retrieval pipeline), T180–T183 and T185–T188 are parallel; T184 (feedback
  endpoint) precedes T185 and T186
- Phase 13: T196–T201 and T208–T218 are parallel once T195 lands; within the consent path T202 → T203
  are sequential, then T204–T206 are parallel and T207 is last

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

Golden path A proves the machine works without a human, and that the gate refuses what it must.
Golden path B proves the hardest guarantee — that a governed human decision survives the requester's
absence — for both human-decided treatments, since they differ only in who decides and where. Only
together do they demonstrate that the governance architecture holds, and between them they exercise all
four execution treatments (`SC-SCOPE-002`).

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
