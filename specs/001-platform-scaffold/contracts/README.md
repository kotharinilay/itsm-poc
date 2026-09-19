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
| `/api/workload/v1/integrations/...` | **Integrations Service** | Workload | Tool catalogue; synchronous system-of-record operations |
| `/api/workload/v1/...` | RagCore | Workload | Execution-leg operations |

**Longest matching path wins**, the same rule that puts `/views` on the monolith.

A client legitimately calls **two** of the three deployables — RagCore and the .NET read API. They are
two backends behind one trust boundary. **The Integrations Service is not client-facing**: only
RagCore calls it, on the workload audience, through APIM like any other caller.

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
4. **Neither deployable reaches the other directly, and no internal service-to-service contract
   exists between them.** *Clarified 2026-09-16.* Service-to-service interaction takes two permitted
   forms, and neither is a direct route:
   - **Asynchronous** — the two sides meet at Service Bus and at the published views. No application
     dependency exists in either direction.
   - **Synchronous** — a service reaches another through the **workload audience**, app-only, and the
     call routes **through APIM** like any other. APIM is the trust boundary and the single place
     identity is derived.

   A direct route — pod to pod, container to container, or by any internal address that bypasses the
   gateway — MUST NOT exist. The scaffold proves this by attempting one and observing it fail
   (spec `FR-DEMO-004a`, `SC-DEMO-003a`).

   > **The stronger half of this rule is deferred.** It used to include a request carrying a
   > well-formed but self-supplied gateway header contract — the shape a real bypass takes. That is
   > `SC-DEMO-003b`, deferred with the control that made it fail
   > ([ADR-0008](../../../docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md)).
   > A service reached directly, from inside the environment, with a complete forged contract, is
   > now believed. No route is *declared* to make that reachable, and none may be added.
5. **Every audience emits its own OpenAPI document from the running service.** A merged document is
   prohibited: it would let a customer-facing client discover the staff and workload surfaces. CI
   publishes versioned artifacts and contract tests validate the emitted documents rather than
   hand-written copies (spec `FR-DEMO-013`).

## The emitted contract

*Added 2026-09-17, when emission became a gated pipeline rather than a step that produced files.*

Five artifacts, one per audience per deployable, under `build/contracts/{dotnet,ragcore}/`:
`customer.v1.openapi.json`, `staff.v1.openapi.json` and — RagCore only — `workload.v1.openapi.json`.
The .NET deployable emits no workload document, because an empty contract reads as "this surface has
no operations" rather than "this surface is somewhere else".

**The application contract is the source, and there is no second copy of it.** Request and response
schemas come from the Pydantic models and the .NET read models the services already use. Where the
generator could not see something the endpoint accepts — the paging, sorting and filtering
parameters the .NET handlers read from the query string themselves — the *endpoint's own whitelist*
was moved onto the route as metadata and is read by both the binder and the document transformer.
Restating the fields in a transformer would have produced a correct document and the drift this rule
exists to prevent.

**What CI asserts, in order** (`.github/workflows/contracts.yml`):

| Gate | What fails the build | Where |
|---|---|---|
| Generation | A document that cannot be produced from a running service | the emit steps |
| Determinism | Two emissions of the same source differing by a byte | emit twice, `diff -r` |
| Publishability | Secret or configuration material; a client-suppliable tenant, role or audience; an error contract that is not RFC 9457 | `build/scripts/openapi_validate.py` |
| Compatibility | A breaking difference against the committed contract, unless approved | `build/scripts/openapi_diff.py` |
| Freshness | A committed contract that no longer matches what the service emits | `diff -r` |

**Determinism is a gate rather than a convention**, because every check above compares bytes. Both
emitters sort object keys and write bare line feeds; a generator that reordered a map or stamped the
host it ran on would make each build report changes nobody made and hide the ones somebody did.

**An approved breaking change is a record, not a flag.** `build/contracts/approved-breaking-changes.json`
holds the finding verbatim, who accepted it, why, what a client already built against the old
contract must do, and a date after which the approval stops applying. There is no environment
variable and no commit-message keyword that bypasses the gate. Versioning is in the URI segment, so
the usual honest answer to a breaking change is `/v2/` rather than a mutation of `/v1/`.

**`tenantId` is the one name whose legality depends on where it sits.** Forbidden as a parameter or a
request field on every audience — that would be a client asserting authority the platform derives.
Permitted as a **query** parameter on the **staff** documents, where it is the narrowing described
above. Permitted in any **response**, where it is the organisation a row belongs to being reported to
a caller already entitled to the row: a rule that forbade the name outright would force an audit read
model to hide the field a reviewer opens it for, and would be satisfied by renaming it rather than by
closing a channel. The rule and its one exception are data in `build/policy/openapi-disclosure.json`,
read by both stacks.

`build/scripts/verify-contract-guards.sh` plants each violation class in turn and asserts the guards
reject it — including that an approved breaking change is let through, and that an expired or
differently-worded approval is not. A gate nobody has seen fail is a gate whose failure mode is
silence.

## Documents

| File | Contract |
|---|---|
| [sample-flows.md](./sample-flows.md) | The scaffold's inert acceptance flows, and OpenAPI emission |
| [customer-api.md](./customer-api.md) | Customer audience — RagCore and .NET |
| [staff-api.md](./staff-api.md) | Staff audience — RagCore and .NET |
| [workload-api.md](./workload-api.md) | Workload audience — RagCore's execution leg |
| [integrations-api.md](./integrations-api.md) | **The Integrations Service** — catalogue, synchronous system-of-record operations |
| [read-views.md](./read-views.md) | PostgreSQL view contract between the deployables |
| [notifications.md](./notifications.md) | SignalR envelope |
| [triggers.md](./triggers.md) | Service Bus trigger message |
