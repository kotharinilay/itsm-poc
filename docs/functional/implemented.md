# Implemented Functional Knowledge — Synthia

**Scope.** This document records **only what the current codebase actually implements**. It was
derived exclusively from implementation artifacts: application source, automated tests, database
schema and migrations, ORM models, implemented API routes and generated contracts, executable
configuration, the LangGraph implementation, background workers, message publishers/consumers, the
Angular/Electron implementation, dependency manifests and build/CI scripts.

No repository prose documentation was used as evidence of functionality. Where an area is unbuilt,
that is stated as an implementation fact, evidenced by code that refuses, returns 501, raises
`NotImplementedError`, or binds `None`.

Commit inspected: `5cdcd26` on branch `speckit-to-claude`.

---

## 1. Deployables actually present

| Deployable | Location | Runtime | State |
|---|---|---|---|
| .NET read monolith (`Synthia.Api`) | `dotnet/` | ASP.NET Core minimal API, .NET 10 | Builds, 246 tests pass |
| RagCore | `ragcore/` | FastAPI + LangGraph, Python 3.12 | 1142 non-integration tests pass, 159 integration tests require Docker |
| Integrations Service | `integrations/` | FastAPI, Python 3.12 | 155 tests pass |
| Web portals | `apps/web` | Angular 20 workspace: `customer-portal`, `staff-portal`, `desktop-renderer` + 4 libraries | Builds; Karma + Playwright suites present |
| Desktop host | `apps/desktop` | Electron + TypeScript | 178 vitest tests pass; a packaged Windows installer exists in `apps/desktop/release/` |

Cross-deployable dependency is prevented by `build/scripts/check-boundaries.sh` and by
`dotnet/tests/Synthia.ArchitectureTests/NoRagCoreDependencyTests.cs` /
`ragcore/tests/architecture/test_no_dotnet.py`.

---

## 2. Actors and implemented entry points

Three audiences exist as **route prefixes**, and the prefix is what selects the authorization model:

- `/api/customer/v1` — end users (delegated credentials only)
- `/api/staff/v1` — staff (delegated credentials only)
- `/api/workload/v1` — app-credential callers

`Synthia.Api` implements customer and staff reads; RagCore implements customer writes/streaming and
declares staff/workload routes; the Integrations Service implements the workload integration surface.
`AudienceRouting.WorkloadPrefix` exists in the .NET tree but no route is mapped under it, so it 404s
from routing.

### 2.1 Implemented .NET read endpoints (all GET, no write endpoint exists)

Customer (`CustomerViewEndpoints.cs`), all requiring role `end_user`:

- `GET /api/customer/v1/views/sessions` — cursor-paged, optional `state` filter
- `GET /api/customer/v1/views/sessions/{sessionId}`
- `GET /api/customer/v1/views/sessions/{sessionId}/messages` — cursor-paged, optional `senderKind`
- `GET /api/customer/v1/views/sessions/{sessionId}/steps`
- `GET /api/customer/v1/views/sessions/{sessionId}/feedback`

Staff (`StaffViewEndpoints.cs`):

- `GET /api/staff/v1/views/sessions/live` — role `technician`, cursor-paged, `state`/`tenantId` filters
- `GET /api/staff/v1/views/sessions/{sessionId}` — role `technician`, returns session + step trail
- `GET /api/staff/v1/views/approvals/queue` — role `technician`, cursor-paged
- `GET /api/staff/v1/views/approvals/unexecuted` — role `technician`, cursor-paged
- `GET /api/staff/v1/views/audit` — role `technician`, cursor-paged, filters `tenantId`,
  `workItemId`, `eventKind`, `occurredFrom`, `occurredTo`
- `GET /api/staff/v1/views/dashboard/platform` — role `administrator`
- `GET /api/staff/v1/views/tenants` — role `administrator`, cursor-paged, `status` filter

Health: `GET /health/live` (process-only) and `GET /health/ready` (database-tagged health checks),
both excluded from the published documents. `MapOpenApi()` is served only in Development.

`NoWriteEndpointTests` walks the endpoint table and asserts no state-changing endpoint exists.

### 2.2 Implemented RagCore endpoints

Fully implemented:

- `POST /api/customer/v1/sessions` → 201, returns a freshly generated `sessionId`. **No work item and
  no database row is created here** — the handler generates a UUID and returns it.
- `POST /api/customer/v1/sessions/{sessionId}/messages` → `text/event-stream`. Runs one graph turn
  when the process holds a compiled graph; otherwise emits the empty stream (see §6.6).
- `PUT /api/customer/v1/messages/{messageId}/feedback` → 204, or 404 when the message is not the
  caller's own agent-authored message. Recorded through `FeedbackRepository` inside a unit of work.
- `DELETE /api/customer/v1/messages/{messageId}/feedback` → 204, idempotent.
- `POST /api/customer/v1/realtime/negotiate` → 200, returns `{url, group}` derived solely from the
  authenticated principal. Takes no body and no query parameters.
- `GET /health/live`, `GET /health/ready` (readiness checks PostgreSQL only; 503 otherwise).

Wired but deliberately inert — every one returns **501** with an RFC 9457 problem body, and the 501
is declared in the generated OpenAPI:

- `POST /api/customer/v1/sessions/{sessionId}/answers`
- `POST /api/customer/v1/work/{workItemId}/consent`
- `GET  /api/customer/v1/work/{workItemId}/instruction`
- `POST /api/customer/v1/work/{workItemId}/result`
- `POST /api/customer/v1/sample-flows/round-trip`
- `GET  /api/customer/v1/sample-flows/round-trip/{workItemId}`
- `POST /api/customer/v1/sample-flows/service-hop`
- `POST /api/staff/v1/approvals/{approvalId}/verdict`
- `POST /api/staff/v1/sessions/{sessionId}/takeover`
- `POST /api/staff/v1/sessions/{sessionId}/messages`
- `POST /api/staff/v1/work/{workItemId}/cancel`
- `POST /api/workload/v1/work/{workItemId}/claim`
- `POST /api/workload/v1/work/{workItemId}/outcome`

Request models for these routes are fully declared and validated by FastAPI (`ConsentRequest`,
`VerdictRequest`, `StaffMessageRequest`, `ExecutionResultRequest`, `AnswerRequest`), so the wire
contract is implemented even though the behaviour is not.

**Consequence of the above, as implemented:** no consent and no staff verdict can currently be
recorded through any HTTP surface. The repositories that read them exist and are exercised by tests,
but nothing writes them in production code.

### 2.3 Implemented Integrations Service endpoints

- `GET /api/workload/v1/integrations/catalogue?sessionId=…|workItemId=…` — exactly one identifier is
  required; both or neither is 400. Resolves tenant from the identifier, returns the entitled
  capability set with `entitled`, `available`, `isReferenceFixture`. `nextCursor` is always `null`.
- `POST /api/workload/v1/integrations/case-operations` — resolves tenant from `sessionId`, runs the
  full access-policy re-check, then calls the ServiceNow connector.
  - 404 unknown session; 403 refused by policy or `CredentialNotEntitledError`;
    **503 when the connector is unbound**; 502 on egress/boundary-validation failure.
- `GET /health/live`, `GET /health/ready`.

---

## 3. Authentication and authorization as actually enforced

### 3.1 Identity contract

No service parses an access token. Identity arrives as five closed headers, consumed identically in
.NET (`PrincipalFactory`) and Python (`ragcore/api/deps.py`, `integrations/api/middleware/identity.py`):

`X-Idp-Tenant-Id`, `X-Idp-Principal-Id`, `X-Idp-Roles`, `X-Idp-Credential-Class`,
`X-Idp-Client-Surface`.

`PrincipalFactory.TryCreate` fails closed on: non-GUID tenant/principal; credential class other than
`delegated`/`app`; empty/whitespace-padded/duplicated/unknown role tokens; role list not in ascending
ordinal order; `end_user` or `none` combined with any other role; and credential class not matching
the audience (workload ⇒ `app`, customer/staff ⇒ `delegated`). Rejection yields 401 and logs only a
reason enum — never the header values.

### 3.2 Self-asserted authority is refused, not ignored

`ForbiddenParameters` (.NET) and the identity middleware (Python) reject any request carrying
`tenant`, `tenantid`, `tid`, `organisation`, `organization`, `role`, `roles`, `audience`, `oid`,
`principalid` as a query parameter, with a validation problem. The **single exception** is `tenantId`
on the staff audience, which is applied as an extra `WHERE` clause beneath the global query filter —
it narrows, and cannot widen.

### 3.3 Role evaluation

Authorization is set intersection (`RoleIntersection.Evaluate`, `ragcore/domain/roles.py`): an empty
intersection denies, and an operation accepting no roles denies everyone. There is no hierarchy, no
ranking and no implied privilege — asserted by `Synthia.AuthorizationTests` (21 tests) including
`NoImpliedPrivilegeTests`.

On the customer audience, `AuthenticatedPrincipal.AuthorizableRoles` returns `{end_user}` regardless
of staff roles held, so staff roles confer nothing on a customer surface.

Denial status codes are implemented deliberately: **403** for a collection the caller may not operate
on; **404** for a specific resource belonging to someone else (sessions, messages, feedback).

### 3.4 Tenancy

- `TenantContext` is constructible only through provenance-named factories
  (`from_admitted_identity`, `from_work_item`, `from_platform_object`); there is no `from_request`.
- .NET: `IdentityContextMiddleware` binds operator-wide scope for the staff audience, and for a
  customer looks the Entra tenant up in `ITenantRegistry`. An unregistered tenant is **403**, not 401.
- `SynthiaReadContext` applies a global query filter on every tenant-scoped view combining
  `HasOrganisationScope`, `CurrentTenantId` and `IsOperatorWide`. An unbound scope reads **nothing**.
- RagCore repositories all derive from `_TenantScoped`; `RetrievalPort.search` takes a
  `TenantContext` as its first positional argument, so no unfiltered retrieval overload exists.
- Evidence: `Synthia.TenantIsolationTests` (11 tests, incl. `AggregateLeakageTests`),
  `Synthia.ContractTests/TenantIsolationContractTests.cs`, `ragcore/tests/isolation/*`.

---

## 4. Validation behaviour actually implemented

- .NET query binding (`QueryBinding`) rejects **unknown filter names** per endpoint against a declared
  whitelist, and validates page size, cursors, enums, GUIDs and timestamps. The audit endpoint
  additionally rejects `occurredFrom >= occurredTo`.
- Paging is opaque keyset cursors: Base64Url-encoded positions (`OpaqueCursor`), returned inside a
  `CursorEnvelope`. Contract-tested by `CursorContractTests`.
- JSON is camelCase in both directions on both stacks.
- Errors are RFC 9457 problem details everywhere, carrying a correlation identifier; every FastAPI
  router declares the problem responses it can return, so the emitted OpenAPI never advertises
  FastAPI's default `HTTPValidationError`.
- RagCore bounds inbound text: one chat turn is truncated at 8,000 characters; a clarification answer
  is truncated at `MAX_ANSWER_CHARACTERS`.
- Outbound third-party responses pass `egress/validation.py` (size limit, shape and type checks)
  before propagating.

---

## 5. Correlation, logging and telemetry

- Both stacks accept `X-Correlation-Id` only when well formed, generate one otherwise, echo it on the
  response, attach it as a trace tag and as OTel baggage, and open a logging scope with it.
- A rejected correlation value is never logged; only the fact of replacement is.
- .NET uses source-generated `LoggerMessage` with fixed event ids.
- `ragcore/observability/` implements telemetry configuration, sampling, W3C trace propagation and
  agent metrics; `messaging/tracecontext.py` captures and restores a `traceparent` across the queue so
  a resumed run continues the same trace.
- Policy files `build/policy/correlation-id.json`, `azure-identity.json`, `edge-trust.json`,
  `openapi-disclosure.json` are asserted by tests on both stacks.

---

## 6. LangGraph workflow — as implemented

### 6.1 Graph shape (`ragcore/src/ragcore/graph/builder.py`)

Nodes registered: `intake`, `converse`, `clarify`, `retrieve`, `ground`, `guardrail`, `propose`,
`classify`, `govern`, `await_consent`, `await_approval`, `execute`, `verify`, `close`.

Edges:

```
START → intake → converse → retrieve
clarify → retrieve
retrieve → ground → guardrail
guardrail  ─(conditional)→ propose | close
propose → classify
classify   ─(conditional)→ govern | END
govern     ─(conditional)→ execute | await_consent | await_approval | close
await_consent → govern
await_approval → govern
execute → verify → END
close → END
```

There is exactly **one** edge into `execute`, from the governance router. Nothing routes from
`retrieve` or `propose` to `execute`. Both suspension nodes route back to `govern`, never forward to
`execute`, so the gate is re-evaluated on resume.

Routing functions: `_route_after_guardrail` routes on the session state the guardrail wrote
(`closed_declined`/`escalated` → `close`, else `propose`); `_route_after_propose` returns `END` when
the `proposal` channel is empty; `route_after_govern` branches solely on the gate's `disposition` and
raises on an empty governance channel.

### 6.2 State (`graph/state.py`)

`AgentState` is a `TypedDict(total=False)` with JSON-native channels only:
`tenant_id`, `session_id`, `work_item_id`, `correlation_id`, `session_state`, `pending_interrupt`,
`conversation`, `retrieved`, `grounding`, `classification`, `proposal`, `governance`, `decision`,
`execution`, `verification`.

Reducers implemented:

- `conversation`, `retrieved` — append.
- `governance` — `seal_governance`: the `treatment` may only narrow (`is_narrowing`), otherwise
  `TreatmentWidenedError`; everything else may advance so a resumed run can move
  `suspend_for_approval → proceed`.
- `decision` — `seal_human_decision`: first decision wins, a later one is silently dropped here.
- `execution`, `verification` — `_seal`: write-once; an identical replay is accepted, a differing
  second write raises `StateChannelSealedError`.

There is no `authorized`, `roles`, `accepted_roles` or `tenant_override` channel anywhere in state.
`tests/unit/test_graph_state.py` asserts each `Literal` mirrors its domain enum exactly, and
`tests/governance/test_authority_boundary.py` asserts no node writes the tenant.

### 6.3 Run context and threads

`RunContext` (tenant, requester, correlation id, session id, optional work item id) is supplied per
invocation and is **not** checkpointed. Checkpoint threads are keyed
`f"{tenant_id}:{requester_oid}:{session_id}"` (`graph/threads.py`), so a session identifier alone
cannot resume another user's or another organisation's thread.

### 6.4 Checkpointing

`graph/checkpointer.py` is the only place a production graph is compiled
(`durable_graph`), against `AsyncPostgresSaver` in a dedicated `langgraph` schema. `checkpointer_dsn`
strips the SQLAlchemy `+driver` suffix and pins `search_path=langgraph`, and refuses a DSN that
already sets `options`. `provision_checkpoint_schema` creates the schema (`CREATE SCHEMA IF NOT
EXISTS`) and runs `setup()`; **no DDL runs at application startup**. Alembic excludes the `langgraph`
schema from autogenerate (`persistence/autogenerate.py`). No foreign key crosses between the
checkpoint schema and `platform`.

### 6.5 Interrupts and resume

Three interrupts are implemented with `langgraph.types.interrupt`:

| Node | Kind | Resume payload | Authority source |
|---|---|---|---|
| `clarify` | `clarification` | read (`resume_field`, string fields only) | none — text only |
| `await_consent` | `consent` | **discarded** | `ConsentRepositoryPort.decision_for` |
| `await_approval` | `approval` | **discarded** | `ApprovalRepositoryPort.decision_for` |

Interrupt payloads carry only `kind`, `sessionId`, optionally `workItemId`, and `correlationId` — no
approval state, no command content, no parameters.

Waking with no durable decision recorded re-suspends in the same `awaiting_*` state (`_still_awaiting`)
— it is neither an error nor a denial. Neither node writes a decision; the graph only reads them.
No timeout produces a verdict anywhere in the code.

### 6.6 Execution and verification nodes

`execute` re-checks the governance disposition at the point of effect and raises
`UnauthorizedExecutionError` for anything other than `proceed` — redundantly with the routing. It
derives idempotency key `f"{work_item_id}:{identity}"` (idempotency boundary 2) and calls
`ToolExecutionPort.invoke`. It writes both `execution` and `verification` channels.

`verify` is deliberately inert: it returns `{}`. With no verification tool, the only outcome
available is `client_attested`.

`close` moves the session to `closed_declined` and clears the pending interrupt.

### 6.7 Nodes that are intentionally inert

- `converse` — sets `session_state = resolving`; makes **no model call**.
- `propose` — returns `{}`; proposes nothing. A proposal enters only when a caller seeds the channel,
  which is what the golden-path tests do.
- `verify` — returns `{}`.
- `intake` — applies the deterministic triage heuristic and reports session state and the work item id
  from run context; it does not create the durable work record.

`graph/nodes/clarification_interrupt.py` exists but **is not registered in the graph**; only its
`MAX_ANSWER_CHARACTERS` constant is imported (by `api/customer/answers.py`).

### 6.8 The run host and the SSE stream

`RunHost.stream_turn` streams the graph and yields `step`, `interrupt`, then exactly one of `done` or
`error`. Step labels come from a closed `STEP_LABELS` map (a node without an entry emits nothing), and
carry no outcome. Exceptions yield an `error` event carrying no detail and are re-raised. `done` is
emitted even after a suspension. Cancellation is not caught anywhere.

**Critical implemented reality:** `graph_dependencies()` returns `None` if any required binding is
missing, and `build_container()` binds `execution=None` unconditionally (along with `case_system`,
`directory`, `discovery`). Therefore, in any normally composed RagCore process, `app.state.run_host`
is `None` and `POST /sessions/{id}/messages` returns `streaming.empty_stream(...)` — a `done` frame
only. **The graph runs only when a test supplies its own container/compiled graph.**

---

## 7. Deterministic governance — as implemented

### 7.1 Treatment assignment (`governance/policy.py`)

`assign_treatment(entry, is_entitled)` is a pure function returning one of four treatments plus a
reason, in this order:

1. no catalogue entry → `NOT_ALLOWED` / `not_in_catalogue`
2. not entitled → `NOT_ALLOWED` / `not_entitled`
3. `requires_elevation` → `NOT_ALLOWED` / `elevation_refused`
4. `STAFF_APPROVAL` with an empty accepted-role set → `NOT_ALLOWED` / `no_role_can_approve`
5. otherwise the catalogue default / `catalogue_default`

Every override routes through `_narrowed`, which raises `PolicyWidenedTreatmentError` on any widening.
There is no `UNKNOWN` treatment.

### 7.2 The gate (`governance/gate.py`)

`evaluate(GateRequest) -> GateOutcome` is pure: no clock call, no I/O, no catalogue lookup. It never
receives a treatment — it derives one. Order actually implemented:

1. tenant not admitted → refuse (`tenant_not_admitted`)
2. treatment `NOT_ALLOWED` → refuse (`treatment_refuses`)
3. knowledge condition withholds → refuse (`knowledge_withheld`) — **before** any treatment branch
4. `AUTO` → proceed
5. `END_USER_APPROVAL` → consent branch
6. `STAFF_APPROVAL` → approval branch

Consent branch checks: decision present (else suspend), type is `EndUserConsent` (a staff verdict here
is `wrong_decision_kind`), `consented_by == requester` (else `not_the_requester`), decision bound to
the same catalogue id **and version** (else `decision_bound_to_another_version`), verdict not refused,
and a window that is present and unexpired (`authorization_window_missing` / `authorization_expired`).

Approval branch additionally re-evaluates the role set intersection against the accepted roles on the
catalogue entry (`approver_holds_no_accepted_role`) and handles `rejected`.

A missing expiry **fails closed** — it is never treated as unlimited.

### 7.3 Catalogue

`governance_record` is keyed `(catalogue_id, version)` and carries `kind`, `default_treatment`,
`accepted_roles`, `is_reference_fixture`, `requires_elevation`, `risk_tier`, `commands`,
`content_hash`, `verification_tool`. A database `CHECK` constraint holds `requires_elevation = false`,
and another requires `version >= 1`.

Four inert reference fixtures are implemented (`ECHO`, `SELF_SERVICE_NOTE`, `STAFF_NOTE`, `WITHHELD`),
all prefixed `synthia.reference.` and flagged `is_reference_fixture=True`.
`reference_fixtures("production")` returns an empty catalogue. **No real ITSM operation exists in the
catalogue code.**

---

## 8. Persistence — as implemented

### 8.1 Schemas and migrations

Alembic, single linear head, revisions `0001` → `0025`, all in `ragcore/migrations/versions`. Two
schemas are owned by migrations (`platform`, `integration`); `langgraph` belongs to the checkpointer.

Tables created: `tenant_mapping`, `chat_session`, `message`, `session_step`, `feedback`, `work_item`,
`governance_record`, `tenant_entitlement`, `operation`, `approval`, `consent`, `audit_event`,
`outbox_message`, `idempotency_record`, `ingestion_run`, plus `integration_job`, connector registry /
bindings and integration execution tables in the `integration` schema.

Later revisions implement, as database objects rather than as application rules:

- `0017` — column-level permission boundary making the `work_item` authority fields immutable to the
  runtime principal
- `0018` — the eleven published `vw_*_v1` views
- `0019` — three database principals with disjoint rights (migration = DDL, RagCore runtime = DML +
  SELECT, .NET runtime = SELECT on views only)
- `0021`, `0022`, `0024`, `0025` — the Integrations principal's grants, including **INSERT on
  `audit_event` without SELECT**

### 8.2 Conventions actually enforced

- snake_case columns; enums stored as lower-snake (upper-snake for `ExecutionTreatment`).
- Optimistic concurrency via a `version` column on versioned rows; `concurrency.py` implements
  `guarded_update`, `require_guarded_update` (raising `ConcurrencyConflictError`) and `claim_once`.
  `idempotency_record` is the one documented exemption.
- Read Committed only; `engine.py` contains no Serializable path.
- `_TenantScoped` repositories always filter by tenant; `TenantRegistry` is the only unscoped one.
- `erasure.py` performs hard deletes per tenant and returns per-table row counts; there is no
  soft-delete flag.
- `retention.py` computes windows per class: chat content from the **terminal** state (90 days by
  default), audit from `occurred_at`, checkpoints from work completion; tenant overrides are read from
  `tenant_mapping.retention_overrides`.

### 8.3 Published read contract

`vw_session_summary_v1`, `vw_session_message_v1`, `vw_session_step_v1`, `vw_work_item_v1`,
`vw_approval_queue_v1`, `vw_approval_unexecuted_v1`, `vw_audit_event_v1`,
`vw_governance_catalogue_v1`, `vw_tenant_v1`, `vw_message_feedback_v1`, `vw_dashboard_rollup_v1`.

The .NET side maps every entity with `ToView` and `SynthiaReadContext.SaveChanges[Async]` throws
unconditionally. `NoMigrationTests` asserts no EF migration, `Database.Migrate()` or `EnsureCreated()`
exists in that tree. The governance catalogue view carries no tenant filter (it is platform-wide);
`tenant_entitlement` is deliberately not published.

---

## 9. Asynchronous and background behaviour

### 9.1 Transactional outbox

`messaging/outbox.py::enqueue_trigger` writes the state change and the message in one transaction.
`workers/outbox_dispatch.py::dispatch_once` publishes each row independently, tolerates duplicates by
design (send-then-mark), and never lets a blocked row block another.

Message bodies are exactly three fields — `{workItemId, correlationId, kind}` for triggers,
`{jobId, correlationId, kind}` for integration commands — implemented in `messaging/publisher.py` and
asserted by `tests/messaging/test_trigger_payload.py`.

Service Bus access is managed-identity only: `messaging/credentials.py` refuses connection strings,
shared access keys and SAS tokens.

### 9.2 Consumers

`workers/resume_worker.py` implements `parse_message` (raising `UndeserializableTriggerError`),
`refuse_unhandled_kind` producing a `DeadLetterReport`, and treats `kind` as a routing hint only —
authority is re-read from the durable work item.

`workers/integration_result_worker.py` implements `parse_result_message` and `concluded_from`, which
reads the outcome from RagCore's own `integration_job` result columns, never from the message. A
failure result does not cause a re-dispatch.

`integrations/workers/command_consumer.py` implements `handle_command` and a three-way settlement map
(complete / dead-letter / abandon). Dead-lettered messages are never auto-replayed
(`messaging/deadletter.py`, with a severity per trigger kind).

`messaging/retry.py` implements a backoff policy and `refuse_post_claim_retry`, which raises
`PostClaimRetryError` — there is no post-claim retry path.

### 9.3 Sweepers

`workers/expiry_sweep.py::sweep_expired`, `workers/retention_sweep.py::sweep_tenant` (chat content,
audit-window-following records, and checkpoint threads derived with the **same**
`checkpoint_thread_id` function the host uses), and `workers/ingestion_run.py::open_run`/`close_run`.

### 9.4 Worker process wiring — intentionally absent

Every worker's `main()` raises `NotImplementedError` with an explicit message: `expiry_sweep`,
`ingestion_run`, `integration_result_worker`, `outbox_dispatch`, `resume_worker`, `retention_sweep`,
and `integrations/workers/command_consumer`. The behaviour functions are implemented and tested; **no
worker process can currently be started.**

Ingestion acquisition, chunking and embedding are not implemented at all; only the run record is.

---

## 10. Execution leg and idempotency

Two distinct idempotency boundaries are implemented:

1. **Atomic claim** — `execution/claim.py::claim_for_execution`, a conditional update on
   `claimed_at IS NULL`; two racing consumers produce exactly one winner.
2. **Effect record** — `execution/idempotency.py` with `derive_key`, `begin_effect` returning a
   `ReplayDecision`, and `complete_effect`, protecting the external system.

`execution/executor.py::ExecutionLeg` keeps attempt and verification as two separate records and
raises `UnauthorizedExecutionError` without a proceed disposition.
`execution/availability.py` distinguishes *not entitled* from *entitled but unreachable*.

`ExecutionLeg` is exercised by `tests/e2e/test_auto_golden_path.py` but is **not bound into the
container or the graph** — the graph calls `ToolExecutionPort`, which is `None` in composition.

---

## 11. External integration behaviour

### 11.1 RagCore holds no connector

`build_container()` binds `case_system = directory = execution = discovery = None`, with the code
stating these must not gain an in-process implementation.
`tests/architecture/test_no_connector_in_ragcore.py` and `build/scripts/check-boundaries.sh` fail the
build if connector code reappears in that tree.

RagCore reaches external systems only through:

- `platform_clients/integrations.py::IntegrationsClient` (synchronous, over APIM) — bound when
  `integrations.is_configured`;
- `persistence/integration_jobs.py::IntegrationDispatcher` (asynchronous) — writes an
  `integration_job` row and publishes `{jobId, correlationId, kind}`.

### 11.2 Model egress

Every model call goes through `ModelEgressPort`. `_model_egress()` is the only place the choice is
made: `AiGatewayEgress` when a gateway is configured, otherwise `LocalDevelopmentEgress`, which calls
no model, produces a deterministic vector, and refuses to construct outside local development. No
provider SDK call exists; `tests/architecture/test_no_direct_model_call.py` asserts it.

`model/safety.py::SafeModel` implements bidirectional content-safety checking with
`ContentBlockedError`, but **no `ContentSafetyPort` implementation is bound and `SafeModel` is not
used outside its own module and tests** — the container binds a bare `GatewayModelAdapter`.

### 11.3 Retrieval

`AzureAiSearchRetrieval` is bound only when configured; otherwise `retrieval` stays `None` (and the
graph then cannot be composed — see §6.8). `retrieval/confidence.py` owns the absolute-score and
margin thresholds as module constants.

`retrieval/hybrid.py` (dense + sparse fusion) and `retrieval/rerank.py` (cross-encoder reranking) are
implemented and unit-tested, but **neither is bound**: no `SparseRetrievalPort` or `RerankerPort`
implementation exists in the tree.

### 11.4 Integrations Service connectors

`ServiceNowAdapter` and `MicrosoftGraphAdapter` are implemented; `McpClient` is implemented and
enforces that an advertised tool is not callable until registered and entitled.

Composition binds **only** ServiceNow, and only when a secret resolver is passed:
`build_container(secrets=None)`. `api/app.py` calls `build_container()` with no argument, so in a
normally started process `container.servicenow is None` and `POST /case-operations` returns **503**.
Neither the Graph adapter nor the MCP client is bound to any container field.

`credentials/resolver.py` resolves per-tenant credentials from Key Vault; `policy/checks.py`
implements the access-policy re-check at execution time.

---

## 12. Realtime behaviour

- RagCore: `POST /realtime/negotiate` returns an endpoint and a group derived solely from the
  principal (`user:{principalId}`). `notifications/signalr.py::SignalRNotifier` and `payload_for` are
  implemented, but `notifications` is `None` in the container and `SignalRNotifier` has **no reference
  anywhere outside its own module** — no notification is published.
- Web: `RealtimeService` depends on an optional `REALTIME_CONNECTION` port. No adapter is registered
  in any portal, so `messages$` is `EMPTY` and `connect()` is a no-op. On a reconnect the service
  raises `resyncRequired`, and surfaces re-read from the API rather than replaying missed messages.
- SSE is the implemented realtime path for chat (`text/event-stream`, event kinds `token`, `step`,
  `interrupt`, `done`, `error`).

---

## 13. Web implementation

Angular 20 workspace with four libraries (`design-system`, `platform-core`, `customer-features`,
`staff-features`) and three applications.

Implemented:

- Typed API clients (`CustomerApiClient`, `StaffApiClient`, `PlatformApiClient`,
  `MessageStreamClient`), correlation interceptor, problem-details typing, keyset paging types.
- `ChatShell` — consumes the SSE stream, renders progressive text and the step trail, tracks
  `pendingInterrupt` as a **kind only**, distinguishes failure from "nothing to say", and announces
  deltas accessibly via `LiveAnnouncer.announceDelta`. Unsubscribing aborts the request and changes no
  server state.
- `FeedbackControl`, `SessionShell`, `ConsentShell`, `HandoffShell` (customer);
  `QueueShell`, `TakeOverShell`, `ReportingShell` (staff) — the staff shells are **structural shells
  with signal state and no behaviour** (e.g. `QueueShell` holds `queue = signal(idle())` and never
  loads).
- Route guards `canMatchForPresentation([...])` gate staff routes by role **for presentation only**;
  `role-visibility.ts` is explicitly presentation-level, and `no-authz.spec.ts` asserts the client
  makes no authorization decision and holds no secret.
- `FORBIDDEN_STAFF_ROUTE_SEGMENTS` enumerates session-origination segments that must not exist on the
  staff surface, and the staff routes contain none.
- Security: `content-security-policy.ts`, `sanitization-policy.ts`; a CSP hosting harness
  (`scripts/csp-host.mjs` + `playwright.csp.config.ts`).
- Configuration is read from the hosting page (`readHostedConfig`), not compiled in.

Not implemented: `AuthService` registers **no** `ACCESS_TOKEN_PROVIDER`, so `accessToken()` returns
`EMPTY` and `status` stays `unknown` unless a surface calls `setSession` — nothing does. There is no
MSAL or identity-library integration in the tree.

---

## 14. Desktop implementation

Electron host (`apps/desktop`), packaged as an NSIS installer (a built artifact is committed under
`release/`).

Implemented and tested:

- A custom standard, secure renderer protocol; the window runs in its own session partition.
- A closed IPC contract of exactly four informational channels — `host:getVersion`,
  `host:getPlatform`, `host:getEndpoints`, `host:describeSessionBoundary` — each with an argument
  validator that fails closed on an unknown channel.
- `BRIDGE_SURFACE` exposes exactly those four members under a single global key `synthiaDesktop`.
- CSP construction and application (`csp.ts`), navigation restriction (`navigation.ts`), permission
  decisions (`decidePermission`), certificate-error handling (`shouldTrustCertificateError`), and a
  forbidden-switch check (`assertNoForbiddenSwitches`, including `no-sandbox`).
- Host configuration parses and validates origins from the environment and defaults to reaching
  nothing.

Intentionally unimplemented, and asserted as such: `endpoint-execution-boundary.ts` exports
`IS_IMPLEMENTED = false`; `executeApprovedScript` and `verifyScriptBindings` both always throw
`EndpointExecutionNotImplementedError`. **No script execution exists on the endpoint.**

---

## 15. Error and failure behaviour

- RFC 9457 problem details on every surface, at media type `application/problem+json`, always carrying
  a correlation identifier.
- 401 for an unusable identity context; 403 for an unregistered organisation or a role-set miss; 404
  for another party's resource; 422/400 for validation; 501 for wired-but-inert routes; 502 for an
  external system's failure (Integrations only); 503 for readiness failure or an unbound connector.
- SSE failures after headers are sent produce an `error` event with no detail, and the exception is
  re-raised.
- `asyncio.CancelledError` is never swallowed; `application/cancellation.py::shielded_cleanup`
  implements bounded cleanup around it.
- Platform defects are raised rather than absorbed: `UnauthorizedExecutionError`,
  `StateChannelSealedError`, `TreatmentWidenedError`, `PolicyWidenedTreatmentError`,
  `ConcurrencyConflictError`, `PostClaimRetryError`.
- Configuration failures stop the process at startup rather than surfacing per request (both Python
  services; .NET `RequiredSecretsValidator`).

---

## 16. Testing and verification actually present

Verified by running the suites in this working tree:

| Suite | Command | Result |
|---|---|---|
| RagCore (non-integration) | `pytest -q -m "not integration"` | **1142 passed**, 159 deselected |
| RagCore (integration) | `pytest -q -m integration` | 159 tests, require Docker/Testcontainers — not run here |
| Integrations | `pytest -q` | **155 passed** |
| .NET | `dotnet test Synthia.sln` | **246 passed** across 11 assemblies |
| Desktop | `vitest run` | **178 passed** in 4 files |
| Web architecture | `npm run test:architecture` | **9 passed** |
| Web unit (sample) | `ng test platform-core` | **28 passed** (Chrome Headless) |

### 16.1 Test categories that exist

- **Unit** — `ragcore/tests/unit/*` (23 files: state, interrupts, thread keys, roles, verdicts,
  treatment policy, confidence, hybrid, rerank, content safety, claim, cache, settings, correlation).
- **Architecture / boundary** — `ragcore/tests/architecture/*` (layering, package boundaries, no
  connector, no direct model call, no .NET dependency); `integrations/tests/architecture/test_layering.py`;
  `Synthia.ArchitectureTests` (88 tests: module isolation, composition root, banned APIs, data-access
  discipline, identity discipline, no write endpoint, no migrations, no RagCore dependency, APIM
  routing, Azure identity, edge trust).
- **Contract / API** — `ragcore/tests/contracts/*`, `Synthia.ContractTests` (51: OpenAPI emission, API
  conventions, cursor contract, configuration validation, secret binding, tenant isolation).
- **Database / migrations** — `ragcore/tests/migrations/*` (single head, upgrade/downgrade, schema
  isolation), `tests/integration/test_persistence.py`, `tests/concurrency/test_optimistic.py`.
- **Tenant isolation** — `ragcore/tests/isolation/*` (3 files incl. cross-tenant retrieval),
  `Synthia.TenantIsolationTests` (11).
- **Security** — `ragcore/tests/security/*` (Azure identity, edge topology, edge trust policy, hard
  failures, integration grants, no leakage, secret binding), `integrations/tests/security/*`,
  `apps/desktop/tests/security.spec.ts`, `apps/web/projects/platform-core/no-authz.spec.ts`,
  Gitleaks + `npm audit` + `dotnet list package --vulnerable` in CI.
- **Governance / authorization** — `ragcore/tests/governance/*` (7 files: authority boundary, auto
  path, not-allowed path, no elevation, unexercised gate refuses, feedback has no influence, fixtures
  excluded), `tests/authorization/test_role_change_midflight.py`, `Synthia.AuthorizationTests` (21).
- **LangGraph / workflow** — `tests/unit/test_graph_state.py`, `test_graph_interrupts.py`,
  `test_checkpoint_thread.py`, `tests/checkpoint/test_durable_checkpointer.py`.
- **Messaging / idempotency** — `tests/messaging/*`, `tests/idempotency/test_duplicate_trigger.py`,
  `tests/integration/test_outbox_crash.py`.
- **E2E** — `ragcore/tests/e2e/test_auto_golden_path.py`, which drives intake → retrieval → grounding
  → guardrail → proposal → classification → gate → execution → verification → audit against an
  `InMemorySaver`, and asserts the refusal path in the same file.
- **Frontend** — Karma unit specs across all 7 Angular projects; Playwright accessibility sweep
  (`e2e/a11y-scaffold.spec.ts`) and CSP hosting sweep (`e2e/csp-hosting.spec.ts`).
- **Electron** — `bridge-surface.spec.ts`, `no-policy.spec.ts`, `renderer-contract.spec.ts`,
  `security.spec.ts`.

### 16.2 Gates implemented in CI

Twelve GitHub Actions workflows: `ragcore`, `integrations`, `dotnet`, `web`, `desktop`, `contracts`,
`boundaries`, `edge`, `migrations`, `images`, `security`, `base-image-digests`.

Implemented gates include: ruff lint + format, `mypy --strict`, pytest; `dotnet build -warnaserror`,
`dotnet format --verify-no-changes`, `dotnet test`; eslint, prettier, `tsc -b`, Angular build, Karma,
Playwright a11y and CSP; Electron typecheck/lint/vitest/build.

The contracts workflow emits OpenAPI from all three services, **emits again and requires byte-identical
output**, validates the documents, compares them against the committed
`build/contracts/**/*.openapi.json`, and fails if the committed contracts are stale.

**Meta-verification is implemented**: `verify-architecture-guards.sh`, `verify-boundary-guard.sh`,
`verify-contract-guards.sh`, `verify-desktop-security-guard.sh` and `verify-edge-guard.sh` plant a
violation and assert the guard fails — i.e. the guards themselves are tested.

`images.yml` builds, starts and inspects every container image (`smoke-images.sh`).

### 16.3 Placeholder tests

The six `dotnet/tests/Synthia.Modules.*.Tests` projects each contain a single `PlaceholderTests` test.
Module-level behaviour is therefore unverified at that layer; the real coverage sits in the
architecture, contract, authorization and isolation suites.

---

## 17. Summary of intentionally inert or unimplemented areas

Each is demonstrated by code, not by prose:

| Area | Evidence |
|---|---|
| Consent recording | `POST /work/{id}/consent` → 501 |
| Staff verdict recording | `POST /approvals/{id}/verdict` → 501 |
| Session take-over, staff messages, work cancel | 501 |
| Workload claim / outcome | 501 |
| Clarification answer / resume | `POST /sessions/{id}/answers` → 501 |
| Execution instruction and result | 501 |
| Sample flows (3 routes) | 501 |
| Every background worker process | `main()` raises `NotImplementedError` (7 workers) |
| Model reasoning in the graph | `converse` and `propose` make no model call; `ModelPort` bound but unused by nodes |
| Verification | `verify` node returns `{}`; `UNVERIFIED = client_attested` |
| Endpoint script execution | `IS_IMPLEMENTED = false`; both functions always throw |
| Tool execution adapter | `execution=None` in composition ⇒ no run host ⇒ empty SSE stream |
| Connectors inside RagCore | `case_system/directory/discovery = None`, guarded by test + build script |
| Notifications | `notifications=None`; `SignalRNotifier` unreferenced |
| Realtime client transport | no `REALTIME_CONNECTION` provider registered |
| Client authentication | no `ACCESS_TOKEN_PROVIDER` registered; no MSAL in the tree |
| Content safety | `SafeModel` implemented, no `ContentSafetyPort` bound |
| Hybrid retrieval and reranking | implemented, no `SparseRetrievalPort`/`RerankerPort` bound |
| Microsoft Graph connector, MCP client | implemented, not bound to the Integrations container |
| ServiceNow connector in a deployed process | `build_container()` called without secrets ⇒ 503 |
| Ingestion acquisition/chunking/embedding | only the run record exists |
| Staff portal behaviour | shells hold idle signals and never load |
| Gateway-provenance verification in the backend | no such middleware stage exists in either stack |
| Real ITSM catalogue operations | only four inert reference fixtures, excluded in production |
| Session/work durable creation on `POST /sessions` | handler returns a generated UUID and writes nothing |

---

## 18. Areas where implementation evidence is insufficient

- **Integration test behaviour.** 159 RagCore tests are marked `integration` and require
  Testcontainers/Docker; they were not executed here, so migration upgrade/downgrade, published-view
  shape and persistence behaviour are asserted by test code but not observed running in this pass.
- **Deployed configuration.** `build/infra/**` and `build/docker/**` describe APIM, Front Door,
  messaging, identity and monitoring topology. These are executable configuration, but no deployed
  environment was available to confirm the runtime behaviour they produce.
- **Container image behaviour.** `smoke-images.sh` exercises image start-up in CI; not run here.
- **Angular suites beyond `platform-core`.** Only one of seven Karma projects and neither Playwright
  suite was executed in this pass.
- **Whether any process ever constructs a container with `execution` bound.** No such code path exists
  in the repository; the conclusion that the graph never runs in production composition follows from
  the absence of an adapter, which is evidence of absence only within this tree.

---

## 19. Discrepancies observed, recorded for a later conformance review

These are stated as observations only. No source, test, configuration or rule was changed.

1. **`POST /sessions/{id}/answers` returns 501 while the run host exists.** The route's own docstring
   says it is 501 "until the run loop is hosted", but `RunHost` and `durable_graph` are implemented and
   wired into the lifespan. The blocking fact is that `graph_dependencies()` returns `None`, not that
   the host is missing.
2. **The compiled graph is unreachable in normal composition.** `build_container()` binds
   `execution=None` unconditionally, so `app.state.run_host` is always `None` and the streaming
   endpoint always returns the empty stream. The full graph machinery is exercised only by tests.
3. **Two clarification-interrupt implementations exist.** `graph/nodes/conversation.py::make_clarify`
   is the registered node; `graph/nodes/clarification_interrupt.py` is a second, unregistered
   implementation from which only a constant is imported.
4. **The Integrations Service cannot perform a case operation as deployed.** `api/app.py` calls
   `build_container()` without a secret resolver, so `servicenow` is always `None` and the endpoint
   returns 503.
5. **Approval/consent reads have no corresponding writes.** `ApprovalRepository` and
   `ConsentRepository` decision reads are implemented and consumed by the graph, but every route that
   would record a decision returns 501.
6. **`HumanDecisionRecord.expires_at` is always `None`** in both `_mirror_consent` and
   `_mirror_verdict`, although the field exists and the gate resolves an expiry separately from the
   durable record.
7. **`GraphDependencies.model`, `work_items` and `audit` are bound but unused by any node** in the
   current node implementations.
8. **Backend gateway-provenance verification is absent in both stacks**, stated in code comments as
   deferred; what remains is network placement plus edge header deletion.
9. **Six .NET module test projects contain only placeholder tests**, so module-level behaviour has no
   direct verification.
10. **`CatalogueResponse.nextCursor` is hard-coded to `null`** on the Integrations catalogue endpoint,
    so the paging field is present but paging is not implemented.
