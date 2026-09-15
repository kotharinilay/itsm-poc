# Workload API Contract

**Audience**: workload — the non-human execution principal, app-only authorization.

In the initial release the Workload principal runs inside the RagCore runtime. This is an accepted and
documented risk, not an oversight (platform specification §18.2, §35.2); splitting it into its own
runtime is the recommended direction for general availability (OQ-02), and the Service Bus seam exists
so that split is a deployment change rather than a redesign.

## Rules

1. The Workload **never** carries customer-tenant authority. Its target organisation is resolved only
   from the work item.
2. It executes only work that is approved, active, unclaimed and unexpired.
3. It claims atomically before acting — idempotency boundary 1.
4. It carries an idempotency key to every external system — idempotency boundary 2.
5. A failed execution does **not** re-fire; it requires fresh human authorization.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/workload/v1/work/{workItemId}/claim` | Atomic claim. 409 if already claimed, expired, or not authorized |
| `POST` | `/api/workload/v1/work/{workItemId}/outcome` | Record outcome with verification result |
| `GET` | `/api/workload/v1/health` | Liveness for the execution leg |

## Outcome body

```json
{
  "status": "executed",
  "verification": "server_confirmed",
  "detail": {}
}
```

`status` is `executed` or `failed`. `verification` is mandatory and is one of `server_confirmed`,
`client_attested` or `contradicted`.

A `client_attested` outcome must not be reported to a user or written to the system of record as
confirmed resolution (ADR-0004).
