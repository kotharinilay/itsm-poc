# Read-View Contract

The only coupling point between the two deployables, and the one no architecture test can catch. It is
therefore governed explicitly.

## Ownership

| Side | Rights |
|---|---|
| RagCore | Owns every table and every view. Owns every migration (Alembic) |
| .NET monolith | `SELECT` on published views only. No table access, no DDL, no migrations |

`Database.Migrate()`, `EnsureCreated()` and EF Core migration files are prohibited in the monolith and
an architecture test enforces their absence.

## Versioning rule

**A view is never altered in place.**

```text
vw_session_summary_v1     <- monolith reads this today
vw_session_summary_v2     <- RagCore adds alongside; monolith migrates when ready
                             v1 dropped a release later, once unreferenced
```

This is expand/contract applied to the read contract. The version number carries the coordination, so
no sign-off gate exists and neither team blocks the other. A CI check asserts that no published view is
altered in place and that any dropped view is unreferenced by the monolith.

## Published views

Names are the contract; shapes are defined by the owning migration.

| View | Serves | Notes |
|---|---|---|
| `vw_session_summary_v1` | Customer and staff session listings | Includes `tenant_id`, state, timestamps, case reference |
| `vw_session_message_v1` | Conversation history | Excludes any row past its content-retention window |
| `vw_session_step_v1` | Step trail | Progress entries only; carries no authority fields |
| `vw_work_item_v1` | Work state | Authority fields exposed read-only |
| `vw_approval_queue_v1` | Pending approvals | Includes the fully disclosed command set |
| `vw_approval_unexecuted_v1` | Approved but never executed | The dead-letter surface required by ADR-0002 |
| `vw_audit_event_v1` | Audit search | Never exposes credential references |
| `vw_governance_catalogue_v1` | Catalogue browsing | Carries `is_reference_fixture` so fixtures are visibly labelled |
| `vw_tenant_v1` | Organisation registry | Status and identifiers, no secret material |
| `vw_message_feedback_v1` | Feedback on a session's messages | Current signal only; revised signals replace rather than accumulate |
| `vw_dashboard_rollup_v1` | Platform dashboard | Pre-aggregated counts, including feedback rate. Derived and retained independently of the signals it was computed from |

## Rules binding every view

1. **`tenant_id` is present on every view.** The monolith applies it on every query; there is no
   unfiltered path. Enforced by tenant-isolation tests.
2. **No credential material, ever** — not values, not Key Vault references.
3. **No authority is writable.** The views are read-only by grant, not merely by convention.
4. **Retention is respected inside the view**, so expired chat content cannot be read back through a
   listing after it has passed its window.
5. A view exposing another organisation's row is a release-blocking defect, not a bug.

## Consequence accepted

The monolith cannot change the shape it reads without a RagCore-side migration. This is the intended
cost of the published-view contract (ADR-0001), and it is what keeps the two deployables free of an
application dependency.
