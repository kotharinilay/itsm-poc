# Quickstart & Validation Guide

**Date**: 2026-09-15 | **Plan**: [plan.md](./plan.md)

How to run the scaffold and prove it does what the specification claims. Every scenario below maps to a
success criterion and is runnable without any use case being defined.

## Prerequisites

| Need | Why |
|---|---|
| .NET 10 SDK | Monolith build and tests |
| Python 3.12 with `uv` (or equivalent) | RagCore build and tests |
| Node.js LTS | Angular workspace and Electron host |
| Docker | PostgreSQL and Testcontainers-backed integration tests |
| Azure CLI, signed in | Managed-identity token acquisition for SignalR, Service Bus, Key Vault |

Local development uses a containerised PostgreSQL and emulated or developer-tier Azure resources. No
secret is ever placed in a file — every credential resolves from Key Vault through the signed-in
identity.

## First run

The README's §Running it locally is the maintained copy of this, with the configuration table. In
short:

```bash
# 1. Database — migrations run as a job, never at application startup (ADR-0003). The checkpointer
#    provisions its own tables from the same job, in this order.
docker run -d --name synthia-db -e POSTGRES_PASSWORD=local -e POSTGRES_DB=synthia \
  -p 5432:5432 postgres:17-alpine
export SYNTHIA_DB_DSN=postgresql+asyncpg://postgres:local@localhost:5432/synthia
cd ragcore
uv run alembic upgrade head
uv run python scripts/provision_checkpoint_schema.py

# 2. RagCore. A factory, not a module-level app: `create_app` builds the container from validated
#    settings, so a test can construct one without touching the environment.
uv run uvicorn ragcore.api.app:create_app --factory --port 8000

# 3. The read-only monolith
cd ../dotnet
ReadDatabase__ConnectionString="Host=localhost;Port=5432;Database=synthia;Username=postgres;Password=local" \
  dotnet run --project src/Synthia.Api

# 4. The Integrations Service
cd ../integrations
SYNTHIA_INTEGRATIONS_PERSISTENCE__DSN=$SYNTHIA_DB_DSN \
  uv run uvicorn integrations.api.app:create_app --factory --port 8100

# 5. Any client surface
cd ../apps/web
npx ng serve customer-portal      # or staff-portal, or desktop-renderer
cd ../desktop && npm run build:renderer && npm run start   # Electron host
```

**The workers are not among these commands**, and that is not an omission: all seven `main()`
functions raise by design until their container definitions land (T324). Their behaviour is
exercised by the suites, not by a process.

Every application route requires the `X-Idp-*` contract APIM would set — see the README for the
header set and for why a request without it is a 401 rather than an anonymous session.

## Validation scenarios

**Scaffold acceptance vs platform behaviour** *(2026-09-16)*. V2a, V2b and V2c are the scaffold's
acceptance flows and must pass through the deployed edge. **V3, V4 and V7 describe approval, consent
and durable suspension — platform behaviour deferred past the scaffold** (spec `FR-DEMO-016`). They
remain here because the behaviour remains specified; they are not gates on scaffold completion.

Each proves a specific claim. Run them in order — later ones depend on earlier state.

### V1 — A session exists and streams (SC-SESS-001, SC-SESS-002)

Sign in on the customer portal, describe a problem, and watch the response arrive progressively.

**Passes when**: partial output is observable before the response completes, a session is created bound
to your organisation, and a greeting alone creates no work record.

### V2 — An unsupported request falls back honestly (SC-FALL-001, SC-SCOPE-001)

Ask for something requiring an action.

**Passes when**: the request is escalated for human resolution, you are told plainly a human will take
it, context is preserved, and nothing is fabricated. **With no use case defined this is the expected
path for every action-requiring request** — it is the correct result, not a failure.

### V2a — The asynchronous round trip, through the real edge (SC-DEMO-001, SC-DEMO-005, SC-DEMO-008…010)

*Added 2026-09-16. Flow **B1** — see [contracts/sample-flows.md](./contracts/sample-flows.md).*

**Must be driven through Front Door → WAF → APIM.** A run against a deployable directly does not
satisfy `FR-DEMO-019`, however green it looks.

1. `POST /api/customer/v1/sample-flows/round-trip` as a signed-in end user. Note the returned
   correlation identifier.
2. Confirm the state row and its outbox row committed **together** — then repeat with the dispatcher
   stopped and confirm the message is still there after a restart.
3. Confirm the dispatcher published, the workload leg claimed atomically, and the outcome persisted.
4. Re-deliver the same bus message. Expect **exactly one** effect, not two.
5. `GET .../round-trip/{id}` and confirm the client refresh returns the persisted outcome.
6. Repeat the whole flow with **no client connected**. Expect an identical outcome.
7. Search telemetry for the correlation identifier from step 1. Expect one journey spanning both
   deployables and the asynchronous hop.

**Expected**: one effect, one correlation identifier end to end, and no external system touched.

### V2b — The .NET read seam (SC-DEMO-006, SC-DEMO-007)

*Flow **B2**.*

1. `GET /api/staff/v1/sample-flows/records` as staff, through APIM, targeting one organisation.
2. Confirm every row belongs to that organisation and none to another.
3. Attempt the same read against a **base table** with the monolith's database principal.

**Expected**: the view read succeeds; the base-table read is refused by PostgreSQL, not by application
code.

### V2c — The service boundary, and the bypass that must fail (SC-DEMO-003a)

*Flow **B3**. The negative half is the point.*

1. `POST /api/customer/v1/sample-flows/service-hop` through APIM. Confirm the callee reports an
   app-only caller carrying no customer-organisation authority.
2. Send the same request **directly to the container**, bypassing the edge and gateway, carrying
   **no** identity contract.

**Expected**: step 1 succeeds; step 2 fails.

> **Step 3 has been withdrawn, and you should know why before you skip it.**
>
> It used to read: *send it again directly, this time carrying a well-formed, self-supplied gateway
> header contract — the shape a real bypass takes*, and it had to fail. That is `SC-DEMO-003b`,
> which is **deferred** along with the control that made it fail — see
> [ADR-0008](../../docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md).
>
> **If you run it today it will succeed.** That is the documented, accepted consequence of the
> deferral, not a finding to raise: the deployable trusts a header it can no longer verify came
> from APIM. Do not record it as a passed check, and do not "fix" it by adding a shared secret or a
> trusted header — ADR-0008 must be superseded first.

### V3 — Staff approval survives the client (SC-EXEC-001)

Drive a session to the `STAFF_APPROVAL` reference operation. **Close the customer client entirely.**
Approve from the staff portal as a `technician`.

**Passes when**: the work resumes and completes with no customer client running. This is the single
most important scenario in the scaffold — it is what a client-driven resume would have broken.

### V4 — Consent is an action, not a sentence (SC-IDENT-001)

Drive a session to the `END_USER_APPROVAL` reference operation. Type "yes, go ahead" in the chat.

**Passes when**: nothing happens. Then submit the explicit consent action and the work continues.

### V5 — Roles intersect, they do not rank (SC-AUTHZ-001)

Sign in holding only `administrator` and attempt to approve.

**Passes when**: denied. Repeat holding both `administrator` and `technician` — approval succeeds, and
both portal modules are visible.

### V6 — The surface decides the persona (SC-AUTHZ-002)

Sign in to a **customer** surface holding every staff role.

**Passes when**: you get exactly end-user permissions, your staff roles confer nothing, and the staff
portal offers no way to start a session.

### V7 — Suspension is durable (SC-INTR-001)

Drive a session to a clarifying question. Leave it at least 24 hours. Return and answer.

**Passes when**: the conversation resumes with prior context intact and continues streaming.

### V8 — Duplicate triggers produce one effect (SC-EXEC-002)

Publish the same resume trigger twice.

**Passes when**: exactly one execution and exactly one external effect. The second is absorbed by the
atomic claim.

### V9 — Expiry is not an error (spec FR-EXEC-001)

Approve an operation and let the fifteen-minute window elapse without execution.

**Passes when**: the work becomes non-executable, no error is raised, and it appears in the staff
portal as approved-but-not-executed.

### V10 — Tenant isolation holds (SC-IDENT-002)

Run the isolation and adversarial retrieval suites; attempt to read another organisation's session by
identifier.

**Passes when**: zero cross-organisation exposure on every path, and a foreign session returns 404 —
not 403, because existence is itself tenant-scoped information.

### V11 — The two deployables are independent (SC-EXT-002 adjacent)

Stop the .NET monolith. Hold a conversation, trigger an approval, resume and execute. Then restart the
monolith and stop RagCore; browse listings and dashboards.

**Passes when**: each works with the other completely absent. This is the observable proof of ADR-0001
— if either fails, an application dependency has crept in.

### V12 — Discovery is not entitlement (SC-EXT-001)

Point RagCore at an MCP server advertising an unregistered capability.

**Passes when**: the capability is not callable. Register it and entitle it to one organisation —
it becomes callable there and nowhere else.

### V13 — Accessibility (SC-SURF-002, SC-SURF-003)

Run the axe-core sweep across all three surfaces, then complete every primary journey by keyboard only.

**Passes when**: zero Level A or AA failures, and sign-in, session, streamed response, consent prompt
and approval queue are all completable without a pointer.

### V14 — Electron decides nothing (spec FR-SURF-004)

Run the Electron security suite.

**Passes when**: `contextIsolation` on, `nodeIntegration` off, sandbox on, IPC rejects unvalidated
messages, navigation outside the allow-list is blocked, and no policy or authorization decision exists
in the host.

### V15 — Migrations reverse (ADR-0003)

```bash
cd ragcore && pytest --test-alembic
```

**Passes when**: single head, upgrade from base, models match DDL, and **every downgrade succeeds**.

### V16 — The outbox survives a crash (research R-017)

Kill the process between the state commit and the dispatcher publishing.

**Passes when**: the outbox row is durable, the dispatcher publishes it on restart, and exactly one
effect results. Nothing is lost and nothing is duplicated.

### V17 — Configuration fails fast (research R-019)

Remove a required setting and start each deployable.

**Passes when**: the process refuses to start with a clear message, rather than starting and failing
later on an untested path.

### V18 — Optimistic concurrency, no locks (research R-018)

Drive two concurrent updates to the same work item.

**Passes when**: one succeeds, the other sees a version conflict and re-reads. No distributed lock is
taken anywhere.

### V19 — Container hardening

Inspect the built production images. The two runtimes are checked against **different** lists — see
plan.md Stage 10. A single combined list cannot pass: `chiseled` is a .NET image family, and the
RagCore image is a slim Python base that has a shell by design.

**The .NET image passes when**: chiseled, digest-pinned, non-root UID 1654, no shell, no package
manager, read-only root filesystem.

**The RagCore image passes when**: digest-pinned, non-root under a fixed documented UID, installed from
`uv.lock` only, no build toolchain and no package-manager cache in the final layer, read-only root
filesystem with every writable path named.

**Both pass when**: explicit resource limits, HTTP health probes and a 25-second drain are configured.

## Gate summary

| Gate | Command |
|---|---|
| .NET build and analyzers | `dotnet build -warnaserror` |
| .NET architecture rules | `dotnet test tests/Synthia.ArchitectureTests` |
| Python lint and format | `ruff check . && ruff format --check .` |
| Python types | `mypy --strict src/` |
| Migrations | `pytest --test-alembic` |
| Cross-deployable boundary | `build/scripts/check-boundaries` |
| Accessibility | `npm run test:a11y` |

A failure in any of these blocks the merge. No performance figure appears in this table — nothing is
gated on responsiveness (constitution Section 2).

## Validating the Integrations Service boundary *(added 2026-09-18)*

Stage 17's golden path C. Each runs against a **deployed** environment (`FR-DEMO-019`) and acts only on
the inert reference connector. Numbering continues the sequence above; identifiers are never reused.

### V20 — RagCore cannot reach an external connector (SC-DEMO-015)

Three separate observations, **all required**. From RagCore's runtime: attempt a direct connection to
the inert reference connector and observe it fail at the network layer; attempt to resolve a connector
secret and observe Key Vault refuse; run the architecture check asserting no adapter, connector or
provider client remains in the RagCore tree.

*Attempting it is the point.* An assertion that the path is unused passes equally on a system where
the path exists and simply has no caller yet.

### V21 — The synchronous call goes through APIM (SC-DEMO-016)

Read the tool catalogue and perform an inert case-like operation, both through the deployed edge.
Then attempt the same calls by the service's internal address, and again with a well-formed but
**self-supplied** identity contract. Expect success on the first, refusal on both others.

### V22 — Asynchronous execution over the message transport (SC-DEMO-017)

Dispatch an inert capability. Inspect the command on the queue: it carries `jobId`, `correlationId`
and `kind`, and **nothing else**. Confirm the Integrations Service read its capability and parameters
from the job row.

### V23 — Duplicate delivery, both boundaries, separately (SC-DEMO-018)

Two independent runs, not one:

1. Deliver a resume trigger twice; confirm the **atomic claim** in RagCore absorbed it.
2. Deliver an execution command twice; confirm the **derived idempotency key** in the Integrations
   Service absorbed it, and that exactly one execution record exists.

Then remove each boundary in turn and confirm **its own** proof fails. A single end-to-end duplicate
test passes whenever either mechanism holds, and would stay green on the day one silently broke.

### V24 — The organisation is not taken from a payload (SC-DEMO-019)

Publish a command carrying an organisation field; expect it dead-lettered with an alert and never
processed. Separately, publish a valid command whose payload asserts a *different* organisation than
the job row; expect the effect bound to the job row's organisation.

### V25 — Connector secrets are unreachable from RagCore (SC-DEMO-020)

Enumerate what RagCore's managed identity can resolve in Key Vault: zero connector secrets. Scan its
source, configuration, environment and image: zero connector secrets.

### V26 — Results correlate back to the originating work (SC-DEMO-021)

Follow one correlation identifier from the edge, through the gateway hop, across both queues, into the
execution record and back to the work item. One identifier, whole journey, three deployables.

### V27 — Integrations is independently observable (SC-DEMO-022)

Query the Integrations Service's traces, connector metrics and execution records **without reading
RagCore's telemetry**, and answer: what was attempted, against which connector, with what outcome and
how long it took.

### V28 — Degradation when Integrations is down (SC-DEMO-023)

Stop the Integrations Service. Confirm conversation, retrieval and guidance still succeed, and that a
capability requiring an external effect falls back to manual resolution or escalation **visibly** —
nothing is reported to a user as completed.

## Known limits of the scaffold

- **No use case resolves.** UC-01 through UC-12 are placeholders. Every action-requiring request
  escalates, by design.
- **No script executes.** The desktop path and its safeguards exist, but the catalogue holds only inert
  fixtures.
- **Reference operations are not product.** They are labelled fixtures, excluded from production
  configuration, and must never be presented as capability.
