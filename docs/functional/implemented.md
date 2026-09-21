# Implemented Functional Knowledge — Synthia

**What this document is.** The canonical record of **what this repository demonstrably implements
today**. Every statement below was re-established from implementation artifacts in this audit:
application source, automated tests actually executed, database schema and migrations, ORM models,
implemented API routes, the generated OpenAPI contracts under `build/contracts/`, executable
configuration, the LangGraph implementation, background workers, message publishers and consumers,
the Angular and Electron implementation, dependency manifests, and the CI workflows.

**What this document is not.** Not a requirements document, not an architecture document, not a
roadmap, and not a summary of either. No repository prose — architecture documents, ADRs, the
platform specification or the Claude governance rules — was used as evidence that a capability
exists. Where a capability is absent, that absence is itself evidenced by
code: a `501` response, a `NotImplementedError`, an unconditional `None` binding, or a raised
refusal.

**Audited revision.** `de27d8156644322ee5889ba2a8c29fab99f876ea` (`de27d81`). The three commits preceding this audit (`9ab956e`, `d2d2c9d`, `de27d81`) touched
only `docs/` and `.claude/`; **no application artifact changed between `5cdcd26` and the audited
revision**, which was verified with `git diff --stat`. The findings below were nonetheless
re-derived from the code rather than carried forward, and several statements in the previous
generated snapshot were found to be wrong — see §19.

**Evidence scope.** Only files tracked by git were treated as source. Untracked build output —
`bin/`, `obj/`, `.venv/`, `__pycache__/`, `node_modules/`, Angular cache, `apps/desktop/release/` —
was excluded.

---

## Status taxonomy used throughout

| Label | Meaning |
|---|---|
| **Implemented** | Directly implemented and reachable in the normal production composition. |
| **Implemented but unbound** | The implementation exists; normal composition binds no dependency for it, so it cannot run. |
| **Wired but inert** | The surface exists and is reachable, and deliberately performs no operation (501, `{}`, no-op). |
| **Test-only** | Demonstrated only through test fixtures or test composition; not reachable in production composition. |
| **Not implemented** | Evidence exists that the capability is deliberately unavailable. |
| **Unverified** | Code exists and the repository contains no executable evidence of how it behaves. |

---

## 1. Deployables

Five deployables are present, buildable and tested. All test results below were produced by running
the suites in this working tree during this audit.

| Deployable | Location | Runtime | State | Test evidence |
|---|---|---|---|---|
| .NET read monolith (`Synthia.Api`) | `dotnet/` | ASP.NET Core minimal API, .NET 10 | **Implemented** — builds and runs; read-only | 246 tests pass across 11 assemblies |
| RagCore | `ragcore/` | FastAPI + LangGraph, Python 3.12 | **Implemented**, with the graph unreachable in production composition (§6.9) | 1142 pass, 159 integration tests deselected |
| Integrations Service | `integrations/` | FastAPI, Python 3.12 | **Implemented**, with the sole connector unbound in a deployed process (§11.4) | 155 tests pass |
| Web portals | `apps/web` | Angular 20 workspace — 3 applications, 4 libraries | **Implemented** for the customer chat surface; staff surface is structural only (§13) | 130 Karma tests pass across all 7 projects; 9 architecture tests pass |
| Desktop host | `apps/desktop` | Electron + TypeScript | **Implemented** as a secure shell; no endpoint execution (§14) | 178 vitest tests pass in 4 files |

Cross-deployable dependency is prevented mechanically by `build/scripts/check-boundaries.sh`,
`dotnet/tests/Synthia.ArchitectureTests/NoRagCoreDependencyTests.cs` and
`ragcore/tests/architecture/test_no_dotnet.py`.

**`apps/desktop/release/` is not tracked in git.** The packaging configuration exists
(`apps/desktop/package.json` → `build.win.target: ["nsis"]`, `dist:win` script), so an NSIS
installer is *producible*; no installer artifact is committed to the repository.

---

## 2. Entry points and API surfaces

Three audiences exist as route prefixes, and the prefix selects the authorization model:

- `/api/customer/v1` — end users, delegated credentials only
- `/api/staff/v1` — staff, delegated credentials only
- `/api/workload/v1` — app-credential callers

`Synthia.Api` implements customer and staff **reads**; RagCore implements the customer write and
streaming surface and declares the staff and workload surfaces; the Integrations Service implements
the workload integration surface.

`AudienceRouting.WorkloadPrefix` is declared in
`dotnet/src/Synthia.Api/Middleware/IdentityContextMiddleware.cs:194` and used only for audience
classification at line 214. No .NET route is mapped under it, so it 404s from routing.

### 2.1 .NET read endpoints — all Implemented, all GET

No state-changing endpoint exists in the .NET tree;
`Synthia.ArchitectureTests/NoWriteEndpointTests` walks the endpoint table and asserts it.

Customer (`dotnet/src/Synthia.Api/Endpoints/CustomerViewEndpoints.cs`), all requiring role
`end_user`:

| Method | Route | Behavior |
|---|---|---|
| GET | `/api/customer/v1/views/sessions` | Cursor-paged; optional `state` filter |
| GET | `/api/customer/v1/views/sessions/{sessionId}` | One session |
| GET | `/api/customer/v1/views/sessions/{sessionId}/messages` | Cursor-paged; optional `senderKind` |
| GET | `/api/customer/v1/views/sessions/{sessionId}/steps` | Step trail |
| GET | `/api/customer/v1/views/sessions/{sessionId}/feedback` | Feedback for the session |

Staff (`StaffViewEndpoints.cs`); the required role is declared per route with `.AcceptsRoles(...)`:

| Method | Route | Role | Behavior |
|---|---|---|---|
| GET | `/api/staff/v1/views/sessions/live` | `technician` | Cursor-paged; `state`/`tenantId` filters |
| GET | `/api/staff/v1/views/sessions/{sessionId}` | `technician` | Session plus step trail |
| GET | `/api/staff/v1/views/approvals/queue` | `technician` | Cursor-paged; discloses the full command |
| GET | `/api/staff/v1/views/approvals/unexecuted` | `technician` | Cursor-paged |
| GET | `/api/staff/v1/views/audit` | `technician` | Cursor-paged; `tenantId`, `workItemId`, `eventKind`, `occurredFrom`, `occurredTo` |
| GET | `/api/staff/v1/views/dashboard/platform` | `administrator` | Aggregate rollup only |
| GET | `/api/staff/v1/views/tenants` | `administrator` | Cursor-paged; `status` filter |

Health: `GET /health/live` (process only) and `GET /health/ready` (database-tagged health checks).
Both are excluded from the published documents; `MapOpenApi()` is served only in Development. The
committed contracts `build/contracts/dotnet/{customer,staff}.v1.openapi.json` contain exactly the
twelve view routes above and no health route.

### 2.2 RagCore endpoints

**Implemented:**

| Method | Route | Behavior |
|---|---|---|
| POST | `/api/customer/v1/sessions` | 201 with a freshly generated `sessionId`. `ragcore/src/ragcore/api/customer/sessions.py:85` returns `StartSessionResponse(session_id=uuid4())` and **writes no database row**. |
| POST | `/api/customer/v1/sessions/{sessionId}/messages` | `text/event-stream`. Runs one graph turn when the process holds a compiled graph; otherwise emits the empty stream — which is the only outcome in production composition (§6.9). |
| PUT | `/api/customer/v1/messages/{messageId}/feedback` | 204, or 404 when the message is not the caller's own agent-authored message. Written through `FeedbackRepository` inside a unit of work. |
| DELETE | `/api/customer/v1/messages/{messageId}/feedback` | 204, idempotent. |
| POST | `/api/customer/v1/realtime/negotiate` | 200 with `{url, group}` derived solely from the authenticated principal. No body, no query parameters. |
| GET | `/health/live`, `/health/ready` | Readiness probes PostgreSQL only; 503 otherwise. |

**Wired but inert** — thirteen routes, each returning **501** with an RFC 9457 problem body, each
501 declared in the generated OpenAPI:

| Method | Route |
|---|---|
| POST | `/api/customer/v1/sessions/{sessionId}/answers` |
| POST | `/api/customer/v1/work/{workItemId}/consent` |
| GET | `/api/customer/v1/work/{workItemId}/instruction` |
| POST | `/api/customer/v1/work/{workItemId}/result` |
| POST | `/api/customer/v1/sample-flows/round-trip` |
| GET | `/api/customer/v1/sample-flows/round-trip/{workItemId}` |
| POST | `/api/customer/v1/sample-flows/service-hop` |
| POST | `/api/staff/v1/approvals/{approvalId}/verdict` |
| POST | `/api/staff/v1/sessions/{sessionId}/takeover` |
| POST | `/api/staff/v1/sessions/{sessionId}/messages` |
| POST | `/api/staff/v1/work/{workItemId}/cancel` |
| POST | `/api/workload/v1/work/{workItemId}/claim` |
| POST | `/api/workload/v1/work/{workItemId}/outcome` |

Twelve of these are decorated with the shared `**NOT_IMPLEMENTED_ROUTE` mapping; `answers` declares
`status_code=501` directly (`ragcore/src/ragcore/api/customer/answers.py:77`) because it also
declares a validated `AnswerRequest` body.

Request models for these routes are fully declared and validated by FastAPI (`ConsentRequest`,
`VerdictRequest`, `StaffMessageRequest`, `ExecutionResultRequest`, `AnswerRequest`), so **the wire
contract is implemented while the behavior is not**.

**Consequence, as implemented:** no consent and no staff verdict can be recorded through any HTTP
surface in this repository. The repositories that *read* them are implemented and are consumed by the
graph, but no production code path writes one.

### 2.3 Integrations Service endpoints — Implemented

| Method | Route | Behavior |
|---|---|---|
| GET | `/api/workload/v1/integrations/catalogue?sessionId=…\|workItemId=…` | Exactly one identifier required; both or neither is 400. Resolves the tenant from the identifier and returns the entitled capability set with `entitled`, `available`, `isReferenceFixture`. |
| POST | `/api/workload/v1/integrations/case-operations` | Resolves the tenant from `sessionId`, runs the full access-policy re-check, then calls the ServiceNow connector. 404 unknown session; 403 refused by policy or `CredentialNotEntitledError`; **503 when the connector is unbound**; 502 on egress or boundary-validation failure. |
| GET | `/health/live`, `/health/ready` | Readiness probes the database. |

`CatalogueResponse.next_cursor` is hard-coded to `None`
(`integrations/src/integrations/api/workload/routes.py:210`): the paging field is part of the wire
contract, and paging is **not implemented**.

---

## 3. Authentication and authorization as actually enforced

### 3.1 Identity contract — Implemented

No service parses an access token. Identity arrives as five closed headers, consumed identically by
`dotnet/src/Synthia.SharedKernel/Identity/PrincipalFactory.cs`, `ragcore/src/ragcore/api/deps.py`
and `integrations/src/integrations/api/middleware/identity.py`:

`X-Idp-Tenant-Id`, `X-Idp-Principal-Id`, `X-Idp-Roles`, `X-Idp-Credential-Class`,
`X-Idp-Client-Surface`.

`PrincipalFactory.TryCreate` fails closed on: a non-GUID tenant or principal; a credential class
other than `delegated`/`app`; an empty, whitespace-padded, duplicated or unknown role token; a role
list not in ascending ordinal order; `end_user` or `none` combined with any other role; and a
credential class not matching the audience (workload ⇒ `app`, customer/staff ⇒ `delegated`).
Rejection yields 401 and logs a reason enum only — never the header values.

### 3.2 Self-asserted authority is refused — Implemented

`ForbiddenParameters` (.NET) and the Python identity middleware reject any request carrying
`tenant`, `tenantid`, `tid`, `organisation`, `organization`, `role`, `roles`, `audience`, `oid` or
`principalid` as a query parameter, with a validation problem. The **single exception** is `tenantId`
on the staff audience, applied as an additional `WHERE` clause beneath the global query filter — it
narrows and cannot widen.

### 3.3 Role evaluation — Implemented

Authorization is set intersection (`RoleIntersection.Evaluate`, `ragcore/domain/roles.py`). An empty
intersection denies; an operation accepting no roles denies everyone. There is no hierarchy, no
ranking and no implied privilege, asserted by `Synthia.AuthorizationTests` (21 tests) including
`NoImpliedPrivilegeTests`.

On the customer audience `AuthenticatedPrincipal.AuthorizableRoles` returns `{end_user}` regardless
of staff roles held, so staff roles confer nothing on a customer surface.

Denial codes are deliberate: **403** for a collection the caller may not operate on; **404** for a
specific resource belonging to someone else (sessions, messages, feedback).

### 3.4 Gateway provenance — Not implemented

Neither stack verifies that a request arrived through the gateway. What is implemented is network
placement plus edge header deletion (`build/policy/edge-trust.json` and the edge tests). The code
records the absence as deferred. Backend provenance verification does not exist in either stack.

---

## 4. Multi-tenancy and isolation

**Implemented:**

- `TenantContext` is constructible only through provenance-named factories
  (`from_admitted_identity`, `from_work_item`, `from_platform_object`). There is no `from_request`.
- .NET `IdentityContextMiddleware` binds operator-wide scope for the staff audience, and for a
  customer looks the Entra tenant up in `ITenantRegistry`. An unregistered tenant is **403**, not 401.
- `SynthiaReadContext` applies a global query filter on every tenant-scoped view combining
  `HasOrganisationScope`, `CurrentTenantId` and `IsOperatorWide`. **An unbound scope reads nothing.**
- Every RagCore repository derives from `_TenantScoped`; `TenantRegistry` is the only unscoped one.
- `RetrievalPort.search` takes a `TenantContext` as its first positional argument, so no unfiltered
  retrieval overload exists.
- The Integrations Service learns a tenant only by resolving a durable platform object
  (`TenantResolver`), never from a request field.

Evidence: `Synthia.TenantIsolationTests` (11 tests, including `AggregateLeakageTests`),
`Synthia.ContractTests/TenantIsolationContractTests.cs`, and `ragcore/tests/isolation/` (3 files,
including cross-tenant retrieval).

---

## 5. Validation and API contracts

**Implemented:**

- .NET query binding (`QueryBinding`) rejects **unknown filter names** per endpoint against a
  declared whitelist, and validates page size, cursors, enums, GUIDs and timestamps. The audit
  endpoint additionally rejects `occurredFrom >= occurredTo`.
- Paging is opaque keyset cursors: Base64Url-encoded positions (`OpaqueCursor`) returned inside a
  `CursorEnvelope`, contract-tested by `CursorContractTests`.
- JSON is camelCase in both directions on both stacks.
- Errors are RFC 9457 problem details everywhere at `application/problem+json`, carrying a
  correlation identifier. Every FastAPI router declares the problem responses it can return, so the
  emitted OpenAPI never advertises FastAPI's default `HTTPValidationError`.
- RagCore bounds inbound text: one chat turn is truncated at `MAX_MESSAGE_CHARACTERS` (8,000); a
  clarification answer is truncated at `MAX_ANSWER_CHARACTERS`.
- Outbound third-party responses pass `egress/validation.py` (size limit, shape and type checks)
  before propagating.

The committed OpenAPI documents under `build/contracts/` are the exposed wire contract and are
regenerated and byte-compared in CI (§16.3).

---

## 6. LangGraph workflow — as implemented

Derived entirely from `ragcore/src/ragcore/graph/**` and `ragcore/tests/`. Where the implementation
differs from any architecture document, the implementation is what is described here.

### 6.1 Graph topology (`graph/builder.py`) — Implemented

Fourteen nodes are registered: `intake`, `converse`, `clarify`, `retrieve`, `ground`, `guardrail`,
`propose`, `classify`, `govern`, `await_consent`, `await_approval`, `execute`, `verify`, `close`.

```text
START → intake → converse → retrieve
clarify → retrieve
retrieve → ground → guardrail
guardrail  ─(conditional: _route_after_guardrail)→ propose | close
propose → classify
classify   ─(conditional: _route_after_propose)→ govern | END
govern     ─(conditional: route_after_govern)→ execute | await_consent | await_approval | close
await_consent  → govern
await_approval → govern
execute → verify → END
close → END
```

There is exactly **one** edge into `execute`, from the governance router. Nothing routes from
`retrieve` or `propose` to `execute`. Both suspension nodes route back to `govern`, never forward to
`execute`, so the gate is re-evaluated on every resume.

Routing functions, as implemented:

- `_route_after_guardrail` routes on the session state the guardrail wrote — `closed_declined` or
  `escalated` → `close`, otherwise `propose`.
- `_route_after_propose` is registered on the **`classify`** node, not on `propose`. It returns `END`
  when the `proposal` channel is `None`, and `govern` otherwise.
- `route_after_govern` branches solely on the gate's `disposition` and raises on an empty governance
  channel.

### 6.2 State shape (`graph/state.py`) — Implemented

`AgentState` is a `TypedDict(total=False)` with fifteen JSON-native channels: `tenant_id`,
`session_id`, `work_item_id`, `correlation_id`, `session_state`, `pending_interrupt`,
`conversation`, `retrieved`, `grounding`, `classification`, `proposal`, `governance`, `decision`,
`execution`, `verification`.

Reducers, as implemented:

| Channel | Reducer | Behavior |
|---|---|---|
| `conversation`, `retrieved` | `_append` | Append. |
| `governance` | `seal_governance` | `treatment` may only narrow (`is_narrowing`), otherwise `TreatmentWidenedError`. Other fields may advance, so a resumed run can move `suspend_for_approval → proceed`. |
| `decision` | `seal_human_decision` | First decision wins; a later one is silently dropped. |
| `execution` | `seal_execution` | Write-once. An identical replay is accepted; a differing second write raises `StateChannelSealedError`. |
| `verification` | `seal_verification` | Write-once, same rule. |

`grounding`, `classification` and `proposal` have no reducer — last write wins.

There is no `authorized`, `roles`, `accepted_roles` or `tenant_override` channel anywhere in state.
`tests/unit/test_graph_state.py` asserts each `Literal` mirrors its domain enum exactly, and
`tests/governance/test_authority_boundary.py` asserts no node writes the tenant.

### 6.3 Run context and thread identity — Implemented

`RunContext` (tenant, requester, correlation id, session id, optional work item id) is supplied per
invocation and is **not** checkpointed. Checkpoint threads are keyed
`f"{tenant_id}:{requester_oid}:{session_id}"` (`graph/threads.py`), so a session identifier alone
cannot resume another user's or another organisation's thread. Verified by
`tests/unit/test_checkpoint_thread.py`.

### 6.4 Checkpointing — Implemented

`graph/checkpointer.py` is the only place a production graph is compiled (`durable_graph`), against
`AsyncPostgresSaver` in a dedicated `langgraph` schema. `checkpointer_dsn` strips the SQLAlchemy
`+driver` suffix, pins `options=-c search_path=langgraph` on the connection, and refuses a DSN that
already sets `options`. `provision_checkpoint_schema` issues `CREATE SCHEMA IF NOT EXISTS` and runs
the library's `setup()`; **no DDL runs at application startup**. Alembic excludes the `langgraph`
schema from autogenerate (`persistence/autogenerate.py`). No foreign key crosses between the
checkpoint schema and `platform`. Verified by `tests/checkpoint/test_durable_checkpointer.py` and
`tests/migrations/`.

### 6.5 Interrupts — Implemented

Three interrupts use `langgraph.types.interrupt`:

| Node | Kind | Resume payload | Where authority comes from |
|---|---|---|---|
| `clarify` | `clarification` | read (`resume_field`, string fields only) | none — text only |
| `await_consent` | `consent` | **discarded** | `ConsentRepositoryPort.decision_for` |
| `await_approval` | `approval` | **discarded** | `ApprovalRepositoryPort.decision_for` |

Interrupt payloads carry only `kind`, `sessionId`, optionally `workItemId`, and `correlationId` — no
approval state, no command content, no parameters.

### 6.6 Resume behavior — Implemented

Waking with no durable decision recorded re-suspends in the same `awaiting_*` state (`_still_awaiting`
in `graph/nodes/interrupts.py`) — neither an error nor a denial. Neither suspension node writes a
decision; the graph only reads them. **No timeout produces a verdict anywhere in the code.**

Because both suspension nodes edge back to `govern`, the gate re-runs against the current tenant
status and the current clock on every resume.

### 6.7 Execution and verification nodes

`execute` (**Implemented**) re-checks the governance disposition at the point of effect and raises
`UnauthorizedExecutionError` for anything other than `proceed` — redundantly with the routing. It
derives idempotency key `f"{work_item_id}:{identity}"` (idempotency boundary 2), calls
`ToolExecutionPort.invoke`, and writes **both** the `execution` and `verification` channels.

`verify` (**Wired but inert**) returns `{}` — the verification record was already written by
`execute`. With no verification tool bound, the only outcome available is `client_attested`.

`close` (**Implemented**) moves the session to `closed_declined` and clears the pending interrupt.

### 6.8 Nodes that are intentionally inert or partial

| Node | State | Evidence |
|---|---|---|
| `converse` | **Wired but inert** | Sets `session_state = resolving` and returns; makes no model call (`graph/nodes/conversation.py:39`). |
| `propose` | **Wired but inert** | Returns `{}`; proposes nothing. A proposal enters the channel only when a caller seeds it, which is what the golden-path tests do (`graph/nodes/grounding.py:143`). |
| `verify` | **Wired but inert** | Returns `{}` (`graph/nodes/execution.py:120`). |
| `intake` | **Implemented, partial** | Applies the deterministic triage heuristic and reports session state plus the work item id **from run context**; it does not create the durable work record. |
| `guardrail` | **Implemented** | A real deterministic scope decision; returns `{}` only on the allow path. |
| `retrieve`, `ground`, `classify`, `govern` | **Implemented** | Real logic; each returns `{}` only on its declared empty-input path. |

`graph/nodes/clarification_interrupt.py` exists and is **not registered in the graph** — it is a
second, unreachable clarification implementation. Only its `MAX_ANSWER_CHARACTERS` constant is
imported, by `api/customer/answers.py`.

### 6.9 The run host and the streaming path — the decisive fact

`RunHost.stream_turn` (`graph/host.py`) streams the graph and yields `step`, `interrupt`, then
exactly one of `done` or `error`. Step labels come from a closed `STEP_LABELS` map of eleven entries
(a node without an entry emits nothing) and carry no outcome. Exceptions yield an `error` event
carrying no detail and are re-raised. `done` is emitted even after a suspension. Cancellation is not
caught anywhere.

**The graph is Implemented but unbound in production composition.**
`ragcore/src/ragcore/config/composition.py:309` binds `execution=None` **unconditionally** (alongside
`case_system`, `directory` and `discovery`), and `graph_dependencies()` returns `None` if any
required binding is missing. Therefore, in any normally composed RagCore process,
`app.state.run_host` is `None` (`api/app.py:139`) and
`POST /api/customer/v1/sessions/{sessionId}/messages` returns `streaming.empty_stream(...)` — a
single `done` frame. `retrieval` is a second unconditional blocker whenever Azure AI Search is
unconfigured.

**The compiled graph runs only when a test supplies its own container or compiled graph.** Everything
in §6.1–§6.8 is therefore **test-only** behavior with respect to the deployed customer message path,
even though each piece is individually implemented and tested.

### 6.10 SSE event kinds

`StreamEventKind` (`api/customer/streaming.py:45`) declares five kinds: `token`, `step`, `interrupt`,
`done`, `error`. The graph-layer `TurnEventKind` declares four — **there is no `token` member**, and
the code states the absence is honest because no model call is made. `token` is consequently a
**declared wire contract kind with no producer anywhere in the repository**. The published OpenAPI
description of the streaming route enumerates all five from `StreamEventKind`.

---

## 7. Deterministic governance — as implemented

### 7.1 Treatment assignment (`governance/policy.py`) — Implemented

`assign_treatment(entry, is_entitled)` is a pure function returning one of four treatments plus a
reason, evaluated in this order:

1. no catalogue entry → `NOT_ALLOWED` / `not_in_catalogue`
2. not entitled → `NOT_ALLOWED` / `not_entitled`
3. `requires_elevation` → `NOT_ALLOWED` / `elevation_refused`
4. `STAFF_APPROVAL` with an empty accepted-role set → `NOT_ALLOWED` / `no_role_can_approve`
5. otherwise the catalogue default / `catalogue_default`

Every override routes through `_narrowed`, which raises `PolicyWidenedTreatmentError` on any
widening. There is no `UNKNOWN` treatment.

### 7.2 The gate (`governance/gate.py`) — Implemented

`evaluate(GateRequest) -> GateOutcome` is pure: no clock call, no I/O, no catalogue lookup. It never
receives a treatment — it derives one. Order as implemented:

1. tenant not admitted → refuse (`tenant_not_admitted`)
2. treatment `NOT_ALLOWED` → refuse (`treatment_refuses`)
3. knowledge condition withholds → withhold — **before** any treatment branch
4. `AUTO` → proceed
5. missing catalogue entry → refuse (`treatment_refuses`)
6. `END_USER_APPROVAL` → consent branch
7. otherwise → approval branch

Consent branch checks: decision present (else suspend); type is `EndUserConsent` (a staff verdict
here is `wrong_decision_kind`); `consented_by == requester` (else `not_the_requester`); decision bound
to the same catalogue id **and version** (else `decision_bound_to_another_version`); verdict not
refused; and an authorization window that is present and unexpired
(`authorization_window_missing` / `authorization_expired`).

Approval branch additionally re-evaluates the role-set intersection against the accepted roles on the
catalogue entry (`approver_holds_no_accepted_role`) and handles `rejected`.

**A missing expiry fails closed** — it is never treated as unlimited.

### 7.3 Catalogue and reference fixtures

`governance_record` is keyed `(catalogue_id, version)` and carries `kind`, `default_treatment`,
`accepted_roles`, `is_reference_fixture`, `requires_elevation`, `risk_tier`, `commands`,
`content_hash`, `verification_tool`. A database `CHECK` constraint holds `requires_elevation = false`;
another requires `version >= 1`.

Four inert reference fixtures are implemented (`ECHO`, `SELF_SERVICE_NOTE`, `STAFF_NOTE`, `WITHHELD`),
all prefixed `synthia.reference.` and flagged `is_reference_fixture=True`.
`reference_fixtures(environment)` **raises `ReferenceFixtureInProductionError`** when
`environment == "production"` (`governance/fixtures.py:195`) — it does not return an empty catalogue.
**No real ITSM operation exists in the catalogue code.**

---

## 8. Persistence and data lifecycle

### 8.1 Schemas and migrations — Implemented

Alembic is the sole schema mechanism. `ragcore/migrations/versions/` holds **25 revisions**,
`0001_platform_schema` → `0025_integrations_recovery_views`, in a **single linear head** (verified by
walking `down_revision` in this audit; also asserted by `ragcore/tests/migrations/`). The .NET side
owns no migrations, asserted by `dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs`.

Two schemas are owned by migrations — `platform` and `integration`; `langgraph` belongs to the
checkpoint library.

Tables created: `tenant_mapping`, `chat_session`, `message`, `session_step`, `feedback`, `work_item`,
`governance_record`, `tenant_entitlement`, `operation`, `approval`, `consent`, `audit_event`,
`outbox_message`, `idempotency_record`, `ingestion_run`, plus `integration_job`, the connector
registry and bindings, and the integration execution tables in the `integration` schema.

Later revisions implement, as database objects rather than application rules:

- `0017_work_item_immutability` — a column-level permission boundary and trigger making the
  `work_item` authority fields immutable to the runtime principal.
- `0018` — the eleven monolith read views (`ALL_VIEWS`).
- `0019_database_principals` — three principals with disjoint rights: the migration job holds DDL,
  the RagCore runtime holds DML + SELECT, the .NET runtime holds SELECT on views only.
- `0021_integrations_principal` — creates the **two** Integrations read views
  (`INTEGRATION_READ_VIEWS`) and grants them to that principal alone.
- `0022`, `0024`, `0025` — further Integrations grants, including **INSERT on `audit_event` without
  SELECT**, and SELECT on four recovery views.

### 8.2 Conventions actually enforced — Implemented

- snake_case columns; enums stored lower-snake (upper-snake for `ExecutionTreatment`).
- Optimistic concurrency via a `version` column on versioned rows. `concurrency.py` implements
  `guarded_update`, `require_guarded_update` (raising `ConcurrencyConflictError`) and `claim_once`.
  `idempotency_record` is the one documented exemption.
- Read Committed only; `engine.py` contains no Serializable path.
- `_TenantScoped` repositories always filter by tenant; `TenantRegistry` is the only unscoped one.
- `erasure.py` performs hard deletes per tenant and returns per-table row counts; there is no
  soft-delete flag.
- `retention.py` computes windows per class: chat content from the **terminal** state (90 days by
  default), audit from `occurred_at`, checkpoints from work completion. Tenant overrides are read
  from `tenant_mapping.retention_overrides`.

### 8.3 Published read contract — thirteen views

Eleven views form the monolith's contract (`persistence/views.py::ALL_VIEWS`, created by `0018`):
`vw_session_summary_v1`, `vw_session_message_v1`, `vw_session_step_v1`, `vw_work_item_v1`,
`vw_approval_queue_v1`, `vw_approval_unexecuted_v1`, `vw_audit_event_v1`,
`vw_governance_catalogue_v1`, `vw_tenant_v1`, `vw_message_feedback_v1`, `vw_dashboard_rollup_v1`.

Two further views form the Integrations Service's disjoint contract
(`INTEGRATION_READ_VIEWS`, created by `0021`): `vw_tenant_entitlement_v1` (tenant, catalogue id,
`enabled` — no credential column) and `vw_connector_credential_ref_v1` (the Key Vault secret **name**,
filtered `WHERE enabled IS TRUE`). The monolith is **not** granted the second.

The .NET side maps every entity with `ToView`, and `SynthiaReadContext.SaveChanges` /
`SaveChangesAsync` throw unconditionally
(`dotnet/src/Synthia.Persistence/SynthiaReadContext.cs:110,117`). The governance catalogue view
carries no tenant filter, because it is platform-wide.

### 8.4 Repositories with no production writer

`SessionRepository` and `OperationRepository` (`ragcore/src/ragcore/persistence/repositories.py:255`
and `:752`) are fully implemented and **never constructed anywhere in production composition** —
`config/composition.py` binds neither. They are exercised only by
`ragcore/tests/isolation/test_tenant_isolation.py` and `tests/architecture/test_boundaries.py`.
Classification: **implemented but unbound / test-only**.

Combined with §2.2, this means **no production code path writes a `chat_session`, `message` or
`session_step` row**. The .NET read endpoints and the published views are implemented against tables
that, in the current composition, only a migration or a test populates.

---

## 9. Background processing

### 9.1 Transactional outbox — Implemented (as functions)

`messaging/outbox.py::enqueue_trigger` writes the state change and the message in one transaction.
`workers/outbox_dispatch.py::dispatch_once` publishes each row independently, tolerates duplicates by
design (send-then-mark), and never lets a blocked row block another.

Message bodies are exactly three fields — `{workItemId, correlationId, kind}` for triggers and
`{jobId, correlationId, kind}` for integration commands — implemented in `messaging/publisher.py`
and asserted by `tests/messaging/test_trigger_payload.py`.

Service Bus access is managed-identity only: `messaging/credentials.py` refuses connection strings,
shared access keys and SAS tokens.

### 9.2 Consumers — Implemented (as functions)

- `workers/resume_worker.py` implements `parse_message` (raising `UndeserializableTriggerError`) and
  `refuse_unhandled_kind` producing a `DeadLetterReport`, and treats `kind` as a routing hint only —
  authority is re-read from the durable work item.
- `workers/integration_result_worker.py` implements `parse_result_message` and `concluded_from`,
  which reads the outcome from RagCore's own `integration_job` result columns, never from the
  message. A failure result does not cause a re-dispatch.
- `integrations/workers/command_consumer.py` implements `handle_command` and a three-way settlement
  map (complete / dead-letter / abandon). Dead-lettered messages are never auto-replayed
  (`messaging/deadletter.py`, with a severity per trigger kind).
- `messaging/retry.py` implements a backoff policy and `refuse_post_claim_retry`, which raises
  `PostClaimRetryError`. There is no post-claim retry path.

### 9.3 Sweepers — Implemented (as functions)

`workers/expiry_sweep.py::sweep_expired`; `workers/retention_sweep.py::sweep_tenant` (chat content,
audit-window-following records, and checkpoint threads derived with the **same**
`checkpoint_thread_id` function the run host uses); `workers/ingestion_run.py::open_run`/`close_run`.

### 9.4 Worker processes — Not implemented

Every worker's `main()` raises `NotImplementedError` with an explicit message, verified across all
seven: `expiry_sweep`, `ingestion_run`, `integration_result_worker`, `outbox_dispatch`,
`resume_worker`, `retention_sweep`, and `integrations/workers/command_consumer`.

**The behavior functions are implemented and tested; no worker process can currently be started.**
Nothing schedules a sweep, drains the outbox, or resumes a suspended run in a deployed system.

Ingestion acquisition, chunking and embedding are **not implemented at all**; only the run record is.

---

## 10. Execution leg and idempotency

Two distinct idempotency boundaries are implemented:

1. **Atomic claim** — `execution/claim.py::claim_for_execution`, a conditional update on
   `claimed_at IS NULL`. Two racing consumers produce exactly one winner.
2. **Effect record** — `execution/idempotency.py` with `derive_key`, `begin_effect` returning a
   `ReplayDecision`, and `complete_effect`, protecting the external system.

`execution/executor.py::ExecutionLeg` keeps attempt and verification as two separate records and
raises `UnauthorizedExecutionError` without a proceed disposition.
`execution/availability.py` distinguishes *not entitled* from *entitled but unreachable*.

`ExecutionLeg` is exercised by `tests/e2e/test_auto_golden_path.py` and is **not bound into the
container or the graph** — the graph calls `ToolExecutionPort`, which is `None` in composition.
Classification: **implemented but unbound / test-only**.

---

## 11. External integration behavior

### 11.1 RagCore holds no connector — Implemented as a boundary

`build_container()` binds `case_system = directory = execution = discovery = None`, with the code
stating these must not gain an in-process implementation.
`tests/architecture/test_no_connector_in_ragcore.py` and `build/scripts/check-boundaries.sh` fail the
build if connector code reappears in that tree.

RagCore reaches external systems only through:

- `platform_clients/integrations.py::IntegrationsClient` (synchronous, over APIM) — bound when
  `integrations.is_configured`;
- `persistence/integration_jobs.py::IntegrationDispatcher` (asynchronous) — writes an
  `integration_job` row and publishes `{jobId, correlationId, kind}`.

### 11.2 Model egress — Implemented

Every model call goes through `ModelEgressPort`. `_model_egress()` is the only place the choice is
made: `AiGatewayEgress` when a gateway is configured, otherwise `LocalDevelopmentEgress`, which calls
no model, produces a deterministic vector, and refuses to construct outside local development. No
provider SDK call exists anywhere; `tests/architecture/test_no_direct_model_call.py` asserts it.

`model/safety.py::SafeModel` implements bidirectional content-safety checking with
`ContentBlockedError`, but **no `ContentSafetyPort` implementation exists and `SafeModel` is
referenced nowhere outside its own module and tests** — the container binds a bare
`GatewayModelAdapter`. Classification: **implemented but unbound**.

Note that no graph node calls the model at all (§6.8), so the model binding is unused by the graph
regardless.

### 11.3 Retrieval — Implemented, conditionally bound

`AzureAiSearchRetrieval` is bound only when configured; otherwise `retrieval` stays `None`, and the
graph then cannot be composed (§6.9). `retrieval/confidence.py` owns the absolute-score and margin
thresholds as module constants.

`retrieval/hybrid.py` (dense + sparse fusion) and `retrieval/rerank.py` (cross-encoder reranking) are
implemented and unit-tested, but **neither is bound**: no `SparseRetrievalPort` or `RerankerPort`
implementation exists in the tree — only the Protocol definitions. Classification: **implemented but
unbound**.

### 11.4 Integrations Service connectors

- `ServiceNowAdapter` (`connectors/servicenow/adapter.py`) and `MicrosoftGraphAdapter`
  (`connectors/graph/adapter.py`) are implemented. `McpClient` (`mcp/client.py`) is implemented and
  enforces that an advertised tool is not callable until registered and entitled.
- `connectors/duo/` and `connectors/onelogin/` are **name-only modules**: each exports a `SYSTEM`
  string and a `CATALOGUE_PREFIX` and contains no client, credential arrangement or governance hook.
- Composition binds **only** ServiceNow, and only when a secret resolver is passed:
  `build_container(secrets=None)` leaves `servicenow = None`. `api/app.py:65` calls
  `build_container()` with **no argument**, so in a normally started process `container.servicenow`
  is `None` and `POST /case-operations` returns **503**. Classification: **implemented but unbound**.
- The `Container` dataclass has **no field** for the Graph adapter or the MCP client, so neither can
  be bound at all in the current composition.
- `credentials/resolver.py` resolves per-tenant credentials from Key Vault; `policy/checks.py`
  implements the access-policy re-check at execution time. Both are implemented and reachable
  whenever a connector is bound.

---

## 12. Realtime behavior

- **RagCore — partially implemented.** `POST /realtime/negotiate` is implemented and returns an
  endpoint and a group derived solely from the principal (`user:{principalId}`).
  `notifications/signalr.py::SignalRNotifier` and `payload_for` are implemented, but `notifications`
  is `None` in the container and `SignalRNotifier` has **no reference anywhere outside its own
  module** — no notification is ever published. Classification: **implemented but unbound**.
- **Web — not implemented.** `RealtimeService` depends on an optional `REALTIME_CONNECTION` port. No
  adapter is registered in any of the three `app.config.ts` files, so `messages$` is `EMPTY` and
  `connect()` is a no-op. On reconnect the service raises `resyncRequired`, and surfaces re-read from
  the API rather than replaying missed messages.
- **SSE is the implemented realtime path for chat** (`text/event-stream`), subject to §6.9 and §6.10.

---

## 13. Web implementation

Angular 20 workspace: four libraries (`design-system`, `platform-core`, `customer-features`,
`staff-features`) and three applications (`customer-portal`, `staff-portal`, `desktop-renderer`).

**Implemented:**

- Typed API clients (`CustomerApiClient`, `StaffApiClient`, `PlatformApiClient`,
  `MessageStreamClient`), a correlation interceptor, problem-details typing and keyset paging types.
- `ChatShell` (`customer-features/src/lib/chat/chat-shell.ts`, 190 lines) — consumes the SSE stream
  via `MessageStreamClient.send(...).subscribe(...)`, renders progressive text and the step trail,
  tracks `pendingInterrupt` as a **kind only**, distinguishes failure from "nothing to say", and
  announces deltas accessibly via `LiveAnnouncer.announceDelta`. Unsubscribing aborts the request and
  changes no server state.
- Customer routes: `sessions` (`SessionShell`), `sessions/:sessionId` (`ChatShell`),
  `sessions/:sessionId/consent` (`ConsentShell`), `sessions/:sessionId/support` (`HandoffShell`).
- `desktop-renderer` reuses `CUSTOMER_FEATURE_ROUTES` verbatim rather than declaring a parallel table.
- Route guards `canMatchForPresentation([...])` gate staff routes by role **for presentation only**;
  `role-visibility.ts` is explicitly presentation-level, and `no-authz.spec.ts` asserts the client
  makes no authorization decision and holds no secret.
- `FORBIDDEN_STAFF_ROUTE_SEGMENTS` enumerates session-origination segments that must not exist on the
  staff surface; the staff routes contain none.
- Security: `content-security-policy.ts`, `sanitization-policy.ts`, and a CSP hosting harness
  (`scripts/csp-host.mjs` + `playwright.csp.config.ts`).
- Configuration is read from the hosting page (`readHostedConfig`) for the two portals, not compiled
  in.

**Placeholder UI — wired but inert.** The three staff shells are structural only. `QueueShell`
injects `StaffApiClient` and `RealtimeService`, declares `queue = signal(idle())`, and **never calls
either** — the component body is four lines of field declarations. `TakeOverShell` and
`ReportingShell` follow the same pattern. No staff surface loads data.

**Not implemented.** `AuthService` registers **no** `ACCESS_TOKEN_PROVIDER` — the token is injected
`{optional: true}` and no application provides one — so `accessToken()` returns `EMPTY` and `status`
stays `unknown` unless a surface calls `setSession`, and nothing does. There is no MSAL or
identity-library dependency in the tree.

---

## 14. Desktop implementation

Electron host (`apps/desktop`), 12 tracked files under `src/` plus 4 test files.

**Implemented and tested:**

- A custom standard, secure renderer protocol (`renderer-protocol.ts`); the window runs in its own
  session partition (`session-boundary.ts`).
- A closed IPC contract of exactly four informational channels — `host:getVersion`,
  `host:getPlatform`, `host:getEndpoints`, `host:describeSessionBoundary` — each with an argument
  validator, failing closed on an unknown channel (`ipc-contracts/index.ts`, `ipc-guard.ts`).
- `BRIDGE_SURFACE` exposes exactly those four members under a single global key `synthiaDesktop`
  (`preload/bridge.ts`).
- CSP construction and application (`csp.ts`), navigation restriction (`navigation.ts`), permission
  decisions (`decidePermission`), certificate-error handling (`shouldTrustCertificateError`), and a
  forbidden-switch check (`assertNoForbiddenSwitches`, including `no-sandbox`).
- Host configuration parses and validates origins from the environment and defaults to reaching
  nothing (`config.ts`).

**Build-only:** `dist:win` and `pack:dir` scripts drive `electron-builder` with an NSIS target and
`asar: true`. No packaged artifact is tracked in the repository.

**Not implemented, and asserted as such:** `endpoint-execution-boundary.ts` exports
`IS_IMPLEMENTED = false`; `executeApprovedScript` and `verifyScriptBindings` both throw
`EndpointExecutionNotImplementedError` unconditionally. **No script execution exists on the
endpoint.**

---

## 15. Error and failure behavior

- RFC 9457 problem details on every surface at `application/problem+json`, always carrying a
  correlation identifier.
- Status codes, as implemented: **401** for an unusable identity context; **403** for an unregistered
  organisation or a role-set miss; **404** for another party's resource; **400/422** for validation;
  **501** for the thirteen wired-but-inert routes; **502** for an external system's failure
  (Integrations only); **503** for readiness failure or an unbound connector.
- SSE failures after headers are sent produce an `error` event with no detail, and the exception is
  re-raised.
- `asyncio.CancelledError` is never swallowed; `application/cancellation.py::shielded_cleanup`
  implements bounded cleanup around it, covered by `tests/unit/test_cancellation.py`.
- Platform defects are raised rather than absorbed: `UnauthorizedExecutionError`,
  `StateChannelSealedError`, `TreatmentWidenedError`, `PolicyWidenedTreatmentError`,
  `ConcurrencyConflictError`, `PostClaimRetryError`, `ReferenceFixtureInProductionError`.
- Configuration failures stop the process at startup rather than surfacing per request — both Python
  services, and the .NET `RequiredSecretsValidator`.

---

## 16. Testing evidence

### 16.1 Suites executed during this audit

| Suite | Command | Result |
|---|---|---|
| RagCore (non-integration) | `uv run pytest -q -m "not integration"` | **1142 passed**, 159 deselected |
| Integrations | `uv run pytest -q` | **155 passed** |
| .NET | `dotnet test Synthia.sln` | **246 passed** across 11 assemblies |
| Desktop | `npx vitest run` | **178 passed** in 4 files |
| Web unit (all 7 projects) | `npm run test:unit` | **130 passed** — design-system 48, platform-core 28, customer-features 16, staff-features 4, customer-portal 5, staff-portal 8, desktop-renderer 21 |
| Web architecture | `npm run test:architecture` | **9 passed** |
| Governance hooks | `python .claude/hooks/test_guards.py` | **188/188 checks passed** |

Not executed in this pass: the 159 RagCore `integration` tests (require Docker/Testcontainers), the
Playwright a11y and CSP suites (require a Chromium install), and `smoke-images.sh`.

### 16.2 Test suites that exist

- **RagCore unit** — `ragcore/tests/unit/` (18 test files: graph state, graph interrupts, checkpoint
  thread keys, roles, verdicts, session state, treatment policy, confidence, hybrid, rerank, content
  safety, claim, cache, cancellation, correlation policy, settings, integrations client, scaffold).
- **Architecture / boundary** — `ragcore/tests/architecture/` (5 files: boundaries, layering, no
  connector in RagCore, no direct model call, no .NET dependency);
  `integrations/tests/architecture/test_layering.py`; `Synthia.ArchitectureTests` (88 tests: module
  isolation, composition root, banned APIs, data-access discipline, identity discipline, no write
  endpoint, no migrations, no RagCore dependency, APIM routing, Azure identity, edge trust).
- **Contract / API** — `ragcore/tests/contracts/` (2 files); `Synthia.ContractTests` (51 tests:
  OpenAPI emission, API conventions, cursor contract, configuration validation, secret binding,
  tenant isolation).
- **Database / migrations** — `ragcore/tests/migrations/` (2 files: single head, upgrade/downgrade,
  schema isolation), `tests/integration/` (4 files), `tests/concurrency/test_optimistic.py`.
- **Tenant isolation** — `ragcore/tests/isolation/` (3 files including cross-tenant retrieval);
  `Synthia.TenantIsolationTests` (11 tests).
- **Security** — `ragcore/tests/security/` (7 files: Azure identity, edge topology, edge trust policy,
  hard failures, integration grants, no leakage, secret binding); `integrations/tests/security/`
  (4 files); `apps/desktop/tests/security.spec.ts`;
  `apps/web/projects/platform-core/no-authz.spec.ts`; Gitleaks, `npm audit` and
  `dotnet list package --vulnerable` in CI.
- **Governance / authorization** — `ragcore/tests/governance/` (7 files: authority boundary, auto
  path, not-allowed path, no elevation, unexercised gate refuses, feedback has no influence, fixtures
  excluded); `tests/authorization/test_role_change_midflight.py`; `Synthia.AuthorizationTests`
  (21 tests).
- **LangGraph / workflow** — `tests/unit/test_graph_state.py`, `tests/unit/test_graph_interrupts.py`,
  `tests/unit/test_checkpoint_thread.py`, `tests/checkpoint/test_durable_checkpointer.py`.
- **Messaging / idempotency / egress / retention** — `tests/messaging/` (3 files),
  `tests/idempotency/test_duplicate_trigger.py`, `tests/integration/test_outbox_crash.py`,
  `tests/egress/` (2 files), `tests/retention/` (1 file).
- **E2E** — `ragcore/tests/e2e/test_auto_golden_path.py`, which drives intake → retrieval → grounding
  → guardrail → proposal → classification → gate → execution → verification → audit against an
  `InMemorySaver`, and asserts the refusal path in the same file. This is the sole executable proof
  that the graph runs end to end, and it runs against a test-supplied composition.
- **Frontend** — Karma unit specs across all 7 Angular projects; Playwright accessibility sweep
  (`e2e/a11y-scaffold.spec.ts`) and CSP hosting sweep (`e2e/csp-hosting.spec.ts`).
- **Electron** — `bridge-surface.spec.ts`, `no-policy.spec.ts`, `renderer-contract.spec.ts`,
  `security.spec.ts`.

### 16.3 CI gates that exist

Twelve GitHub Actions workflows: `ragcore`, `integrations`, `dotnet`, `web`, `desktop`, `contracts`,
`boundaries`, `edge`, `migrations`, `images`, `security`, `base-image-digests`.

Implemented gates include ruff lint and format, `mypy --strict` and pytest; `dotnet build -warnaserror`,
`dotnet format --verify-no-changes` and `dotnet test`; eslint, prettier, `tsc -b`, the Angular build,
Karma, and the Playwright a11y and CSP suites; Electron typecheck, lint, vitest and build.

The contracts workflow emits OpenAPI from all three services, **emits again and requires
byte-identical output**, validates the documents, compares them against the committed
`build/contracts/**/*.openapi.json`, and fails if the committed contracts are stale.

**The guards are themselves tested.** `build/scripts/verify-architecture-guards.sh`,
`verify-boundary-guard.sh`, `verify-contract-guards.sh`, `verify-desktop-security-guard.sh` and
`verify-edge-guard.sh` each plant a violation and assert that the guard fails.

`images.yml` builds, starts and inspects every container image via `smoke-images.sh`.

### 16.4 Coverage gaps that exist in the test suites

- **The six `dotnet/tests/Synthia.Modules.*.Tests` projects each contain a single `PlaceholderTests`
  test** (Approvals, Audit, Governance, Sessions, Tenancy, Work — 1 test each). Module-level behavior
  is unverified at that layer; the real coverage sits in the architecture, contract, authorization
  and isolation suites.
- **`RunHost` has no test.** `graph/host.py` and `api/customer/sessions.py` both reference
  `tests/unit/test_run_host.py`, and **no such file exists**. No test in the repository references
  `RunHost` or `STEP_LABELS`. The stream orchestration, the step-label mapping, the claimed agreement
  between `TurnEventKind` and `StreamEventKind`, and the terminal-event guarantee are all
  **unverified**.
- Two further referenced test files do not exist: `tests/e2e/test_sample_flows_are_inert.py` and
  `tests/integrations/test_no_provider_leak.py`.

---

## 17. Summary — intentionally inert, unbound or unimplemented

Each row is demonstrated by code, not by prose.

| Area | Classification | Evidence |
|---|---|---|
| Consent recording | Wired but inert | `POST /work/{id}/consent` → 501 |
| Staff verdict recording | Wired but inert | `POST /approvals/{id}/verdict` → 501 |
| Session take-over, staff messages, work cancel | Wired but inert | 501 |
| Workload claim / outcome | Wired but inert | 501 |
| Clarification answer and resume | Wired but inert | `POST /sessions/{id}/answers` → 501 |
| Execution instruction and result | Wired but inert | 501 |
| Sample flows (3 routes) | Wired but inert | 501 |
| Every background worker process | Not implemented | `main()` raises `NotImplementedError` (7 workers) |
| Model reasoning in the graph | Wired but inert | `converse` and `propose` make no model call; no node calls `ModelPort` |
| Verification | Wired but inert | `verify` returns `{}`; only outcome is `client_attested` |
| Endpoint script execution | Not implemented | `IS_IMPLEMENTED = false`; both functions always throw |
| Tool execution adapter | Implemented but unbound | `execution=None` ⇒ no run host ⇒ empty SSE stream |
| The compiled graph on the customer path | Test-only | see §6.9 |
| `ExecutionLeg` | Implemented but unbound / test-only | not bound to container or graph |
| `SessionRepository`, `OperationRepository` | Implemented but unbound / test-only | never constructed in composition |
| Connectors inside RagCore | Not implemented, by design | `case_system/directory/discovery = None`, guarded by test + build script |
| Notifications | Implemented but unbound | `notifications=None`; `SignalRNotifier` unreferenced |
| Realtime client transport | Not implemented | no `REALTIME_CONNECTION` provider registered |
| Client authentication | Not implemented | no `ACCESS_TOKEN_PROVIDER` registered; no MSAL in the tree |
| Content safety | Implemented but unbound | `SafeModel` implemented, no `ContentSafetyPort` implementation |
| Hybrid retrieval and reranking | Implemented but unbound | no `SparseRetrievalPort`/`RerankerPort` implementation |
| Microsoft Graph connector, MCP client | Implemented but unbound | no `Container` field exists for either |
| Duo, OneLogin connectors | Not implemented | name-only modules (`SYSTEM`, `CATALOGUE_PREFIX`) |
| ServiceNow connector in a deployed process | Implemented but unbound | `build_container()` called without secrets ⇒ 503 |
| Ingestion acquisition, chunking, embedding | Not implemented | only the run record exists |
| Staff portal behavior | Wired but inert | shells inject clients, hold idle signals, never load |
| Gateway-provenance verification in the backend | Not implemented | no such middleware stage in either stack |
| Real ITSM catalogue operations | Not implemented | four inert reference fixtures, which **raise** in production |
| Durable session/work creation on `POST /sessions` | Wired but inert | handler returns a generated UUID and writes nothing |
| `token` SSE event kind | Wired but inert | declared in `StreamEventKind`, no producer anywhere |
| Integrations catalogue paging | Wired but inert | `next_cursor` hard-coded to `None` |

---

## 18. Areas where implementation evidence is insufficient

Used sparingly, and only where the repository contains no executable evidence.

- **`RunHost` behavior** (§16.4). The code exists; no test exercises it, and the file its own
  docstrings cite does not exist. Its runtime behavior is **unverified**.
- **Integration-marked tests.** 159 RagCore tests require Testcontainers/Docker and were not executed
  here, so migration upgrade/downgrade, published-view shape and persistence behavior are asserted by
  test code but were not observed running in this pass.
- **Deployed configuration.** `build/infra/**` and `build/docker/**` are executable configuration for
  APIM, Front Door, messaging, identity and monitoring. No deployed environment was available, so the
  runtime behavior they produce is unverified.
- **Container image behavior.** `smoke-images.sh` exercises image start-up in CI; not run here.
- **Playwright suites.** Neither the a11y nor the CSP sweep was executed in this pass.
- **Absence of a production `execution` binding.** The conclusion in §6.9 follows from the absence of
  any adapter in this tree. It is evidence of absence within this repository only.

---

## 19. Corrections to the previous generated snapshot

The Phase 3 snapshot of this document (derived from `5cdcd26`) contained the following statements
that the current implementation disproves. No source, test, configuration or rule was changed to
resolve them; the document was corrected.

1. **"`reference_fixtures("production")` returns an empty catalogue."** It **raises
   `ReferenceFixtureInProductionError`** (`ragcore/src/ragcore/governance/fixtures.py:195`).
2. **"Eleven published views"** and **"`tenant_entitlement` is deliberately not published."** There
   are **thirteen** views. Revision `0021` creates `vw_tenant_entitlement_v1` and
   `vw_connector_credential_ref_v1` and grants them to the Integrations principal; the monolith is
   granted neither (§8.3).
3. **"A packaged Windows installer exists in `apps/desktop/release/`" / "a built artifact is
   committed under `release/`."** `apps/desktop/release/` is **not tracked by git**. Only the
   packaging configuration is committed.
4. **"`ragcore/tests/unit/*` (23 files)."** There are **18** test files in that directory.
5. **"`_route_after_propose`" described as routing from `propose`.** It is registered on the
   **`classify`** node (`graph/builder.py`).
6. **"SSE event kinds `token`, `step`, `interrupt`, `done`, `error`" presented as the implemented
   stream.** `token` is declared in `StreamEventKind` and has **no producer**; `TurnEventKind` omits
   it entirely (§6.10).
7. **The reducer names** for `execution` and `verification` are `seal_execution` and
   `seal_verification`, not a shared `_seal`.
8. **Only one Angular project's unit suite was run.** All seven were run in this audit: 130 tests.

---

## 20. Implementation findings

Observations about the implementation as it stands. These are implementation facts, not judgments
about whether the implementation or any other document is correct.

1. **The compiled graph is unreachable in normal composition.** `build_container()` binds
   `execution=None` unconditionally, so `app.state.run_host` is always `None` and the streaming
   endpoint always returns the empty stream. The entire graph — fourteen nodes, three interrupts, the
   gate, the execution leg — is exercised only by tests.
2. **`POST /sessions/{id}/answers` returns 501 while the run host exists.** The route's docstring
   says it is 501 "until the run loop is hosted", but `RunHost` and `durable_graph` are implemented
   and wired into the lifespan. The blocking fact is that `graph_dependencies()` returns `None`, not
   that the host is missing.
3. **Two clarification-interrupt implementations exist.** `graph/nodes/conversation.py::make_clarify`
   is the registered node; `graph/nodes/clarification_interrupt.py` is a second, unregistered
   implementation from which only a constant is imported.
4. **The Integrations Service cannot perform a case operation as deployed.** `api/app.py` calls
   `build_container()` without a secret resolver, so `servicenow` is always `None` and the endpoint
   returns 503.
5. **Approval and consent reads have no corresponding writes.** `ApprovalRepository` and
   `ConsentRepository` decision reads are implemented and consumed by the graph, but every route that
   would record a decision returns 501.
6. **`HumanDecisionRecord.expires_at` is always `None`** in both `_mirror_consent` and
   `_mirror_verdict`, although the field exists and the gate resolves an expiry separately from the
   durable record.
7. **`GraphDependencies.model`, `work_items` and `audit` are bound but unused by any node** in the
   current node implementations.
8. **No production code path writes `chat_session`, `message` or `session_step` rows** (§8.4). The
   .NET read endpoints and eleven of the thirteen published views read tables that only a migration or
   a test populates.
9. **`SessionRepository` and `OperationRepository` have no production constructor.**
10. **`RunHost` has no test, and three referenced test files do not exist** (§16.4).
11. **Six .NET module test projects contain only placeholder tests.**
12. **`CatalogueResponse.nextCursor` is hard-coded to `null`**, so the paging field is part of the
    wire contract while paging is not implemented.
13. **Backend gateway-provenance verification is absent in both stacks**, stated in code comments as
    deferred; what remains is network placement plus edge header deletion.
14. **The `Container` dataclass in the Integrations Service has no field for the Graph adapter or the
    MCP client**, so those implementations cannot be bound without a composition change.

---

## 21. Implementation-versus-architecture conformance findings

Recorded neutrally and **not resolved here**. Determining which side should change is out of scope
for this document; see `.claude/rules/90-functional-knowledge.md` §90.7.

1. **Graph state vocabulary.** The current implementation carries `tenant_id`, `session_id`,
   `correlation_id`, `work_item_id`, `governance.treatment`, `decision`, `execution` and
   `verification`. The architecture source of truth specifies `tid`, `user_id`, `request_id`,
   `case_ref`, `execution_treatment`, `approval`, `consent` and `action_result`. This is a deferred
   conformance finding.
2. **Node names.** The current implementation registers `govern`, `await_approval`, `execute`,
   `verify` and `close`. The architecture source of truth specifies `record_policy_decision`,
   `human_approval`, `execute_action`, `verify` and `respond`. This is a deferred conformance finding.
3. **Customer message path behavior.** The current implementation returns an empty SSE stream for
   every customer message in normal composition (§6.9). The architecture source of truth specifies a
   running agent turn. This is a deferred conformance finding.
4. **Data-access split.** The current implementation uses EF Core on the .NET side for data access
   while Alembic owns all schema. The split is enforced by `NoMigrationTests`, and no mechanical check
   ties the EF model to the Alembic-owned schema. This is a deferred conformance finding.

No architecture document, ADR, application source file, test, migration or configuration file was
changed while producing this document.
