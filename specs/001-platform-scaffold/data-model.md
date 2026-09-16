# Phase 1 Data Model: Synthia Platform Engineering Scaffold

**Date**: 2026-09-15 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

PostgreSQL is the single authoritative durable store (constitution Principle IV). RagCore owns every
table and every migration; the .NET monolith reads only through versioned views defined in
[contracts/read-views.md](./contracts/read-views.md).

**Schemas**

| Schema | Owner | Contents |
|---|---|---|
| `platform` | RagCore / Alembic | Every table below |
| `langgraph` | LangGraph checkpointer's own `setup()` | Checkpoint tables. Excluded from Alembic autogenerate |

**Conventions** (constitution v3.1.0): every mutable row carries a `version` column for **optimistic
concurrency** — no pessimistic or distributed locking exists. Standard audit columns (`created_at`,
`updated_at`, and `created_by`/`updated_by` where a principal is meaningful) apply to every table.

**Optimistic concurrency — two exemptions, both named.**

*`idempotency_record`* carries no `version` column. It is written once at claim time and updated
exactly once when `outcome` is recorded; its `idempotency_key` primary key already serialises every
concurrent writer, so a version column would add a second concurrency mechanism to a row that
structurally cannot have two live writers.

*`governance_record`* carries no row-version column either, and for a different reason: its
`version` column is **half the primary key**, not a row counter. A catalogue entry is never edited
in place — a change is a new `(catalogue_id, version)` row, and the old one stays exactly as it was
because an approval granted against it must keep meaning what it meant. A second `row_version`
would be a concurrency mechanism on a row that structurally cannot be updated.

Every other table in this document carries `version`, including the append-only ones (`message`,
`consent`, `audit_event`) where the value stays `1` for the life of the row — the runtime principal
holds no `UPDATE` grant on `audit_event`, so that constancy is enforced by the database rather than
asserted by convention. **No further exemption exists**, and adding one requires naming it here;
`tests/concurrency/test_optimistic.py` fails until it is.

**Soft delete — no entity in the scaffold uses it.** The convention is: a row requiring soft deletion
carries `deleted_at`, excluded by a global query filter and by every published view. **No table below
declares `deleted_at`, and none is intended to.** Erasure (FR-AUDIT-006) is a hard delete, because a
soft-deleted row is still the organisation's data and would defeat the requirement. Retention
(FR-SESS-007) is likewise a removal, not a flag. The convention is reserved for a future entity that
needs recoverable deletion; the first table to adopt it states why here.

**Isolation level — Read Committed everywhere; no Serializable transaction exists.** Every invariant
in this model is enforced by a constraint or an atomic conditional update rather than by isolation
level: the work-item claim is a conditional update on `claimed_at IS NULL`; first-valid-verdict-wins
rests on the unique `work_item_id` on `approval`; duplicate external effects are prevented by the
`idempotency_key` primary key; feedback revision rests on the unique `(message_id, given_by_oid)`.
**Serializable is not used anywhere in the scaffold.** If a future invariant genuinely needs it, it is
named here first, because an unnamed Serializable transaction is indistinguishable from a copy-paste.

Every durable identifier is a UUID. Every timestamp is `timestamptz` stored in UTC.
Every tenant-scoped table carries `tenant_id` as a non-nullable column and every repository applies it
— there is no query path that omits it. Money, counters and free text are out of scope for the
scaffold.

---

## Sample flows add no entity

*Added 2026-09-16.* The scaffold's acceptance flows (spec `FR-DEMO-001`–`FR-DEMO-019`,
[contracts/sample-flows.md](./contracts/sample-flows.md)) introduce **no table, no column and no
enum**. They reuse what is already here:

| Flow step | Entity it uses |
|---|---|
| The record a customer sample flow creates | `chat_session` + `work_item` |
| The inert operation it proposes | `operation`, bound to a `governance_record` reference fixture |
| The message announcing the state change | `outbox_message`, committed in the same transaction |
| The workload leg's atomic claim | `work_item.claimed_at` — idempotency boundary 1 |
| The external-effect guard | `idempotency_record` — idempotency boundary 2 |
| The outcome the client reads back | `work_item.outcome` + `operation.verification` |
| What the flow leaves behind | `audit_event` |
| What the staff read seam reads | `vw_*_v1`, never a base table |

**This is deliberate and is the point.** A sample flow that needed its own schema would be proving a
fixture rather than the platform. If a future flow appears to need a new entity, that is a signal the
flow is drifting into product behaviour, not that the model is missing something.

Approval and consent remain modelled below in full. The scaffold does not write to `approval` or
`consent` (`FR-DEMO-016`); the tables, their constraints and their rules are unchanged, because the
deferral is of a demonstration rather than of a design (`FR-DEMO-017`).

---

## Tenant mapping

Binds a validated Entra tenant identifier to its platform representation.

| Field | Type | Notes |
|---|---|---|
| `tenant_id` | uuid, PK | Platform identifier |
| `entra_tid` | uuid, unique, not null | The validated `tid`. The only accepted external key |
| `display_name` | text, not null | |
| `status` | enum, not null | `active`, `suspended`, `offboarded` |
| `retention_overrides` | jsonb, null | Per-class overrides; platform defaults apply when absent |
| `created_at`, `updated_at` | timestamptz | |

**Rules**: `entra_tid` is the only value that may be matched against a token-derived tenant. Work does
not execute when status is not `active` (spec FR-EXEC-003). No region column — single region by decision
(spec FR-SURF-015).

---

## Chat session

One conversation. 1:1 with a work item.

| Field | Type | Notes |
|---|---|---|
| `session_id` | uuid, PK | Opaque to clients |
| `tenant_id` | uuid, FK, not null | |
| `requester_oid` | uuid, not null | Entra `oid` of the end user |
| `state` | enum, not null | The nine states below — **not** a four-value enum |
| `case_reference` | text, null | Reference to the case in the system of record. Set when the triage gate fires |
| `created_at`, `updated_at`, `closed_at` | timestamptz | |
| `content_expires_at` | timestamptz, **null while active** | Set when the session reaches a terminal state: that timestamp + retention (default 90 days). Null means not yet eligible to expire (spec FR-SESS-020) |

**States** (spec FR-SESS-015): `conversational`, `resolving`, `awaiting_user`, `awaiting_consent`,
`awaiting_approval`, `staff_controlled`, and terminal `resolved`, `escalated`, `closed_declined`.
The three `awaiting_*` states persist indefinitely; losing the realtime connection changes nothing.
A session exists only once a genuine problem is articulated — greetings create nothing (spec FR-SESS-003).

---

## Message

| Field | Type | Notes |
|---|---|---|
| `message_id` | uuid, PK | |
| `session_id` | uuid, FK, not null | |
| `tenant_id` | uuid, not null | Denormalised for non-bypassable filtering |
| `sender_kind` | enum, not null | `end_user`, `agent`, `staff` |
| `sender_oid` | uuid, null | Null for `agent` |
| `body` | text, not null | |
| `created_at` | timestamptz, not null | |

**Rules**: a `staff` message is only valid while the session is `staff_controlled`, and its presence
never confers requester authority (spec FR-SURF-009). Messages are removed with their session's content
retention; audit is unaffected (spec FR-AUDIT-004).

---

## Session step

One entry in the progress trail a client renders while work is in flight. Owned by the Session
context.

| Field | Type | Notes |
|---|---|---|
| `step_id` | uuid, PK | |
| `session_id` | uuid, FK, not null | |
| `tenant_id` | uuid, not null | |
| `kind` | text, not null | A machine-readable step kind, for the client to localise |
| `summary` | text, not null | A short, client-safe description |
| `created_at`, `updated_at` | timestamptz | |

**Added at Stage 7, and why.** [contracts/read-views.md](./contracts/read-views.md) publishes
`vw_session_step_v1` and the monolith's `SessionStepRow` reads it, but this document named no table
behind it. Recorded here rather than resolved by dropping the view, which would have left a
published contract with nothing underneath it.

**Rules**
- **Carries no authority field** — no treatment, no verdict, no target. A step says *something is
  happening*; it never says *this was allowed*.
- Follows chat-content retention: a step trail describes a conversation and expires with it.

---

## Feedback

A per-message thumbs signal. Owned by the Session context.

| Field | Type | Notes |
|---|---|---|
| `feedback_id` | uuid, PK | |
| `message_id` | uuid, FK, not null | The agent-authored message being rated |
| `session_id` | uuid, FK, not null | |
| `tenant_id` | uuid, not null | |
| `given_by_oid` | uuid, not null | Must be the session's `requester_oid` |
| `signal` | enum, not null | `positive`, `negative` |
| `created_at`, `updated_at` | timestamptz | |

**Unique constraint** on (`message_id`, `given_by_oid`) — feedback is **revisable**, so a change
updates the existing row rather than inserting a second. Withdrawal deletes the row.

**Rules**
- Only the session's owning user may record feedback, and only on a message in their own session.
- Feedback MUST NOT be read by governance, retrieval or execution. It is a quality signal and is
  never an input to a decision.
- Follows chat-content retention (90 days). Aggregate figures derived for reporting are retained
  independently, so expiring signals does not erase reporting history.

---

## Work item — the durable authority record

| Field | Type | Notes |
|---|---|---|
| `work_item_id` | uuid, PK | |
| `tenant_id` | uuid, FK, not null | **Immutable** |
| `session_id` | uuid, unique, not null | 1:1 with session. **No FK** — see below |
| `requested_by_oid` | uuid, not null | **Immutable** |
| `case_reference` | text, null | **Immutable once set** |
| `governed_action` | text, null | Catalogue id. **Immutable once set** |
| `target` | jsonb, null | **Immutable once set** |
| `state` | enum, not null | see below |
| `approval_state` | enum, not null | `none`, `pending`, `approved`, `rejected`, `expired` |
| `expires_at` | timestamptz, null | Set on authorization; execution validity window |
| `claimed_at` | timestamptz, null | Set by the atomic claim |
| `claimed_by` | text, null | Executing principal |
| `outcome` | jsonb, null | Result plus verification outcome |
| `created_at`, `updated_at` | timestamptz | |

**`session_id` carries no foreign key, and that is a decision.** The work item follows *audit*
retention — seven years — while its session follows *chat* retention at ninety days from the
terminal state. A foreign key forces them to share one window: `RESTRICT` makes the ninety-day
sweep impossible, and `CASCADE` or `SET NULL` destroys the authority record or its identity along
with the conversation. Expiring a conversation MUST NOT take the record of what was authorized in
it (spec FR-AUDIT-004). The `unique` constraint still enforces the 1:1. This is the same reasoning
as `audit_event.work_item_id`, and the same conclusion: a reference that can cascade is a reference
that can delete the evidence. Found by `tests/retention/test_retention_classes.py`, which could not
delete an expired session while the work item referenced it.

**Immutability is enforced at the database permission boundary** — a trigger or column-level grant, not
application convention (constitution Principle III, spec FR-EXEC-008). The six immutable fields above are
the authority fields.

**States**: `open → awaiting_decision → authorized → claimed → executed | failed`, plus terminal
`expired`, `cancelled`, `escalated`.

**Rules**
- Expiry (`now >= expires_at`) makes the item non-executable. This is not an error (spec FR-EXEC-001).
- The claim is atomic — a conditional update on `claimed_at IS NULL`. This is idempotency boundary 1.
- A failed execution does **not** re-fire; it requires fresh authorization (spec FR-EXEC-006).
- Cancellation is permitted before claim; after claim, execution completes and records normally.

---

## Operation

A proposed or executed action within a session.

| Field | Type | Notes |
|---|---|---|
| `operation_id` | uuid, PK | |
| `work_item_id` | uuid, FK, not null | |
| `tenant_id` | uuid, not null | |
| `catalogue_id` | text, not null | References a governance record |
| `catalogue_version` | int, not null | Bound at proposal time |
| `treatment` | enum, not null | `AUTO`, `END_USER_APPROVAL`, `STAFF_APPROVAL`, `NOT_ALLOWED` |
| `parameters` | jsonb, not null | |
| `idempotency_key` | text, unique, null | Idempotency boundary 2 — carried to the external system |
| `status` | enum, not null | `proposed`, `gated`, `authorized`, `executed`, `failed`, `refused` |
| `verification` | enum, null | `server_confirmed`, `client_attested`, `contradicted` |
| `created_at`, `executed_at` | timestamptz | |

**Rules**: `treatment` is written by deterministic governance only — never by model output
(spec FR-AGENT-004). A `client_attested` outcome must not be presented as confirmed
resolution (spec FR-AGENT-008, ADR-0004).

---

## Governance record — the operation catalogue

| Field | Type | Notes |
|---|---|---|
| `catalogue_id` | text, PK | |
| `version` | int, PK | Composite key with `catalogue_id` |
| `kind` | enum, not null | `read`, `action` |
| `default_treatment` | enum, not null | |
| `accepted_roles` | text[], not null | Evaluated by **set intersection**. Order is meaningless |
| `is_reference_fixture` | bool, not null | True for the four scaffold fixtures |
| `requires_elevation` | bool, not null | **Must be false** — Alpha permits no elevation (ADR-0004) |
| `risk_tier` | enum, not null | Non-destructive tiers only in the scaffold |
| `commands` | jsonb, null | Disclosed in full in the approval payload |
| `content_hash` | text, null | Binds what was approved to what executes |
| `verification_tool` | text, null | Null means the outcome can only be `client_attested` |

**Rules**
- A capability is callable only when registered here **and** entitled to the organisation. Discovery
  never confers entitlement (spec FR-EXT-014, constitution Principle III).
- `is_reference_fixture = true` entries are inert, are excluded from production configuration, and are
  never counted as UC-01..UC-12 (spec FR-SCOPE-007).
- A `check` constraint enforces `requires_elevation = false`.

---

## Tenant entitlement

Which organisation may use which capability. There is no global toolset.

| Field | Type | Notes |
|---|---|---|
| `tenant_id` | uuid, FK, PK | |
| `catalogue_id` | text, PK | |
| `enabled` | bool, not null | |
| `credential_reference` | text, null | Key Vault reference — **never a secret value** |

---

## Approval

| Field | Type | Notes |
|---|---|---|
| `approval_id` | uuid, PK | |
| `work_item_id` | uuid, FK, unique, not null | **At most one approval per case** |
| `tenant_id` | uuid, not null | |
| `requested_at` | timestamptz, not null | |
| `decided_at` | timestamptz, null | |
| `decided_by_oid` | uuid, null | Staff identity |
| `decided_by_roles` | text[], null | Role set held at decision time |
| `verdict` | enum, null | `approved`, `rejected` |
| `expires_at` | timestamptz, null | `decided_at` + 15 minutes |

**Rules**: the first valid verdict wins; later verdicts are recorded but do not change the outcome
(spec FR-INTR-010). Only a holder of `technician` may decide. There is no system-generated verdict and no
approval by timeout (spec FR-INTR-008).

---

## Consent

| Field | Type | Notes |
|---|---|---|
| `consent_id` | uuid, PK | |
| `work_item_id` | uuid, FK, not null | |
| `tenant_id` | uuid, not null | |
| `consented_by_oid` | uuid, not null | Must equal the work item's `requested_by_oid` |
| `decided_at` | timestamptz, not null | |
| `verdict` | enum, not null | `granted`, `refused` |

**Rules**: consent is an explicit authenticated action, never inferred from chat text (spec FR-SESS-011).
It never satisfies a `STAFF_APPROVAL` requirement (spec FR-INTR-007).

---

## Audit event

| Field | Type | Notes |
|---|---|---|
| `audit_id` | uuid, PK | |
| `tenant_id` | uuid, not null | |
| `occurred_at` | timestamptz, not null | |
| `action` | text, not null | |
| `requested_by_oid` | uuid, null | The actor chain — |
| `approved_by_oid` | uuid, null | — who asked, who approved, |
| `executed_by` | text, not null | — and who actually did it |
| `execution_method` | enum, not null | `workload`, `desktop_script`, `none` |
| `outcome` | text, not null | |
| `verification` | enum, null | `server_confirmed`, `client_attested`, `contradicted` |
| `correlation_id` | text, not null | |
| `retain_until` | timestamptz, not null | `occurred_at` + 7 years by default |

**Rules**: append-only — no update, no delete before `retain_until`. Audit retention is independent of
chat retention; expiring chat content must not remove the audit record (spec FR-AUDIT-004). Denials,
expiries and escalations are recorded as durably as permissions (spec FR-AUDIT-003). Credentials never
appear here — only stable principal identifiers and non-secret references.

---

## Graph checkpoint

Owned by the checkpointer in the `langgraph` schema. Listed for completeness, **not** modelled by
Alembic.

**Rules**: working state, never an authority record. The graph reads authority from the work item and
cannot rewrite it — this is the structural reason a misbehaving agent cannot retarget approved work.
Retained 30 days after the owning work completes, then pruned by a job we own (ADR-0003). No foreign
key crosses into `platform`.

---

## Outbox message

Makes an asynchronous message as durable as the state change that produced it (research R-017).

| Field | Type | Notes |
|---|---|---|
| `outbox_id` | uuid, PK | |
| `tenant_id` | uuid, not null | |
| `occurred_at` | timestamptz, not null | |
| `kind` | text, not null | Trigger kind |
| `payload` | jsonb, not null | **Opaque identifiers and correlation only** — never authority-bearing |
| `dispatched_at` | timestamptz, null | Null until published |
| `attempts` | int, not null, default 0 | |
| `version` | int, not null | Optimistic concurrency |

**Rules**: the row commits in the **same transaction** as the state change it describes. A dispatcher
worker publishes afterwards and sets `dispatched_at`. Publication is at-least-once by construction, so
every consumer is idempotent. The payload is subject to the trigger contract: no tenant, requester,
role, action, target or approval state.

---

## Idempotency record

| Field | Type | Notes |
|---|---|---|
| `idempotency_key` | text, PK | Deterministic, derived from the operation |
| `tenant_id` | uuid, not null | |
| `operation_id` | uuid, FK, not null | |
| `outcome` | jsonb, null | The original result, replayed on a repeat |
| `created_at` | timestamptz, not null | |

**Rules**: a repeated request with the same key returns the original outcome rather than acting again.
This is idempotency boundary 2 — it protects the **external** system. Boundary 1 remains the atomic
claim on the work item, which protects the platform. Both are required; neither substitutes for the
other.

**No `version` column — the one named exemption from optimistic concurrency** (see §Conventions).
The row is inserted once and updated exactly once, when `outcome` is written. The primary key
serialises concurrent writers, so there is no second writer for a version column to detect.

---

## Ingestion run

The twelfth bounded context (§32.12), realised as a RagCore worker — research R-021.

| Field | Type | Notes |
|---|---|---|
| `run_id` | uuid, PK | |
| `tenant_id` | uuid, not null | Every ingested record is tenant-stamped |
| `source` | text, not null | Knowledge source |
| `watermark` | text, null | Resume point for incremental acquisition |
| `document_count` | int, not null, default 0 | |
| `state` | enum, not null | `running`, `completed`, `failed` |
| `started_at`, `completed_at` | timestamptz | |
| `version` | int, not null | |

**Rules**: runs are **idempotent** — re-running from a watermark MUST NOT duplicate documents. The
retrieval index is derived, so a lost index is rebuilt by re-running ingestion rather than restored.
Ingestion never writes authority.

---

## Entity relationships

```text
tenant_mapping 1─────* chat_session 1─────1 work_item
                 │         │                    │
                 │         └──* message 1──0..1 feedback
                 │                              │
                 │                              ├──* operation ──* (catalogue_id, version) governance_record
                 │                              ├──0..1 approval
                 │                              └──* consent
                 ├──* tenant_entitlement *───── governance_record
                 └──* audit_event

outbox_message      ─ ─ ─ published by the dispatcher worker; no FK to work_item
idempotency_record 1─────1 operation
ingestion_run       ─ ─ ─ independent; feeds the derived retrieval index

langgraph.* (checkpoints) ─ ─ ─ joined by identifier in application code only, no FK
```

## Retention summary

| Class | Default | Overridable per organisation |
|---|---|---|
| Chat content — sessions, messages, feedback | 90 days **from terminal state** | Yes |
| Derived reporting aggregates | Independent of the above | Yes |
| Audit events | 7 years | Yes |
| Graph checkpoints | 30 days after completion | Yes |
| Work items, operations, approvals, consent | Follow audit | Yes |

A missing override never means unbounded retention — the platform default applies (spec FR-SESS-008).
