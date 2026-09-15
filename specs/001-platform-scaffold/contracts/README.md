# Interface Contracts: Synthia Platform Engineering Scaffold

**Date**: 2026-09-15 | **Plan**: [../plan.md](../plan.md)

These are behavioural contracts, not generated schemas. Concrete OpenAPI documents are produced by the
implementations and validated against these by contract tests.

## Audiences and routing

Identity is derived once, at APIM. Both deployables consume the same closed Gateway-derived header
contract and neither parses a token.

| Path prefix | Deployable | Audience | Nature |
|---|---|---|---|
| `/api/customer/v1/...` | RagCore | Customer | Conversation, streaming, consent, instruction, result, feedback, negotiate |
| `/api/customer/v1/views/...` | .NET | Customer | Read models |
| `/api/staff/v1/...` | RagCore | Staff | Approval verdict, take-over, cancellation |
| `/api/staff/v1/views/...` | .NET | Staff | Queues, step trail, dashboards |
| `/api/workload/v1/...` | RagCore | Workload | Execution-leg operations |

A client legitimately calls both deployables. They are two backends behind one trust boundary.

## Conventions binding every endpoint

| Concern | Rule |
|---|---|
| Versioning | URI segment (`/v1/`). A breaking change adds `/v2/`; it never mutates `/v1/` |
| JSON casing | camelCase, both directions, both deployables |
| Errors | RFC 9457 `application/problem+json` with `type`, `title`, `status`, `detail`, `instance`, `correlationId` |
| Correlation | `X-Correlation-Id` accepted at the edge, echoed on every response, carried on every trigger, notification, log, span and audit record |
| Tenant | **Never** a parameter. Derived from the header contract for end users; from the platform object being operated on for staff |
| Roles | **Never** a parameter. Derived from the header contract |
| Routing | Resource-oriented, plural nouns, kebab-case for multi-word segments; HTTP verbs carry the action. Action-style routes only where an operation is genuinely command-like |
| Pagination | **Keyset/cursor** by default: `?limit=&cursor=`; response carries `items` and `nextCursor`. Cursors are **opaque** to clients. Offset paging only where explicitly justified |
| Sorting | `?sort=field` / `?sort=-field`, over a **whitelisted** field set — enumerated per resource below. An unknown sort field is a 400 |
| OpenAPI | Generated from the application contracts — built-in OpenAPI in .NET, FastAPI schemas in RagCore |
| Filtering / sorting | Allow-listed fields only. An unknown field is a 400, never silently ignored |
| Idempotency | Any state-changing endpoint accepts `Idempotency-Key`; a repeat returns the original outcome |
| Auth failure | 401 unauthenticated, 403 unauthorized, **404 where existence itself is tenant-scoped information** |

## Sortable and filterable fields, per resource

The policy above is only enforceable against a concrete list. **These are the complete sets.** A field
absent from a row below is not sortable or filterable on that resource, and a request naming one is a
400 — never silently ignored. Adding a field is a contract change.

| Resource | Sortable | Filterable |
|---|---|---|
| `GET /api/customer/v1/views/sessions` | `createdAt`, `updatedAt`, `state` | `state` |
| `GET /api/customer/v1/views/sessions/{id}/messages` | `createdAt` | `senderKind` |
| `GET /api/customer/v1/views/sessions/{id}/steps` | `createdAt` | — |
| `GET /api/staff/v1/views/sessions/live` | `createdAt`, `updatedAt`, `state` | `state`, `tenantId` |
| `GET /api/staff/v1/views/approvals/queue` | `createdAt`, `expiresAt` | `tenantId` |
| `GET /api/staff/v1/views/approvals/unexecuted` | `decidedAt`, `expiresAt` | `tenantId` |
| `GET /api/staff/v1/views/audit` | `occurredAt` | `tenantId`, `workItemId`, `eventKind`, `occurredAt` (range) |
| `GET /api/staff/v1/views/tenants` | `displayName`, `status` | `status` |

**`tenantId` as a filter is a staff-only narrowing, never a widening.** It selects within the set the
caller may already see; it is not a tenant parameter and does not establish authority (see rule 1
below). It is absent from every customer resource, where the organisation is derived and a filter on
it would be meaningless.

Default sort is `-createdAt` (or `-occurredAt` for audit) where the client supplies none, so keyset
pagination always has a deterministic order.

## Rules that outrank any endpoint definition

1. No endpoint accepts a tenant, role or audience parameter and trusts it.
2. The realtime channel carries no decision. Every consequential decision arrives as an authenticated
   request on one of the APIs above.
3. The .NET monolith exposes **no** state-changing endpoint. Every `views` route is a read.
4. Neither deployable calls the other. There is no internal service-to-service contract between them.

## Documents

| File | Contract |
|---|---|
| [customer-api.md](./customer-api.md) | Customer audience — RagCore and .NET |
| [staff-api.md](./staff-api.md) | Staff audience — RagCore and .NET |
| [workload-api.md](./workload-api.md) | Workload audience |
| [read-views.md](./read-views.md) | PostgreSQL view contract between the deployables |
| [notifications.md](./notifications.md) | SignalR envelope |
| [triggers.md](./triggers.md) | Service Bus trigger message |
