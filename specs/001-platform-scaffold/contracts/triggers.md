# Trigger Contract (Service Bus)

## The rule that defines this contract

**Every trigger is untrusted.** The event causes work to happen; the durable work record provides the
authority and the tenant context. A consumer that reads authority from a message is defective
regardless of where the message came from.

## Message body

```json
{
  "workItemId": "…",
  "correlationId": "…",
  "kind": "approval.granted"
}
```

That is the entire payload. It carries — and may carry — **nothing else**.

Explicitly forbidden in a trigger: tenant, requester, roles, action, target, approval state, expiry,
command content, credentials, or any other authority-bearing value.

## Trigger kinds

`kind` names the decision that made the work resumable. It is a **routing hint only** — the consumer
reads the authority from the durable work record either way, and a consumer that decides anything from
`kind` is defective.

| Kind | Raised when | Who decided | Resumes to |
|---|---|---|---|
| `approval.granted` | A staff verdict authorized the work | A principal holding a role the operation accepts | Execution |
| `approval.rejected` | A staff verdict refused it | As above | Closure |
| `consent.granted` | The work item's own requester consented | The work item's `requested_by_oid`, and no one else | Execution |
| `consent.refused` | That requester refused | As above | Closure |
| `sample.flow` | The scaffold is proving the seam itself | Nobody — no decision was made | Inert sample execution |

The values mirror the `verdict` enums in `data-model.md` — `approved`/`rejected` for approval,
`granted`/`refused` for consent — so the message never introduces vocabulary the database does not
already hold. The two refusal kinds exist so a declined decision **closes the work honestly** rather
than leaving it suspended until it expires; they resume the graph but never reach execution.

This is a closed set. Adding a kind is a contract change, and no kind may imply an authority the work
record does not independently carry.

**`sample.flow` is the scaffold's own kind, added 2026-09-16**, and it is the exception that proves
the rule rather than a hole in it. No human decided anything, so it grants nothing; it exists so the
outbox-to-bus-to-consumer seam can be exercised end to end before any governed operation crosses it.
It resumes to an execution that acts only on an inert reference fixture and reaches no external
system (spec FR-DEMO-007, FR-DEMO-014). It MUST NOT be raised for, stand in for, or be counted as
any of UC-01 through UC-12.

The four decision kinds above remain specified in full; **their handlers are deferred** (spec
FR-DEMO-016). Until they land, a consumer receiving one dead-letters it with an alert — which is the
correct behaviour under the rule below, not a gap in it: an unhandled kind is never treated as
authorization to proceed.

## Why the queue exists at all

Both the publisher and the consumer currently live in the RagCore deployable, so a direct function call
would be simpler today. The queue is there for three reasons:

1. The approving request must return before execution runs.
2. At-least-once delivery, message expiry and dead-lettering are properties of the transport, not of a
   function call, and the fifteen-minute window depends on all three.
3. It keeps the verdict-to-execution boundary a **seam**, so the resume worker — or a further
   decomposition of RagCore — can become its own deployable later as a deployment change rather than a
   redesign. This is the direction the platform specification itself recommends (OQ-02) for separating
   credential classes.

## Delivery semantics

| Property | Rule |
|---|---|
| Delivery | At-least-once. Duplicates are expected |
| Idempotency — platform | The atomic claim on the work item absorbs duplicates |
| Idempotency — external | The idempotency key prevents a duplicate external effect |
| Expiry | Messages carry the same fifteen-minute bound as the execution window. An expired message dead-letters rather than executing |
| Dead letter | **Not** automatically replayed. Surfaces for operational handling |
| Ordering | Not assumed anywhere |

## Dispatcher obligations — before the message exists

The outbox row commits in the same transaction as the state change it describes; a dispatcher worker
publishes it afterwards and sets `dispatched_at`. That leaves one case the consumer rules above cannot
cover: **a row that never becomes a message.**

| Property | Rule |
|---|---|
| Attempts | Bounded. `attempts` increments per publish failure; the ceiling is **10** |
| Backoff | Exponential with jitter between attempts |
| Ordering | Not guaranteed and not assumed. A blocked row MUST NOT block dispatch of any other row |
| On ceiling | The row is marked **undispatchable** and left in place. It is never silently dropped and never auto-retried past the ceiling |
| Visibility | An undispatchable row carrying `approval.granted` or `consent.granted` is a **governance failure**, not an operational one, and surfaces exactly where dead-lettered approved work surfaces — `vw_approval_unexecuted_v1`, the staff portal's approved-but-not-executed list, plus an operational alert |
| Recovery | **Fresh authorization**, never replay — identical to the dead-letter rule below |

The two refusal kinds (`approval.rejected`, `consent.refused`) becoming undispatchable is an
operational alert only: no authority was granted, so nothing can execute on it. The work remains
suspended until cancelled or expired.

**Why a ceiling rather than indefinite retry.** The execution window is fifteen minutes. A row that
cannot publish within it can no longer lead to a valid execution, so retrying past that point creates
the illusion of pending work that can never complete. Surfacing it to a human is the honest outcome.

## Consumer obligations

On receiving a trigger, the resume worker MUST:

1. Load the work item from PostgreSQL by the opaque identifier.
2. Verify the work record independently carries the authority the kind claims — approved or consented
   as applicable — and that it is active, not cancelled and not expired. A refusal kind skips to closure.
3. Claim it atomically. If the claim fails, stop — another consumer has it.
4. Resume the graph from its checkpoint.
5. Execute under the Workload principal with an idempotency key.
6. Record the outcome with its verification result.

## Retry

| Stage | Policy |
|---|---|
| Pre-claim transient failure (database unreachable, message undeserializable) | Bounded exponential backoff with jitter, inside the remaining window. Exhausted attempts dead-letter |
| Post-claim execution failure | **No retry.** Record the outcome, escalate, leave the work item non-executable |

A failed authorized action requires fresh human authorization. Re-firing a failed consequential
operation without a human seeing the failure is the wrong default (ADR-0002, answering OQ-07).

## Dead-lettered approved work

Work a human approved but that never executed is a governance failure, not merely an operational one:

- An operational alert fires.
- The item appears in the staff portal as **approved, not executed**, with work identifier, approver,
  approval time and expiry.
- Recovery is **fresh authorization**, never replay.

## Expiry sweeper

A sweeper in the resume worker marks work non-executable once the window passes with no successful
claim. Expiry is a normal outcome and is not reported as an error.
