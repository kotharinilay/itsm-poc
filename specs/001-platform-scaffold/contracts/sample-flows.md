# Sample Flow Contract

*Added 2026-09-16.* The scaffold's acceptance surface: the inert flows that prove the platform's
integration seams before any product exists (spec `FR-DEMO-001`–`FR-DEMO-019`).

**These are fixtures, and the contract says so.** Every operation below acts on a reference operation
that produces no real effect, is excluded from production configuration, and MUST NEVER be counted as
or allowed to become one of UC-01..UC-12. They live in their own document rather than being scattered
through the three audience contracts so that deleting them later is a deletion, not an excavation.

**They are not product capability and MUST NOT be presented as such** on any surface.

## What each flow proves

| Flow | Path | Proves |
|---|---|---|
| **B1** | Customer API → RagCore → PostgreSQL txn → outbox → Service Bus → workload leg → inert execution → persistence → SignalR → client refresh | The asynchronous round trip: transactional durability, the deployable seam, idempotent consumption, notification as a leaf |
| **B2** | Staff API → APIM → .NET read API → published view → response | The read contract as a runtime boundary, and least-privileged database access |
| **B3** | Customer API → APIM → RagCore → workload/service boundary | Synchronous service-to-service through the gateway, and that no direct route exists |

Every flow is **entered through Front Door + WAF + APIM** (`FR-DEMO-019`). A run against a deployable
directly does not satisfy this contract, and the negative case — a direct request failing — is part of
it rather than an afterthought.

## Endpoints, by audience

Each audience keeps its own emitted OpenAPI document. A merged document is prohibited: it would let a
customer-facing client discover the staff and workload surfaces.

### Customer audience — RagCore

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/customer/v1/sample-flows/round-trip` | Starts **B1**. Returns the correlation identifier and the identifier of the record created. Accepts no tenant, role or audience parameter |
| `GET` | `/api/customer/v1/sample-flows/round-trip/{id}` | The client state refresh at the end of **B1**. Returns the outcome the workload leg persisted |
| `POST` | `/api/customer/v1/sample-flows/service-hop` | Starts **B3**. Reaches the workload boundary through APIM and returns what the callee reported about the caller's identity |

### Staff audience — .NET read API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/staff/v1/sample-flows/records` | **B2**. Reads `vw_*_v1` only. Target organisation resolved from the platform object, never from the request |

### Workload audience

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/workload/v1/sample-flows/execute` | The inert execution in **B1**, reached app-only. Claims atomically, performs no external effect, records an outcome |

## Rules binding every sample flow

1. **Inert.** No external effect, no account, device or record modified (`FR-DEMO-014`).
2. **Not a use case.** Never counted as, substituted for, or allowed to become UC-01..UC-12
   (`FR-DEMO-015`).
3. **No tenant, role or audience parameter is accepted or trusted.** Identity is derived once, at
   APIM; organisation comes from the derived context for end users and from the platform object for
   staff.
4. **Idempotent by construction.** A repeated trigger or a repeated request produces exactly one
   effect — the atomic claim absorbs the duplicate.
5. **The notification authorizes nothing.** B1 reaches the same outcome with no client connected; the
   client learns the result by reading back, not from the notification payload.
6. **The trigger carries nothing authority-bearing** — opaque identifiers and correlation only, per
   [triggers.md](./triggers.md).
7. **No model call, no retrieval query, no cache read.** Those are product behaviour. A sample flow
   that reached the AI Gateway, AI Search or Redis would be proving the wrong thing.
8. **No approval, no consent, no endpoint execution, no desktop script** (`FR-DEMO-016`).

## OpenAPI emission

| Requirement | Applies to |
|---|---|
| Emitted from the running service, never hand-maintained | Both deployables |
| Generated from the route models — FastAPI for RagCore, the built-in generator for .NET Minimal APIs | Both |
| One document per audience — `customer`, `staff`, `workload` | Both |
| Versioned artifacts published by CI on every build | CI |
| Contract tests validate the **emitted** document, not a copy | CI |

A route whose emitted shape stops matching its declared contract fails the build rather than surfacing
at a client (`SC-DEMO-011`).
