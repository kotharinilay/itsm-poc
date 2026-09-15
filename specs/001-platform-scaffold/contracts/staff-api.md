# Staff API Contract

**Audience**: staff. Only reachable from the staff portal. The target organisation is **always**
derived from the platform object being operated on, never supplied by the caller.

## Role model

`technician`, `senior_technician` and `administrator` are independent capabilities with no hierarchy.
Authorization is **set intersection** between the roles held and the roles the operation accepts. An
empty intersection denies. `administrator` does not imply `technician`.

In the initial release `technician` may approve and `administrator` may not; no operation accepts
`senior_technician`.

Any implementation that sorts, ranks or compares roles is a defect.

## RagCore — commands

| Method | Path | Accepts roles | Purpose |
|---|---|---|---|
| `POST` | `/api/staff/v1/approvals/{approvalId}/verdict` | `technician` | Approve or reject |
| `POST` | `/api/staff/v1/sessions/{sessionId}/takeover` | `technician` | Transition to staff-controlled |
| `POST` | `/api/staff/v1/sessions/{sessionId}/messages` | `technician` | Send a message into a taken-over session |
| `POST` | `/api/staff/v1/work/{workItemId}/cancel` | `technician` | Cancel before execution is claimed |

### Verdict

Request body:

```json
{ "verdict": "approved", "note": "optional" }
```

- Requires a fresh staff token. Recorded against `decided_by_oid` with the role set held at the time.
- First valid verdict wins; a later one is recorded but does not change the outcome.
- On approval, `expires_at` is set to now plus 15 minutes and a trigger is published. **The request
  returns before execution runs.**
- No system-generated verdict, no approval by timeout.

### Take-over

An authenticated state transition, not a socket message. The staff member becomes an additional sender
in the end user's session. It does **not** transfer requester authority — consent for that user's own
account or device still belongs to the original end user.

### Cancel

Permitted before the claim. After the claim, execution completes and the outcome is recorded normally.

## .NET — staff read models

| Method | Path | Accepts roles | Purpose |
|---|---|---|---|
| `GET` | `/api/staff/v1/views/sessions/live` | `technician` | Live sessions. Cursor paged |
| `GET` | `/api/staff/v1/views/approvals/queue` | `technician` | Pending approvals, with full disclosed commands |
| `GET` | `/api/staff/v1/views/approvals/unexecuted` | `technician` | **Approved but never executed** — the dead-letter surface (ADR-0002) |
| `GET` | `/api/staff/v1/views/sessions/{sessionId}` | `technician` | Session detail and step trail |
| `GET` | `/api/staff/v1/views/audit` | `technician` | Audit search. Cursor paged |
| `GET` | `/api/staff/v1/views/dashboard/platform` | `administrator` | Platform dashboard |
| `GET` | `/api/staff/v1/views/tenants` | `administrator` | Organisation registry |

Note the split: the approval **queue** is read from the monolith; the **verdict** is written to
RagCore. Because both share one database, the read reflects the write immediately.

## Absent by design

There is **no** endpoint on this audience to start a chat session or raise a request. Staff needing
their own support use a customer surface.
