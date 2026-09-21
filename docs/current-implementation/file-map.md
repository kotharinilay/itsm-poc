# Source file map — current implementation

Paths are relative to the repo root. Endpoint and DB behaviour is described in [scenarios.md](scenarios.md) and [database.md](database.md); this page only says what each file is for. Lock files, `bin/obj`, generated OpenAPI artifacts and trivial fixtures are omitted.

## apps/

### apps/web — Angular workspace (`angular.json`, one library per concern)

| File | Purpose |
| ---- | ------- |
| `apps/web/projects/customer-portal/src/app/{app,app.config,app.routes,platform.config}.ts` | Customer portal shell, providers and API base config; mounts `customer-features` routes. |
| `apps/web/projects/staff-portal/src/app/{app,app.config,app.routes,platform.config}.ts` | Staff portal shell and config; mounts `staff-features` routes. |
| `apps/web/projects/desktop-renderer/src/app/app.ts`, `app.config.ts` | Renderer shell (layout, router outlet, bridge seam) loaded inside Electron; no feature behaviour. |
| `apps/web/projects/desktop-renderer/src/app/desktop/desktop-bridge.ts`, `desktop-bridge.types.ts`, `desktop-bridge.service.ts` | Typed wrapper over the preload bridge (`window` API exposed by `apps/desktop`). |
| `apps/web/projects/platform-core/src/lib/api/platform-api.client.ts`, `platform-api.config.ts`, `platform.interceptors.ts` | Base HTTP client and base URL config; `correlationInterceptor`, `authInterceptor`, `problemDetailsInterceptor`. |
| `apps/web/projects/platform-core/src/lib/api/customer-api.client.ts` | Calls RagCore customer routes and .NET `/views/*` customer routes. |
| `apps/web/projects/platform-core/src/lib/api/staff-api.client.ts` | Calls RagCore staff routes and .NET `/views/*` staff routes. |
| `apps/web/projects/platform-core/src/lib/api/message-stream.client.ts` | SSE reader for `POST /sessions/{id}/messages`. |
| `apps/web/projects/platform-core/src/lib/api/correlation.ts`, `platform-api-error.ts` | Correlation id generation; typed API error. |
| `apps/web/projects/platform-core/src/lib/contracts/*.ts` | TypeScript request/response types mirroring the OpenAPI contracts (customer, staff, paging, problem details). |
| `apps/web/projects/platform-core/src/lib/auth/*.ts` | Auth session, access-token provider, role-based UI visibility. |
| `apps/web/projects/platform-core/src/lib/realtime/*.ts` | Realtime connection abstraction and notification envelope type. |
| `apps/web/projects/platform-core/src/lib/security/content-security-policy.ts`, `sanitization-policy.ts` | CSP builder and HTML sanitisation rules. |
| `apps/web/projects/customer-features/src/lib/chat/chat-shell.ts` | Chat screen: sends a turn for an existing session over SSE and announces stream events. Does not start a session. |
| `apps/web/projects/customer-features/src/lib/chat/feedback/feedback-control.ts` | Thumbs up/down control calling the feedback endpoints. |
| `apps/web/projects/customer-features/src/lib/{consent,session}/*-shell.ts` | Consent prompt and session list: structural shells, no behaviour implemented. |
| `apps/web/projects/customer-features/src/lib/handoff/handoff-shell.ts` | Hand-off notice telling the user a person will take the request. |
| `apps/web/projects/staff-features/src/lib/{queue,reporting,take-over}/*-shell.ts`, `staff-features.routes.ts` | Approval queue, reporting and take-over screens: structural shells with no behaviour, plus their role-gated routes. |
| `apps/web/projects/design-system/src/lib/a11y/*.ts` | Focus trap, live announcer, skip link. |
| `apps/web/projects/design-system/src/lib/states/*.ts`, `status/*.ts` | Loading / empty / partial-failure state components and status indicator. |
| `apps/web/e2e/a11y-scaffold.spec.ts`, `playwright.config.ts` | Playwright accessibility smoke test. |
| `apps/web/e2e/csp-hosting.spec.ts`, `playwright.csp.config.ts`, `scripts/csp-host.mjs` | The CSP baseline sent and obeyed: the server the portal image runs, and the tests that drive the built portals through it. |

### apps/desktop — Electron shell

| File | Purpose |
| ---- | ------- |
| `apps/desktop/src/main/index.ts` | Electron main-process composition root; only wiring, decisions live in sibling modules. |
| `apps/desktop/src/main/app-shell.ts` | Process-wide hardening and the IPC handler table (testable without Electron). |
| `apps/desktop/src/main/window.ts` | Secure `BrowserWindow` switches, exported as data so tests can assert each. |
| `apps/desktop/src/main/renderer-protocol.ts`, `csp.ts` | Serves the renderer bundle from the `app://renderer` scheme; applies the CSP from the main process via `onHeadersReceived`, with a nonce. |
| `apps/desktop/src/main/navigation.ts` | Deny-by-default navigation and new-window allow-list. |
| `apps/desktop/src/main/session-boundary.ts` | States and tests that the main process holds no token and takes no part in sign-in. |
| `apps/desktop/src/main/ipc-guard.ts`, `apps/desktop/src/ipc-contracts/index.ts` | IPC sender and argument validation; the typed channel allow-list. |
| `apps/desktop/src/main/endpoint-execution-boundary.ts` | Placeholder for endpoint script execution; executes nothing (FR-DEMO-016). |
| `apps/desktop/src/main/config.ts` | Validated, frozen host config: the origins the desktop may reach (feeds navigation and CSP `connect-src`). |
| `apps/desktop/src/preload/bridge.ts` | Preload script exposing the narrow renderer API via `contextBridge`. |
| `apps/desktop/scripts/stage-renderer.mjs` | Copies the `desktop-renderer` build into the Electron package. |
| `apps/desktop/tests/*.spec.ts` | Vitest checks for bridge surface, renderer contract and Electron security settings. |

## dotnet/ — read-only API (`Synthia.sln`)

| File | Purpose |
| ---- | ------- |
| `dotnet/src/Synthia.Api/Program.cs` | Host setup: Key Vault config, DI modules, middleware order, endpoint mapping. |
| `dotnet/src/Synthia.Api/Endpoints/CustomerViewEndpoints.cs` | Five customer `/views/*` GET routes. |
| `dotnet/src/Synthia.Api/Endpoints/StaffViewEndpoints.cs` | Seven staff `/views/*` GET routes with role requirements. |
| `dotnet/src/Synthia.Api/Endpoints/CursorEnvelope.cs` | `{items, nextCursor}` response wrapper. |
| `dotnet/src/Synthia.Api/Middleware/CorrelationMiddleware.cs` | Accepts/mints `X-Correlation-Id`, echoes it back. |
| `dotnet/src/Synthia.Api/Middleware/IdentityContextMiddleware.cs` | Builds the principal from `X-Idp-*`, rejects authority query params, admits the tenant; also holds `AudienceRouting`. |
| `dotnet/src/Synthia.Api/Middleware/RequestScope.cs` | Scoped holder for principal, tenant scope and correlation id. |
| `dotnet/src/Synthia.Api/Authorization/RoleFilter.cs` | `AcceptsRoles` / `AcceptsRolesOfCustomer` endpoint filters. |
| `dotnet/src/Synthia.Api/Querying/QueryBinding.cs`, `QueryDeclaration.cs`, `ResourceQueries.cs` | Parses `limit`/`cursor`/`sort`/filters against per-route whitelists. |
| `dotnet/src/Synthia.Api/Paging/OpaqueCursor.cs` | Encodes/decodes keyset cursors. |
| `dotnet/src/Synthia.Api/Errors/*.cs` | RFC 9457 problem helpers, exception handler, JSON options. |
| `dotnet/src/Synthia.Api/Contracts/ContractOpenApi.cs`, `ContractResponses.cs` | Per-audience OpenAPI documents (`customer`, `staff`) and response metadata. |
| `dotnet/src/Synthia.Api/Health/HealthEndpoints.cs` | `/health/live`, `/health/ready` (Npgsql check). |
| `dotnet/src/Synthia.Api/Configuration/*.cs` | Key Vault and Container Apps options, required-secret validation. |
| `dotnet/src/Synthia.Api/Http/OutboundHttpDefaults.cs` | Default timeouts/resilience for outbound `HttpClient`s. |
| `dotnet/src/Synthia.Api/appsettings.json` | Non-secret defaults (log levels, port, timeouts). |
| `dotnet/src/Synthia.Persistence/SynthiaReadContext.cs` | EF Core context; every entity `ToView(...)`, global tenant query filter. |
| `dotnet/src/Synthia.Persistence/Views/PublishedViewRows.cs` | View name constants and row classes for the 11 `vw_*_v1` views. |
| `dotnet/src/Synthia.Persistence/Paging/Keyset.cs` | Keyset pagination over `IQueryable`. |
| `dotnet/src/Synthia.Persistence/Conventions/*.cs` | Snake-case naming, enum↔text converters, read-only conventions, tenant filter builder. |
| `dotnet/src/Synthia.Persistence/PersistenceRegistration.cs`, `ReadDatabaseOptions.cs` | Registers the read context and its connection options. |
| `dotnet/src/Modules/Synthia.Modules.Sessions/SessionReadModel.cs` | Customer and staff session, message and step queries. |
| `dotnet/src/Modules/Synthia.Modules.Sessions/FeedbackReadModel.cs` | Session feedback and feedback-rate queries. |
| `dotnet/src/Modules/Synthia.Modules.Sessions/SortKeys.cs` | Sort key definitions for session/message paging. |
| `dotnet/src/Modules/Synthia.Modules.Approvals/ApprovalReadModel.cs` | Approval queue and unexecuted-approval queries. |
| `dotnet/src/Modules/Synthia.Modules.Audit/AuditReadModel.cs` | Audit search query. |
| `dotnet/src/Modules/Synthia.Modules.Tenancy/TenantRegistry.cs` | Tenant admission lookup (the only `IgnoreQueryFilters` call). |
| `dotnet/src/Modules/Synthia.Modules.Tenancy/TenantReadModel.cs` | Tenant list and platform dashboard rollup. |
| `dotnet/src/Modules/*/*ModuleRegistration.cs` | DI registration per module (Work and Governance currently register nothing). |
| `dotnet/src/Synthia.Contracts/ReadModels/*.cs` | Response DTOs (sessions, approvals, audit, tenants, dashboard). |
| `dotnet/src/Synthia.Contracts/Paging/*.cs`, `Querying/SortSpec.cs`, `Errors/ProblemTypes.cs`, `Boundaries/PlatformBoundaries.cs` | Paging/sort types, problem type URIs, boundary constants. |
| `dotnet/src/Synthia.SharedKernel/Identity/*.cs` | Identifier value types, principal factory, tenant context and scope interfaces. |
| `dotnet/src/Synthia.SharedKernel/Authorization/*.cs` | Staff roles and role-set intersection. |
| `dotnet/src/Synthia.SharedKernel/{Sessions,Work,Governance}/*.cs` | Session/work state enums, treatment and verdict types. |
| `dotnet/src/Synthia.Observability/*.cs` | OpenTelemetry + Azure Monitor registration and tag names. |
| `dotnet/Directory.Build.props`, `Directory.Packages.props`, `.editorconfig` | Shared build settings, central package versions, analyzers. |
| `dotnet/tests/Synthia.ArchitectureTests/*.cs` | Enforces no write endpoints, no migrations, no RagCore reference, module isolation, identity/Azure rules. |
| `dotnet/tests/Synthia.ContractTests/*.cs` | OpenAPI emission, API conventions, cursor contract, config validation, secret binding. |
| `dotnet/tests/Synthia.AuthorizationTests/*.cs`, `Synthia.TenantIsolationTests/*.cs` | Role matrix and tenant scope / aggregate-leak tests. |
| `dotnet/tests/Synthia.SharedKernel.Tests/{RoleIntersectionTests,VerdictTests}.cs` | Shared-kernel unit tests (other module test projects hold placeholders only). |

## ragcore/ — orchestration service (Python, FastAPI)

### API

| File | Purpose |
| ---- | ------- |
| `ragcore/src/ragcore/api/app.py` | App factory: lifespan (container, secrets, telemetry, run host), middleware, routers. |
| `ragcore/src/ragcore/api/deps.py` | FastAPI dependencies: container, correlation id, principal, tenant admission. |
| `ragcore/src/ragcore/api/customer/sessions.py` | `POST /sessions`, `POST /sessions/{id}/messages` (SSE). |
| `ragcore/src/ragcore/api/customer/streaming.py` | SSE frame encoding (`token`, `step`, `interrupt`, `done`, `error`). |
| `ragcore/src/ragcore/api/customer/feedback.py` | `PUT`/`DELETE /messages/{id}/feedback`. |
| `ragcore/src/ragcore/api/customer/negotiate.py` | `POST /realtime/negotiate`. |
| `ragcore/src/ragcore/api/customer/answers.py` | `POST /sessions/{id}/answers` (501). |
| `ragcore/src/ragcore/api/customer/routes.py` | Consent / instruction / result routes (501). |
| `ragcore/src/ragcore/api/customer/sample_flows.py` | Sample-flow routes (501). |
| `ragcore/src/ragcore/api/staff/routes.py` | Staff verdict / takeover / messages / cancel (501). |
| `ragcore/src/ragcore/api/workload/routes.py` | Workload claim / outcome (501). |
| `ragcore/src/ragcore/api/health.py` | `/health/live`, `/health/ready`. |
| `ragcore/src/ragcore/api/openapi.py` | Generates `/openapi.json` and per-audience contract documents. |
| `ragcore/src/ragcore/api/schemas.py` | Base Pydantic model (camelCase) and `ProblemDetails`. |
| `ragcore/src/ragcore/api/middleware/{correlation,identity,problems}.py` | Correlation id, identity-header guard, problem-detail handlers. No provenance layer (ADR-0008). |

### Configuration and infrastructure

| File | Purpose |
| ---- | ------- |
| `ragcore/src/ragcore/config/composition.py` | Composition root: builds `Container`, decides which adapters are bound; `graph_dependencies`. |
| `ragcore/src/ragcore/config/settings.py` | Pydantic settings (DB, AI gateway, retrieval, messaging, cache, Integrations edge address, observability). |
| `ragcore/src/ragcore/config/secrets.py` | Resolves Key Vault secret references at startup (`KeyVaultSecretResolver`). |
| `ragcore/src/ragcore/infrastructure/azure_credentials.py` | Single shared `DefaultAzureCredential`. |
| `ragcore/src/ragcore/infrastructure/cache.py` | Redis transient cache (Entra auth) or `NullCache`. |
| `ragcore/src/ragcore/infrastructure/clock.py` | System clock adapter. |
| `ragcore/src/ragcore/egress/http.py`, `validation.py` | Pooled outbound HTTP with timeouts/retry; validation of provider responses. |
| `ragcore/src/ragcore/platform_clients/integrations.py` | HTTP client for the Integrations Service via APIM, authenticated with RagCore's own workload token (bound only when configured; no live caller). |

### Persistence

| File | Purpose |
| ---- | ------- |
| `ragcore/src/ragcore/persistence/models.py` | SQLAlchemy table definitions for every `platform` table. |
| `ragcore/src/ragcore/persistence/repositories.py` | Tenant-scoped repositories (tenant registry, sessions, work items, approvals, consents, catalogue, outbox, audit, feedback, idempotency). |
| `ragcore/src/ragcore/persistence/integration_jobs.py` | `IntegrationDispatcher`: writes `integration_job` + outbox row; reads result columns. |
| `ragcore/src/ragcore/persistence/views.py` | The 13 published view definitions. |
| `ragcore/src/ragcore/persistence/engine.py` | Async engine, session factory, `UnitOfWork`, `current_session`. |
| `ragcore/src/ragcore/persistence/base.py`, `enums.py` | Declarative base and column conventions; PostgreSQL enum bindings. |
| `ragcore/src/ragcore/persistence/concurrency.py` | Optimistic concurrency (`guarded_update` on `version`). |
| `ragcore/src/ragcore/persistence/retention.py`, `erasure.py` | Retention windows per data class; per-tenant hard delete. |
| `ragcore/src/ragcore/persistence/autogenerate.py` | Alembic autogenerate filter (excludes `langgraph`). |
| `ragcore/migrations/env.py`, `alembic.ini` | Alembic environment; version table in `platform`. |
| `ragcore/migrations/versions/0001`–`0025_*.py` | Schema history: enums, 20 tables, trigger, 13 views, 4 roles and grants. |
| `ragcore/scripts/provision_checkpoint_schema.py` | Creates LangGraph checkpoint tables from the migration job. |
| `ragcore/scripts/emit_contracts.py` | Writes per-audience OpenAPI files to `build/contracts/ragcore/`. |

### Domain, governance and orchestration

| File | Purpose |
| ---- | ------- |
| `ragcore/src/ragcore/domain/*.py` | Pure domain types: identifiers, principal, roles, tenancy, work/session state, governance enums, envelopes, audit chain, proposal, decisions, errors. |
| `ragcore/src/ragcore/application/ports.py` | Protocol interfaces for every adapter the application/graph needs. |
| `ragcore/src/ragcore/application/sessions.py`, `cases.py` | Session lifecycle / triage gate; case creation rule. |
| `ragcore/src/ragcore/application/escalation.py`, `audit.py`, `cancellation.py` | Escalation hand-off, audit writing, cancellation-safe helpers. |
| `ragcore/src/ragcore/governance/gate.py` | Control gate turning a proposal into authorised work or a refusal. |
| `ragcore/src/ragcore/governance/policy.py`, `conditions.py` | Deterministic treatment policy; knowledge/ability/security conditions. |
| `ragcore/src/ragcore/governance/catalogue.py`, `fixtures.py` | Catalogue entry shape; four inert `synthia.reference.*` fixtures. |
| `ragcore/src/ragcore/graph/builder.py`, `state.py`, `projections.py` | LangGraph topology, typed state, enum→state literal mapping. |
| `ragcore/src/ragcore/graph/host.py`, `checkpointer.py`, `context.py`, `dependencies.py`, `threads.py` | Run host (turn → events), Postgres checkpointer, run context, graph dependency bundle, checkpoint thread key (organisation + requester + session). |
| `ragcore/src/ragcore/graph/nodes/*.py` | Graph nodes: intake, guardrail, classify, grounding, governance, clarification/consent/approval interrupts, execution, closure. |
| `ragcore/src/ragcore/execution/claim.py`, `idempotency.py` | Atomic claim (boundary 1) and idempotency key/replay (boundary 2). |
| `ragcore/src/ragcore/execution/executor.py`, `availability.py` | Execution + verification leg; entitled-but-unreachable outcome. |
| `ragcore/src/ragcore/retrieval/search.py` | Azure AI Search client with mandatory tenant filter. |
| `ragcore/src/ragcore/retrieval/hybrid.py`, `rerank.py`, `confidence.py`, `embedding.py` | Hybrid fusion, cost-gated rerank, confidence thresholds, embedding input. |
| `ragcore/src/ragcore/model/gateway.py`, `adapter.py`, `egress.py`, `local.py` | AI Gateway (APIM) model client, adapter, egress seam, local no-model stand-in. |
| `ragcore/src/ragcore/model/safety.py` | Inbound/outbound content safety checks. |
| `ragcore/src/ragcore/messaging/publisher.py`, `outbox.py`, `credentials.py` | Service Bus publisher, outbox writer, managed-identity client. |
| `ragcore/src/ragcore/messaging/retry.py`, `deadletter.py`, `tracecontext.py`, `sample_flow.py` | Retry policy, dead-letter handling, trace propagation, inert sample flow. |
| `ragcore/src/ragcore/notifications/signalr.py` | Azure SignalR REST notifier (not bound in the container). |
| `ragcore/src/ragcore/observability/*.py` | Azure Monitor telemetry, structured logging with redaction, sampling, propagation, agent metrics. |

### Workers (entry points raise `NotImplementedError`; functions are tested)

| File | Purpose |
| ---- | ------- |
| `ragcore/workers/outbox_dispatch.py` | `dispatch_once`: publishes undispatched outbox rows to Service Bus. |
| `ragcore/workers/resume_worker.py` | Parses trigger messages; dead-letters unhandled kinds. |
| `ragcore/workers/integration_result_worker.py` | Parses integration result messages; concludes from `integration_job` result columns. |
| `ragcore/workers/expiry_sweep.py` | `sweep_expired`: marks unclaimed work past `expires_at` as expired. |
| `ragcore/workers/retention_sweep.py` | `sweep_tenant`: deletes expired chat content and checkpoints per tenant. |
| `ragcore/workers/ingestion_run.py` | `open_run` / `close_run` for `ingestion_run`. |

### Tests

| File | Purpose |
| ---- | ------- |
| `ragcore/tests/conftest.py`, `tests/support/*.py` | Fixtures, fakes for ports, fake gateway and transport. |
| `ragcore/tests/migrations/*.py` | Up/down consistency, model-vs-DDL match, schema isolation. |
| `ragcore/tests/security/*.py` | Edge topology and trust policy, Azure identity, secret binding, DB grants (incl. Integrations), hard failures, leakage. |
| `ragcore/tests/governance/*.py`, `authorization/*.py` | Gate paths, no elevation, fixtures excluded, feedback has no influence, mid-flight role change. |
| `ragcore/tests/isolation/*.py` | Tenant isolation for DB and retrieval. |
| `ragcore/tests/integration/*.py`, `messaging/*.py`, `idempotency/*.py`, `concurrency/*.py` | Persistence, outbox crash, trace continuity, command/result messages, duplicate triggers, optimistic locking. |
| `ragcore/tests/contracts/*.py`, `architecture/*.py` | OpenAPI surface, layering, no connector/model/.NET dependency. |
| `ragcore/tests/unit/*.py`, `checkpoint/*.py`, `e2e/*.py`, `retention/*.py`, `egress/*.py` | Unit coverage of graph, roles, retrieval, cache, settings; checkpointer; AUTO golden path; retention classes; egress adapters. |

## integrations/ — Integrations Service (Python, FastAPI)

| File | Purpose |
| ---- | ------- |
| `integrations/src/integrations/api/app.py` | App factory: middleware, health and workload routers, OpenAPI path. |
| `integrations/src/integrations/api/workload/routes.py` | `GET /catalogue`, `POST /case-operations`. |
| `integrations/src/integrations/api/health.py` | `/health/live`, `/health/ready` with readiness registry. |
| `integrations/src/integrations/api/middleware/{correlation,identity,problems}.py` | Same pipeline as RagCore; identity expects a workload (app) principal. |
| `integrations/src/integrations/config/composition.py` | Builds the container; `servicenow` bound only when a secret resolver is passed. |
| `integrations/src/integrations/config/settings.py` | Settings (DSN, queues, observability). |
| `integrations/src/integrations/catalogue/repository.py` | `CatalogueRepository` (capabilities, entitlement, registered version) and `TenantResolver`. |
| `integrations/src/integrations/catalogue/registry.py` | `ConnectorRegistry.binding_for`: binding + connector endpoint. |
| `integrations/src/integrations/policy/checks.py` | `AccessPolicy.evaluate`: entitled → registered → version → binding. |
| `integrations/src/integrations/credentials/resolver.py` | Reads the credential reference view, resolves the secret via `SecretResolverPort`. |
| `integrations/src/integrations/connectors/servicenow/adapter.py` | ServiceNow case creation over HTTPS with bearer credential. |
| `integrations/src/integrations/connectors/graph/adapter.py` | Microsoft Graph adapter (not bound in the container). |
| `integrations/src/integrations/connectors/{duo,onelogin}/__init__.py` | Descriptions of Duo/OneLogin as MCP target systems; no adapter code. |
| `integrations/src/integrations/mcp/client.py` | MCP client for discovery/invocation (not bound in the container). |
| `integrations/src/integrations/execution/executor.py` | `ExecutionLeg.run`: load job, re-check, invoke once, record in one transaction. |
| `integrations/src/integrations/execution/idempotency.py`, `normalization.py` | Derived idempotency key; response normalisation/validation. |
| `integrations/src/integrations/persistence/engine.py` | Async engine, `Database` helper, readiness probe. |
| `integrations/src/integrations/persistence/jobs.py` | Loads `integration_job`; updates the four result columns. |
| `integrations/src/integrations/persistence/executions.py` | `execution_record` + `integration.outbox_message` writes and outbox claiming. |
| `integrations/src/integrations/persistence/audit.py` | INSERT into `platform.audit_event`. |
| `integrations/src/integrations/messaging/consumer.py`, `envelope.py`, `publisher.py` | Command consumer, 3-field envelopes, Service Bus result publisher. |
| `integrations/src/integrations/domain/*.py`, `application/ports.py` | Catalogue/execution domain types and ports. |
| `integrations/src/integrations/egress/http.py` | Resilient outbound HTTP with explicit timeouts. |
| `integrations/src/integrations/observability/*.py` | Logging and OpenTelemetry/Azure Monitor setup. |
| `integrations/workers/command_consumer.py` | Command-queue worker (`main` raises `NotImplementedError`; `handle_command` is tested). |
| `integrations/scripts/emit_contracts.py` | Writes `build/contracts/integrations/workload.v1.openapi.json`. |
| `integrations/tests/unit/*.py`, `security/*.py`, `architecture/test_layering.py` | Policy, audit, connectors, consumer, envelope, health; API boundary, APIM routing, identity; layering. |

## build/

| File | Purpose |
| ---- | ------- |
| `build/docker/{dotnet,ragcore,integrations}.Dockerfile` | Container images; RagCore/Integrations run `uvicorn … create_app --factory`. |
| `build/docker/portals.Dockerfile` | One image per browser portal (`--build-arg PORTAL`): builds the Angular bundle and serves it with the per-response-nonce CSP (ADR-0009). |
| `build/docker/migrate.job.yaml` | Container Apps job running Alembic + checkpoint provisioning. |
| `build/docker/containerapps/{monolith,ragcore,integrations}.yaml` | Container Apps definitions (env, probes, scaling, queue names). |
| `build/docker/containerapps/{customer,staff}-portal.yaml` | Portal Container Apps: internal ingress, no secret, no managed identity beyond the registry pull. |
| `build/infra/apim/apis.json`, `*.v1.xml`, `global.inbound.xml` | APIM API definitions and policies (JWT validation, `X-Idp-*` headers, routing per audience). |
| `build/infra/ai-gateway/policy.xml`, `providers.json` | AI Gateway (APIM) policy and model provider routing. |
| `build/infra/frontdoor/front-door.json` | Front Door in front of APIM. |
| `build/infra/identity/managed-identities.json` | Managed identities and Azure role assignments per service. |
| `build/infra/messaging/queues.json` | Service Bus queues (`synthia-triggers`, `synthia-integration-commands`, `synthia-integration-results`) and queue-scoped roles. |
| `build/infra/monitoring/telemetry.json` | Telemetry settings. |
| `build/policy/{azure-identity,edge-trust,openapi-disclosure}.json` | Machine-checked policies used by tests and guard scripts. |
| `build/contracts/**/*.openapi.json`, `approved-breaking-changes.json` | Published OpenAPI artifacts and the breaking-change allow-list. |
| `build/scripts/openapi_validate.py`, `openapi_diff.py` | Validate and diff OpenAPI artifacts in CI. |
| `build/scripts/check-*.sh`, `verify-*.sh` | Boundary, edge-path, architecture, contract and desktop-security guards. |
| `build/scripts/smoke-images.sh`, `edge_front_door.py` | Builds, starts and inspects every image; answers the structural Front Door questions `check-edge-path.sh` asks. |
| `build/scripts/dev.sh`, `dev.ps1` | Local development runner. |
| `.github/workflows/*.yml` | CI per component plus boundaries, contracts, migrations, security. |

## docs/

| File | Purpose |
| ---- | ------- |
| `docs/adr/0001`–`0008*.md` | Architecture decisions (ownership split, approval placement, migrations, script integrity, third-party systems, desktop CSP, integration boundary, deferred gateway provenance). |
| `docs/architecture/integrations-service-delta.md` | Changes introduced by the Integrations Service split. |
| `docs/current-implementation/*.md` | This documentation set. |
