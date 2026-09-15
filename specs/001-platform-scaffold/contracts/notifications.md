# Notification Contract (SignalR)

## The rule that defines this contract

**SignalR is a leaf on every consequential path, never a link.** It may tell a client that something
exists or has changed. It may never carry, imply or trigger a decision. Every consequential decision
arrives as an authenticated API request that identifies the decider.

A client that acts on a notification does so by calling an API — and that API re-decides the
authorization from scratch, as if no notification had been sent.

## Publishing

RagCore publishes directly to the Azure SignalR Service **data-plane REST API** using a Microsoft Entra
token obtained from managed identity (credential scope `https://signalr.azure.com/.default`, with
RBAC). No access key is used, and **no .NET component is involved** — this is what keeps ADR-0001's
no-dependency rule intact.

| Operation | API |
|---|---|
| Notify one user | `POST /api/hubs/{hub}/users/{user}/:send` |
| Notify a group | `POST /api/hubs/{hub}/groups/{group}/:send` |
| Issue a client token | `POST /api/hubs/{hub}/:generateToken` |

## Connection and groups

A client negotiates through `POST /api/customer/v1/realtime/negotiate` (RagCore). Group membership is
derived from the trusted identity context at negotiation time. **A client never asks to join a group by
identifier.**

## Envelope

```json
{
  "kind": "interrupt.pending",
  "occurredAt": "2026-09-15T10:04:05Z",
  "correlationId": "…",
  "sessionId": "…",
  "workItemId": "…"
}
```

| Field | Rule |
|---|---|
| `kind` | One of the event kinds below |
| `correlationId` | Always present; ties the notification to the originating request and to audit |
| Identifiers | Opaque. The client fetches detail through an authenticated API call |

**The envelope carries no authority-bearing value** — no tenant, no role, no approval state, no target,
no command content. A consumer that reads authority from a notification is defective regardless of
where the message came from.

## Event kinds

| Kind | Meaning | What the client does |
|---|---|---|
| `interrupt.pending` | Work suspended awaiting a decision | Fetch detail, then call the appropriate API |
| `approval.decided` | A verdict was recorded | Refresh the queue view |
| `work.progressed` | Step trail advanced | Refresh the step trail |
| `work.completed` | Execution finished | Fetch outcome |
| `work.failed` | Execution failed | Fetch detail; a human decides what happens next |
| `instruction.ready` | An authorized instruction can now be fetched | Fetch it from the Customer API — never from this channel |
| `session.taken_over` | A person joined the conversation | Show that a human is present |

## Availability

The platform continues without the channel. Clients recover state by querying the APIs, so a missed
notification delays awareness but never loses work and never changes what is authorized.
