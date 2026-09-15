# Customer API Contract

**Audience**: customer. Every caller is an `end_user`, **including a Synoptek staff member** — staff
roles are not consulted on this audience and confer nothing (spec FR-SURF-008).

## RagCore — conversation and commands

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/customer/v1/sessions` | Start a session. Returns the session identifier |
| `POST` | `/api/customer/v1/sessions/{sessionId}/messages` | Send a message. **Streams the response** as `text/event-stream` |
| `POST` | `/api/customer/v1/sessions/{sessionId}/answers` | Answer a pending clarifying question |
| `POST` | `/api/customer/v1/work/{workItemId}/consent` | Grant or refuse consent |
| `GET` | `/api/customer/v1/work/{workItemId}/instruction` | Fetch the authorized execution instruction (desktop only) |
| `POST` | `/api/customer/v1/work/{workItemId}/result` | Post execution result and exit status (desktop only) |
| `PUT` | `/api/customer/v1/messages/{messageId}/feedback` | Record or revise a thumbs signal |
| `DELETE` | `/api/customer/v1/messages/{messageId}/feedback` | Withdraw a previously recorded signal |
| `POST` | `/api/customer/v1/realtime/negotiate` | Obtain a realtime connection token. Group membership derived from identity |

### Streaming

`POST .../messages` responds `text/event-stream`. Event kinds: `token` (partial content), `step`
(progress in the step trail), `interrupt` (work has suspended — carries kind and identifiers only),
`done`, `error`.

**The stream carries no authority.** An `interrupt` event tells the client that a decision is needed;
the decision is made by calling the consent or answer endpoint. The stream ending is not a decision.

### Consent

- Only the work item's `requested_by_oid` may consent. Anyone else receives 403.
- An affirmative chat message is **never** consent. Only this endpoint records it.
- Consent does **not** satisfy a `STAFF_APPROVAL` requirement.

Request body:

```json
{ "verdict": "granted" }
```

### Feedback

`PUT` is idempotent by design: feedback is **revisable**, so repeating it replaces the previous signal
rather than creating a second. Body:

```json
{ "signal": "positive" }
```

Only the session's owning user may record feedback, and only against an agent-authored message in
their own session. Anyone else receives 404 — existence is tenant-scoped information.

Feedback is a quality signal. It is never read by governance, retrieval or execution, and can never
influence an authorization outcome.

### Instruction fetch (desktop)

Returns work item id, catalogue id, catalogue version, content hash and parameters. The client
verifies all four before executing and aborts on any mismatch (ADR-0004). Never delivered over the
realtime channel. Returns 410 once the validity window has elapsed.

In the scaffold the catalogue holds only inert reference fixtures, so no real script is ever returned.

## .NET — customer read models

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/customer/v1/views/sessions` | List my sessions. Cursor paged |
| `GET` | `/api/customer/v1/views/sessions/{sessionId}` | Session detail |
| `GET` | `/api/customer/v1/views/sessions/{sessionId}/messages` | Conversation history. Cursor paged |
| `GET` | `/api/customer/v1/views/sessions/{sessionId}/steps` | Step trail |

Scoped to the caller's own organisation **and** their own sessions. A session belonging to another
user or organisation returns 404 — existence is itself tenant-scoped information.

## Accessibility obligations reaching the API

- Streamed content is delivered so assistive technology can announce it as it arrives without
  repeating already-announced text.
- Every interrupt carries a machine-readable `kind`, so a client can convey state by more than colour.
