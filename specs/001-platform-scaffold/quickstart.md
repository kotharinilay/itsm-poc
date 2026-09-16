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

```bash
# 1. Database — migrations run as a job, never at application startup
cd ragcore
alembic upgrade head

# 2. RagCore API and the resume worker (separate processes, same image)
uv run uvicorn ragcore.api:app --reload
uv run python workers/resume_worker.py

# 3. The read-only monolith
cd ../dotnet
dotnet run --project src/Synthia.Api

# 4. Any client surface
cd ../apps/web
npm run start:customer-portal     # or start:staff-portal
cd ../desktop && npm run start    # Electron host
```

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

### V2c — The service boundary, and the bypass that must fail (SC-DEMO-003a, SC-DEMO-003b)

*Flow **B3**. The negative half is the point.*

1. `POST /api/customer/v1/sample-flows/service-hop` through APIM. Confirm the callee reports an
   app-only caller carrying no customer-organisation authority.
2. Send the same request **directly to the container**, bypassing the edge and gateway.
3. Send it again directly, this time carrying a **well-formed, self-supplied gateway header
   contract** — the shape a real bypass takes.

**Expected**: step 1 succeeds; steps 2 and 3 both fail. A pass on step 3 means the deployable is
trusting a header it should only ever accept from APIM, which is the whole vulnerability.

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

## Known limits of the scaffold

- **No use case resolves.** UC-01 through UC-12 are placeholders. Every action-requiring request
  escalates, by design.
- **No script executes.** The desktop path and its safeguards exist, but the catalogue holds only inert
  fixtures.
- **Reference operations are not product.** They are labelled fixtures, excluded from production
  configuration, and must never be presented as capability.
