# Phase 0 Research: Synthia Platform Engineering Scaffold

**Date**: 2026-09-15 | **Plan**: [plan.md](./plan.md)

Every decision below is traceable to the constitution, an ADR, or the platform specification. Where a
fact was verified against vendor documentation during research, that is stated. Where a detail must be
confirmed at implementation time, it says so rather than asserting.

---

## R-001 — How does RagCore stream a chat response, given SignalR may not authorize?

**Decision**: Chat responses stream over **HTTP server-sent events on the authenticated Customer API**,
not over SignalR.

**Rationale**: Constitution Principle III makes SignalR "a leaf on every consequential path, never a
link", and spec FR-IDENT-005 forbids the realtime channel from authorizing anything. If the response stream
ran over SignalR, the conversation itself would depend on the channel and the separation would erode
in practice even if it held in theory. SSE keeps the stream on the same authenticated request that
carried the user's message, so the identity that authorized the turn is the identity receiving it.
SSE is also one-directional, which matches the shape of the problem — the client has nothing to send
mid-stream.

**Alternatives considered**: WebSocket on the Customer API (bidirectional, but adds a second
connection lifecycle for no gain — the user's next message is a new authenticated request);
streaming over SignalR (rejected on the principle above).

---

## R-002 — Can RagCore publish SignalR notifications without any .NET component?

**Decision**: Yes. RagCore calls the **Azure SignalR Service data-plane REST API** directly, using a
Microsoft Entra token from managed identity.

**Verified against Microsoft Learn** (Azure SignalR Service data-plane REST API reference): the service
exposes `POST /api/hubs/{hub}/groups/{group}/:send` and `POST /api/hubs/{hub}/users/{user}/:send`,
documented as callable from "any programming language that can make REST API calls". Entra
authentication is supported with credential scope `https://signalr.azure.com/.default` plus RBAC, so
no access key is needed — which also satisfies the constitution's zero-standing-secrets commitment.
The same API exposes `POST /api/hubs/{hub}/:generateToken`, so RagCore can also issue the client
connection token.

**Rationale**: This is what makes ADR-0001's no-dependency rule survivable. Had SignalR publishing
required a .NET server hub, the monolith would have been dragged onto the notification path and
become a dependency of RagCore.

**Consequence**: the SignalR *negotiate* endpoint lives in RagCore, not the monolith. Group membership
is derived from the trusted identity context at negotiation time; a client never asks to join a group
by identifier.

**Alternatives considered**: a .NET SignalR hub server (rejected — creates the forbidden dependency);
Web PubSub (rejected — the platform specification names SignalR, and changing it requires an
amendment).

---

## R-003 — How do the two deployables share PostgreSQL without coupling?

**Decision**: RagCore owns every table and every migration. The monolith reads **only** through
explicitly versioned views (`vw_<name>_v1`), which are created and owned by RagCore's Alembic history
using `alembic_utils` so views are first-class autogeneratable entities rather than raw `op.execute`
strings.

**Rationale**: ADR-0001 identified the schema as the real coupling point — no architecture test
catches a breach of it. Versioned views turn a breaking change into an additive one: `_v2` is added
alongside `_v1`, the monolith migrates on its own schedule, `_v1` is dropped a release later once
unreferenced. The version number carries the coordination, so no sign-off gate is needed.

**Consequence**: the monolith's EF Core contexts map to views, not tables, and are configured
`HasNoKey()` or with an explicit key per view. `AsNoTracking` is the default for every query.

---

## R-004 — Where do the LangGraph checkpoint tables live?

**Decision**: In their own PostgreSQL schema (`langgraph`), owned entirely by the checkpointer's own
`setup()` routine. Alembic **excludes** that schema from autogenerate via `include_schemas` /
`include_object`, and a test asserts autogenerate never proposes a change inside it.

**Rationale**: `langgraph-checkpoint-postgres` creates and versions its own tables. Two migration
systems in one database are safe only while their schemas are disjoint; without the exclusion,
autogenerate would propose dropping the checkpoint tables it did not create.

**Consequence**: no foreign key crosses the boundary. The work item is the authority record and the
checkpoint is working state (platform specification §15.6), joined by identifier in application code.

---

## R-005 — Migration tooling and rollback

**Decision**: Alembic on its async template (`alembic init -t async`, `async_engine_from_config` over
asyncpg). Migrations run as a dedicated pipeline job before the new revision activates — never at
application startup. Database principals are separated: migration job holds DDL, RagCore runtime holds
DML+SELECT, the monolith runtime holds SELECT on its views only.

Rollback is layered: every revision implements `downgrade()` (proven by `pytest-alembic`'s
`test_up_down_consistency`); production safety comes from **expand/contract** so an application
rollback never needs a schema change; point-in-time restore is the last resort for data-destructive
cases.

**Rationale**: Full reasoning in [ADR-0003](../../docs/adr/0003-database-migrations-and-rollback.md).
Startup migration fails three independent ways under Container Apps: replicas race, scale-to-zero
makes timing unpredictable, and the app would hold DDL rights for its whole life.

**CI gates** (verified against pytest-alembic documentation): `test_single_head_revision`,
`test_upgrade`, `test_model_definitions_match_ddl`, `test_up_down_consistency`.

---

## R-006 — How is the .NET-to-RagCore prohibition actually enforced?

**Decision**: Four independent mechanisms, because any one of them can be worked around.

1. **Structural** — separate top-level trees with no shared solution or workspace, so a reference
   cannot be added without a visibly odd cross-tree path in the diff.
2. **Architecture tests** — `Synthia.ArchitectureTests` asserts no assembly reference, no type, and no
   configured `HttpClient` base address resolving to the RagCore service. RagCore's
   `tests/architecture` asserts the mirror image.
3. **CI boundary check** — `build/scripts/check-boundaries` greps for the forbidden imports, package
   references and service names, and fails the pipeline.
4. **Review** — the constitution names it explicitly as a rejection criterion.

**Rationale**: Principle V calls this out as the rule most likely to erode under delivery pressure,
because the tempting shortcut ("just call RagCore for this one field") is always locally reasonable.

---

## R-007 — How are the two backends addressed through one gateway?

**Decision**: Route by path prefix at APIM, with the audience and version in the URI segment:

| Path prefix | Deployable | Purpose |
|---|---|---|
| `/api/customer/v1/...` | RagCore | Conversation, streaming, consent, instruction fetch, result post, feedback, negotiate |
| `/api/customer/v1/views/...` | .NET | Customer read models — my sessions, history |
| `/api/staff/v1/...` | RagCore | Approval verdict, take-over, cancellation |
| `/api/staff/v1/views/...` | .NET | Live sessions, approval queue, step trail, dashboards |
| `/api/workload/v1/...` | RagCore | Execution-leg operations |

**Rationale**: URI-segment versioning is required by the constitution's .NET standards. The `views`
segment makes the read/write split explicit in the URL and gives APIM a deterministic, unambiguous
routing rule with no content inspection. A client calling both deployables is expected and correct —
they are two backends behind one trust boundary, not two products.

**Consequence**: because PostgreSQL is the single store, a write through RagCore is immediately visible
to a read through the monolith. There is no eventual-consistency window to design around.

---

## R-008 — How do OneLogin, Duo and further third parties attach?

**Decision**: As **MCP servers** behind ports declared in `application/`, with adapters in
`integrations/`. Every capability is registered in the governance catalogue with an execution treatment
and entitled per organisation before it is callable.

**Rationale**: Spec FR-EXT-014 makes discovery insufficient for entitlement, and the platform specification
§21.2 already states that "MCP-discovered tools inherit exactly the same governance as native ones".
The port-and-adapter split is what keeps provider vocabulary out of the domain: `domain/` never
imports an SDK, and an adapter translates to platform terms at the boundary.

**Consequence**: adding a fourth or fifth third party is a registration and entitlement change, not an
architecture change (spec FR-EXT-010, SC-EXT-002). Credentials are per organisation and per system, resolved
from Key Vault, and never appear in conversation, step trail, telemetry or audit.

---

## R-009 — Angular workspace shape and desktop reuse

**Decision**: One Angular workspace with three applications and four libraries.
`desktop-renderer` is its own application that composes the same `customer-features` library as
`customer-portal`, adding only a desktop bridge service that talks to the preload surface.

**Rationale**: Making the renderer a separate application keeps desktop-only capability (script
execution) out of the web bundle, while the shared library guarantees the two customer experiences do
not drift. Building the web portal *as* the renderer was rejected because it would ship desktop code
paths to browsers, and because the desktop needs a different composition root.

**Enforcement**: ESLint boundary rules prevent `customer-features` importing from `staff-features` or
from any application, and prevent `design-system` importing business logic.

---

## R-010 — Electron security posture

**Decision**: `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, a narrow typed
`contextBridge` surface, every IPC message validated against a schema in `ipc-contracts/`, and
navigation restricted to an allow-list. Script handling — fetch, hash verification, execution — happens
in the **main process only**; the renderer never receives the script body, the instruction, or the hash.

**Rationale**: ADR-0004 and constitution Principle VII. The endpoint is the platform's only execution
path inside a customer network and is the highest-value target in the architecture.

**Consequence for the scaffold**: with no catalogue entries defined, no script executes. The safeguards
and the security tests exist and are exercised; the capability they guard is dormant.

---

## R-011 — .NET container baseline

**Decision**: Multi-stage build — SDK image to build, **chiseled Ubuntu ASP.NET runtime** for the final
image, running as the non-root `app` user on port 8080, with `InvariantGlobalization=true`.

**Verified against Microsoft Learn**: chiseled images contain no shell and no package manager, include
a non-root user and are configured with it enabled, and **do not support globalization by default** —
ICU and tzdata require the `-extra` variant. SDK images are not produced for chiseled variants, so a
multi-stage build is mandatory.

**Rationale**: The English-only decision (spec FR-SURF-014) is what makes plain chiseled viable rather than
`-extra`; a localized product would need the larger image. Timestamps are handled as
`DateTimeOffset.UtcNow` throughout (rule DN1) and stored in UTC, so tzdata is not required.

**Caveat to verify at implementation**: the exact tag follows the `TFM-OS-type-variant` scheme —
expected `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled`. Confirm the OS codename against MCR
before pinning. **If per-organisation timezone display is ever required, this decision must change to
the `-extra` variant** — it is not a free choice to revisit silently.

---

## R-012 — Python container baseline

**Decision**: Multi-stage build on a slim Python 3.12 base, non-root user, dependencies installed from
a committed lockfile, no build toolchain in the final image.

**Rationale**: Matches the `py312` baseline in `python.yaml` and the platform's zero-standing-secrets
posture (credentials come from managed identity at runtime, never baked in). A lockfile is required by
the rule pack's packaging row.

**Consequence**: two images total, one per deployable. The resume worker runs from the **same image**
as the RagCore API with a different entrypoint — it shares the domain and persistence code, so a
separate image would duplicate it and risk version skew.

---

## R-013 — Idempotency infrastructure

**Decision**: Two distinct boundaries, both required, neither substituting for the other:

- **Platform** — an atomic claim on the work item, so duplicate trigger delivery cannot execute the
  same work twice.
- **External** — an idempotency key carried to the external system, so a retry inside an adapter
  cannot cause a duplicate external effect.

**Rationale**: Platform specification §29.4 requires both explicitly. The claim protects the platform;
the key protects the third party.

**Consequence**: retry policy is narrow by design. Pre-claim transient failures retry with bounded
backoff inside the remaining window; **post-claim execution failures do not retry at all** and require
fresh human authorization (spec FR-EXEC-006, ADR-0002, answering OQ-07).

---

## R-014 — Correlation and observability

**Decision**: A correlation identifier is accepted at the gateway, propagated through both deployables,
carried on every Service Bus trigger and every SignalR envelope, and attached to every log line, span
and audit record. OpenTelemetry in both stacks exporting to Application Insights.

**Rationale**: The two deployables never call each other, so a distributed trace is the only way to
follow one user request across them. Without a shared correlation identifier, a conversation that
suspends and resumes hours later is unreconstructable.

**Constraint**: audit and telemetry remain separate stores with separate retention (spec FR-AUDIT-002, and
platform specification §28.1). Telemetry must never be used to answer an audit question.

---

## R-015 — Error contract

**Decision**: RFC 9457 `application/problem+json` from both deployables, with a shared shape:
`type`, `title`, `status`, `detail`, `instance`, plus `correlationId`. No internal identifier, stack
trace, credential reference or other tenant's data ever appears in an error body.

**Rationale**: The constitution's .NET standards require ProblemDetails; using the same contract in
RagCore means clients have one error model across both backends rather than two.

---

## R-016 — How does the agent reach a model, and where are budgets enforced?

**Decision**: Every model call — reasoning and embeddings alike — goes through the **AI Gateway**. No
component reaches a provider directly. Per-organisation token and request budgets and throttles are
configured **at the AI Gateway and at APIM**, not in application code.

**Rationale**: Platform specification §13.5 makes the AI Gateway a required policy function owning
provider routing, provider-normalised token metering, budgets and throttles, semantic cache, and
bidirectional content safety. §9.3 lists models as "brokered by the AI Gateway". §25.2 places noisy-
neighbour containment "at the AI Gateway and Gateway". Enforcing budgets inside RagCore would leave
them unable to constrain the other deployable or the model egress path, and provider-normalised
metering is only meaningful at the point every call passes through.

The AI Gateway is explicitly **not** an identity boundary (§13.5). A call that reaches a platform
service still traverses APIM and is authorized there and at the service.

**Consequence**: the model adapter lives behind an application port in
`ragcore/src/ragcore/integrations/model/`, and an architecture test asserts no provider SDK import or
provider endpoint exists outside it. Content safety is applied at this boundary — inbound before the
model, outbound before a response returns (§35.5) — which is also layer 2 of the scope guardrail
(§16.3).

**Alternatives considered**: a direct provider client per call site (rejected — no metering point, no
budget enforcement, and provider coupling spread across the codebase); budgets in RagCore application
code (rejected — contradicts §25.2 and cannot constrain the monolith or model egress).

---

## R-017 — How does a state change become a reliable asynchronous message?

**Decision**: A **transactional outbox in PostgreSQL**. The state change and the outbox row commit in
one transaction; a dispatcher worker publishes to Service Bus afterwards and marks the row dispatched.

**Rationale**: Writing state and publishing in two independent operations has no crash-safe ordering —
publish-then-crash loses the state, commit-then-crash loses the message. The outbox makes the message
as durable as the fact that produced it, which is what the approval path needs: a verdict that is
recorded but never triggers resume is a governance failure, not a lost notification.

**Consequence**: publication is at-least-once by construction, so every consumer is idempotent and the
atomic claim absorbs duplicates. The dispatcher is a worker in the RagCore deployable.

**Alternatives considered**: direct publish inside the transaction (rejected — a broker call inside a
database transaction couples their availability and can still fail after commit); change-data capture
(rejected — new infrastructure, and the platform specification names none).

---

## R-018 — Concurrency control

**Decision**: **Optimistic concurrency** with a version column on every mutable row, plus the atomic
claim for execution. Read Committed by default; Serializable only for a named invariant.
**No distributed locking as an architectural primitive.**

**Rationale**: The contended paths are narrow and known — the work-item claim, the approval verdict,
take-over — and each is a single-row conditional update, which PostgreSQL already makes atomic. A
distributed lock would add a failure mode (lock loss, lease expiry, split brain) to solve a problem the
database solves for free, and would put liveness of the fifteen-minute window at the mercy of a lock
service.

**Consequence**: a losing writer sees a conflict and re-reads rather than blocking. First-valid-verdict
and first-take-over both fall out of the same mechanism.

---

## R-019 — Configuration and startup validation

**Decision**: Typed options in both stacks, validated at startup. .NET uses `AddOptions<T>()` with
`BindConfiguration`, `ValidateDataAnnotations()` and `ValidateOnStart()`; Python uses Pydantic Settings.
Application and domain code MUST NOT read raw configuration keys.

**Rationale**: A missing or malformed setting should stop the process at start, not surface as a null
three hours later on a path nobody tested. `ValidateOnStart()` converts a latent configuration defect
into a failed deployment, which is where it is cheapest.

**Consequence**: configuration validation becomes a test category — options bind, validate, and fail
fast — and a container that starts is a container whose configuration is known good.

---

## R-020 — Outbound HTTP and resilience

**Decision**: `IHttpClientFactory` with typed clients and `DelegatingHandler` chains, using standard
`Http.Resilience`/Polly v8 applied consistently. `HttpClient` is never constructed manually. **Every
outbound call carries an explicit timeout**, and resilience distinguishes transient from non-transient
failure.

**Rationale**: Manual `HttpClient` instantiation causes socket exhaustion and stale DNS; per-call
bespoke retry causes inconsistent behaviour and hidden amplification. The timeout rule is specific to
this platform: RagCore calls MCP servers, the system of record, Graph and SignalR inside a
fifteen-minute execution window, and one call without a timeout can hold work past its expiry —
turning a slow dependency into an expired approval.

**Consequence**: retry policy must not be confused with the execution-retry rule. Transport-level retry
of a *read* is fine; a failed side-effecting operation still does not re-fire (ADR-0002).

---

## R-021 — Where does Ingestion live?

**Decision**: `Ingestion` is the twelfth bounded context (§32.12) and is realised as a RagCore package
with its own scheduled worker. It owns the ingestion run record, watermarks and document identity.

**Rationale**: Ingestion embeds and indexes, so it sits with the retrieval and model boundaries rather
than with read models. It is asynchronous, scheduled and idempotent by nature, which matches the worker
shape already established for resume, outbox dispatch and expiry.

**Consequence**: it does **not** become a separate deployable — that would need an ADR under
Principle V. Every ingested record is tenant-stamped, and AI Search remains a derived index that can be
rebuilt by re-running ingestion.

---

## R-022 — Where do integrations live? *(added 2026-09-18)*

**Decision**: In a **separate Python deployable**, the Integrations Service, parallel to RagCore.
Decided at the architecture level by `Synthia-Platform-Specification.md` §21.6 and
[ADR-0007](../../docs/adr/0007-integration-service-boundary.md); recorded here so the plan's reader
finds the reasoning where the other structural decisions sit.

**Rationale**: RagCore processes untrusted model output, retrieved content and chat text by design.
Co-locating every organisation's connector credentials with it makes an orchestrator compromise a
credential breach for every customer system — the accepted risk the platform specification records in
§18.2 and §35.2 as OQ-02. Moving credential resolution and external egress into a separate runtime
discharges the most damaging half of it. §14.1 already described these three contexts as independently
addressable; ADR-0001 collapsed them, and this narrows that divergence rather than adding one.

**Alternatives considered**:

- *Keep integrations inside RagCore.* Rejected — leaves OQ-02's damaging half unaddressed and leaves
  §14.1 and §9.2 describing a structure that does not exist.
- *Split RagCore into user-facing and execution runtimes* (§18.2's own recommendation for OQ-02).
  Rejected as insufficient: it separates the *platform* credential classes but leaves connector
  credentials wherever the adapters live.
- *One service per integration context.* Rejected as the premature distributed decomposition
  Principle V names as a defect — three deployables with no boundary between them that anything
  enforces.

**Consequence**: gateway hops return to the tool path that ADR-0001 removed, so the §34.2 hop-count
baseline moves again and **OQ-06 cannot be closed until it is re-measured**. No performance figure is
an acceptance criterion in the interim. A directed application dependency now exists, RagCore →
Integrations, with results returning over Service Bus rather than as a call — which is what keeps the
graph acyclic.

---

## R-023 — Do the two Python services share a library? *(added 2026-09-18)*

**Decision**: **No.** Separate `pyproject.toml`, separate lockfile, separate virtual environment,
separate CI pipeline. Correlation middleware, the problem-details shape, the settings base and the
telemetry setup are **duplicated**, deliberately.

**Rationale**: constitution Principle VI — DRY applies *within* a module boundary, and unrelated
modules must not be forced into a shared abstraction merely to remove duplication, because duplication
across boundaries is cheaper than a false shared contract. More concretely: a shared package would be
a **build-level dependency between two deployables required to have none**, and it would not appear as
a cross-tree path, so `build/scripts/check-boundaries.sh` could not catch it.

**Alternatives considered**: a `synthia-common` package, rejected above; vendoring by copy with a sync
script, rejected as the same coupling with worse ergonomics and no enforcement.

**Consequence**: the two services' middleware will drift. That is accepted — each is small, each is
tested in its own suite, and a divergence in one service's error contract is caught by its own
publishability gate rather than by a shared type nobody owns.

---

## Outstanding — not resolved here

| Item | Why it is not resolved | Impact if left |
|---|---|---|
| Scale envelope (organisations, concurrent sessions) | No figure exists in any source document; recorded Outstanding in the clarification session | Load-test design has no target. No effect on the scaffold's structure |
| Second approval in one session | Platform specification OQ-01, open upstream | Agent behaviour undefined for a case needing two approvals. Assumed to escalate |
| Script signing for GA | ADR-0004 residual gap | Integrity rests on API trustworthiness until closed. Blocks catalogue expansion beyond non-destructive entries |
| "Destructive" taxonomy | ADR-0004 | The §35.4 shipping gate cannot be lifted |
| Resume/checkpoint reconciliation contract | Platform specification OQ-08 | Behaviour undefined when a trigger arrives at an unexpected checkpoint position |
| Which system-of-record operations are synchronous | ADR-0007 §Unresolved. §22.3 classifies six write classes identically; §22.5 makes only case creation clearly blocking | The Integrations contract cannot be frozen. Case creation is specified; the other five are not guessed |
| The job row's result columns and their column-scoped `GRANT` | ADR-0007 §Unresolved | `FR-INTEG-020` and `FR-DEMO-025` are provable only once the DDL exists — the protection lives at the database permission boundary |
| OQ-06 latency re-baseline | Deferred again by R-022's restored gateway hops | None. No performance figure gates a release |
