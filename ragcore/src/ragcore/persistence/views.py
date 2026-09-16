"""The eleven published ``vw_*_v1`` views — the read contract, and the only coupling point.

**Names are the contract; shapes are defined here** (``contracts/read-views.md``). The .NET
monolith holds ``SELECT`` on these views and on nothing else: no table access, no DDL, no
migrations. Its ``PublishedViews`` constants and its row classes are the other half of this file,
and a column renamed here is a runtime failure there — which is the intended cost of the
published-view contract (ADR-0001).

**A view is never altered in place.** A change adds ``_v2`` alongside, the monolith migrates when
it is ready, and ``_v1`` is dropped a release later once unreferenced. The version number carries
the coordination, so neither team blocks the other and no sign-off gate exists.

**Four rules bind every view below.**

1. ``tenant_id`` is present, so the monolith's global query filter has a column to apply and no
   unfiltered path exists. The single exception is ``vw_governance_catalogue_v1`` — see its own
   note, which states why and what carries the tenant dimension instead.
2. **No credential material, ever.** Not values, not Key Vault references. ``tenant_entitlement``
   is consequently not published at all: it carries ``credential_reference``, and a view over it
   would be one ``SELECT *`` away from publishing the column.
3. **Retention is respected inside the view**, not by the caller. Expired chat content cannot be
   read back through a listing after its window passes, because the view itself excludes it.
4. **Enums are published as ``text``**, never as the native PostgreSQL type. The monolith reads
   them through a ``ValueConverter<TEnum, string>``, and an unrecognised value must throw at the
   read rather than arrive as a default. Casting at this boundary keeps the native type — and its
   protection against a value nobody defined — on the write side.

Soft delete is excluded by construction rather than by a predicate: no scaffold table declares
``deleted_at`` (``data-model.md`` §Conventions), so there is nothing for these views to filter.
The first table to adopt the convention adds the predicate here at the same time.
"""

from __future__ import annotations

from typing import Final

from alembic_utils.pg_view import PGView

from ragcore.persistence.base import PLATFORM_SCHEMA

SESSION_SUMMARY_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_session_summary_v1",
    definition="""
    SELECT
        s.session_id,
        s.tenant_id,
        s.requester_oid,
        s.state::text AS state,
        s.case_reference,
        s.created_at,
        s.updated_at,
        s.closed_at
    FROM platform.chat_session AS s
    WHERE s.content_expires_at IS NULL OR s.content_expires_at > now()
    """,
)
"""Customer and staff session listings.

The retention predicate reads ``IS NULL OR > now()`` rather than ``> now()``: ``content_expires_at``
is **null while the session is active** (spec FR-SESS-020), so the shorter form would have hidden
every live conversation.
"""

SESSION_MESSAGE_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_session_message_v1",
    definition="""
    SELECT
        m.message_id,
        m.session_id,
        m.tenant_id,
        m.sender_kind::text AS sender_kind,
        m.sender_oid,
        m.body,
        m.created_at
    FROM platform.message AS m
    JOIN platform.chat_session AS s
      ON s.session_id = m.session_id
     AND s.tenant_id = m.tenant_id
    WHERE s.content_expires_at IS NULL OR s.content_expires_at > now()
    """,
)
"""Conversation history, excluding any row past its content-retention window.

The join carries ``tenant_id`` as well as ``session_id``. Redundant given the foreign key, and kept
anyway: it makes the tenant filter local to both sides of the join, so the view cannot be widened
by a future edit that changes what the join is on.
"""

SESSION_STEP_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_session_step_v1",
    definition="""
    SELECT
        p.step_id,
        p.session_id,
        p.tenant_id,
        p.kind,
        p.summary,
        p.created_at
    FROM platform.session_step AS p
    JOIN platform.chat_session AS s
      ON s.session_id = p.session_id
     AND s.tenant_id = p.tenant_id
    WHERE s.content_expires_at IS NULL OR s.content_expires_at > now()
    """,
)
"""The step trail. **Progress entries only; carries no authority field.**

No treatment, no verdict, no target. A step says something is happening; it never says something
was allowed.
"""

WORK_ITEM_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_work_item_v1",
    definition="""
    SELECT
        w.work_item_id,
        w.tenant_id,
        w.session_id,
        w.requested_by_oid,
        w.case_reference,
        w.governed_action,
        w.state::text AS state,
        w.approval_state::text AS approval_state,
        w.expires_at,
        w.claimed_at,
        w.claimed_by,
        w.created_at,
        w.updated_at,
        w.version
    FROM platform.work_item AS w
    """,
)
"""Work state, with authority fields exposed **read-only**.

``target`` is absent. The monolith renders and searches work; it does not need the parameter
document, and the smallest published surface is the one hardest to widen by accident.

No retention predicate: work items follow *audit* retention, not chat retention, so a work item
outlives the conversation that produced it (``data-model.md`` §Retention summary).
"""

APPROVAL_QUEUE_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_approval_queue_v1",
    definition="""
    SELECT
        a.approval_id,
        a.work_item_id,
        a.tenant_id,
        op.catalogue_id,
        op.catalogue_version,
        g.commands::text AS disclosed_commands,
        a.requested_at,
        a.expires_at,
        a.created_at,
        a.updated_at,
        a.version
    FROM platform.approval AS a
    JOIN LATERAL (
        SELECT o.catalogue_id, o.catalogue_version
        FROM platform.operation AS o
        WHERE o.work_item_id = a.work_item_id
          AND o.tenant_id = a.tenant_id
        ORDER BY o.created_at DESC
        LIMIT 1
    ) AS op ON true
    LEFT JOIN platform.governance_record AS g
      ON g.catalogue_id = op.catalogue_id
     AND g.version = op.catalogue_version
    WHERE a.decided_at IS NULL
    """,
)
"""Pending approvals, **with the fully disclosed command set**.

``disclosed_commands`` is the catalogue entry's ``commands`` at the version the operation bound at
proposal time — not at the current version. That is the point of a composite catalogue key: an
approver sees what they are approving, and a catalogue edit between approval and execution cannot
silently change it.

The lateral join takes the most recent operation on the case. One case carries at most one
approval, so this resolves to one row per approval; the ``ORDER BY`` is what makes it deterministic
rather than incidental.
"""

APPROVAL_UNEXECUTED_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_approval_unexecuted_v1",
    definition="""
    SELECT
        a.approval_id,
        a.work_item_id,
        a.tenant_id,
        op.catalogue_id,
        a.decided_at,
        a.decided_by_oid,
        a.expires_at,
        a.version
    FROM platform.approval AS a
    JOIN platform.work_item AS w
      ON w.work_item_id = a.work_item_id
     AND w.tenant_id = a.tenant_id
    JOIN LATERAL (
        SELECT o.catalogue_id
        FROM platform.operation AS o
        WHERE o.work_item_id = a.work_item_id
          AND o.tenant_id = a.tenant_id
        ORDER BY o.created_at DESC
        LIMIT 1
    ) AS op ON true
    WHERE a.verdict = 'approved'
      AND a.decided_at IS NOT NULL
      AND w.state <> 'executed'
    """,
)
"""Approved but never executed — **the dead-letter surface ADR-0002 requires**.

An approval that a human granted and that nothing ever acted on is a silent failure: the requester
believes it happened, and nothing in an ordinary listing says otherwise. This view is what makes
that state visible, which is why it is a published contract rather than an operational query.
"""

AUDIT_EVENT_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_audit_event_v1",
    definition="""
    SELECT
        e.audit_id,
        e.tenant_id,
        e.occurred_at,
        e.work_item_id,
        e.action,
        e.requested_by_oid,
        e.approved_by_oid,
        e.executed_by,
        e.execution_method::text AS execution_method,
        e.outcome,
        e.verification::text AS verification,
        e.correlation_id,
        e.retain_until
    FROM platform.audit_event AS e
    WHERE e.retain_until > now()
    """,
)
"""Audit search. **Never exposes credential references.**

Retention here is audit retention — seven years by default — and is entirely independent of chat
retention. Expiring a conversation leaves every one of these rows intact (spec FR-AUDIT-004), which
is the property ``tests/retention/test_retention_classes.py`` exists to hold.
"""

GOVERNANCE_CATALOGUE_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_governance_catalogue_v1",
    definition="""
    SELECT
        g.catalogue_id,
        g.version,
        g.kind::text AS kind,
        g.default_treatment::text AS default_treatment,
        g.accepted_roles,
        g.is_reference_fixture,
        g.requires_elevation,
        g.risk_tier::text AS risk_tier,
        g.verification_tool
    FROM platform.governance_record AS g
    """,
)
"""Catalogue browsing, carrying the reference-fixture label so fixtures are **visibly** labelled.

**The one view without ``tenant_id``, and the reason is structural.** The catalogue is
platform-wide: an entry is not owned by an organisation, so there is no tenant value to publish and
a cross join against the registry would multiply every entry by every customer. The tenant-scoped
half of this concern is *entitlement*, and ``tenant_entitlement`` is deliberately not published at
all because it carries ``credential_reference`` (rule 2 beats rule 1 where they meet).

``contracts/read-views.md`` rule 1 says ``tenant_id`` is on every view. Recorded here as a known
divergence rather than resolved by publishing a column with nothing meaningful in it, and matched
by the monolith's ``GovernanceCatalogueRow``, which declares itself not tenant-scoped for the same
reason.
"""

TENANT_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_tenant_v1",
    definition="""
    SELECT
        t.tenant_id,
        t.entra_tid,
        t.display_name,
        t.status::text AS status,
        t.created_at,
        t.updated_at,
        t.version
    FROM platform.tenant_mapping AS t
    """,
)
"""The organisation registry. **Status and identifiers, no secret material.**

``retention_overrides`` is absent: it is operational configuration the sweeper reads, not something
a listing needs, and every column not published is a column that cannot leak.

The registry is itself tenant-scoped — an organisation row belongs to that organisation — so the
monolith's global filter applies here unchanged and a staff caller narrows within it rather than
widening past it.
"""

MESSAGE_FEEDBACK_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_message_feedback_v1",
    definition="""
    SELECT
        f.message_id,
        f.session_id,
        f.tenant_id,
        f.signal::text AS signal,
        f.updated_at
    FROM platform.feedback AS f
    JOIN platform.chat_session AS s
      ON s.session_id = f.session_id
     AND s.tenant_id = f.tenant_id
    WHERE s.content_expires_at IS NULL OR s.content_expires_at > now()
    """,
)
"""Feedback on a session's messages. **Current signal only.**

Revised signals replace rather than accumulate, which is a property of the unique constraint on
``(message_id, given_by_oid)`` rather than of this view — so there is no ``DISTINCT ON`` here and
no window function picking a latest row. There is only ever one.
"""

DASHBOARD_ROLLUP_V1: Final = PGView(
    schema=PLATFORM_SCHEMA,
    signature="vw_dashboard_rollup_v1",
    definition="""
    WITH windows AS (
        SELECT DISTINCT
            tenant_id,
            date_trunc('day', created_at) AS window_start
        FROM platform.chat_session
        UNION
        SELECT DISTINCT
            tenant_id,
            date_trunc('day', requested_at) AS window_start
        FROM platform.approval
    ),
    bounded AS (
        SELECT
            tenant_id,
            window_start,
            window_start + interval '1 day' AS window_end
        FROM windows
    )
    SELECT
        b.tenant_id,
        b.window_start,
        b.window_end,
        (
            SELECT count(*)
            FROM platform.chat_session AS s
            WHERE s.tenant_id = b.tenant_id
              AND s.created_at >= b.window_start
              AND s.created_at < b.window_end
        ) AS session_count,
        (
            SELECT count(*)
            FROM platform.approval AS a
            WHERE a.tenant_id = b.tenant_id
              AND a.decided_at >= b.window_start
              AND a.decided_at < b.window_end
        ) AS approval_count,
        (
            SELECT count(*)
            FROM platform.approval AS a
            JOIN platform.work_item AS w
              ON w.work_item_id = a.work_item_id
             AND w.tenant_id = a.tenant_id
            WHERE a.tenant_id = b.tenant_id
              AND a.verdict = 'approved'
              AND a.decided_at >= b.window_start
              AND a.decided_at < b.window_end
              AND w.state <> 'executed'
        ) AS unexecuted_approval_count,
        COALESCE(
            (
                SELECT count(f.feedback_id)::double precision
                     / NULLIF(count(*), 0)::double precision
                FROM platform.message AS m
                LEFT JOIN platform.feedback AS f
                  ON f.message_id = m.message_id
                 AND f.tenant_id = m.tenant_id
                WHERE m.tenant_id = b.tenant_id
                  AND m.sender_kind = 'agent'
                  AND m.created_at >= b.window_start
                  AND m.created_at < b.window_end
            ),
            0.0
        ) AS feedback_rate
    FROM bounded AS b
    """,
)
"""Pre-aggregated platform counts, per organisation per day.

**Tenant-stamped, and the aggregate-leakage rule is a property of what this publishes** rather than
of how it is queried: every window is scoped to one ``tenant_id``, so there is no total for a
caller to subtract their own figures from.

``feedback_rate`` is the share of *agent* messages carrying a signal. Derived here and retained
independently of the signals it was computed from, so expiring feedback at ninety days does not
erase reporting history (spec FR-SESS-012).
"""

ALL_VIEWS: Final[tuple[PGView, ...]] = (
    SESSION_SUMMARY_V1,
    SESSION_MESSAGE_V1,
    SESSION_STEP_V1,
    WORK_ITEM_V1,
    APPROVAL_QUEUE_V1,
    APPROVAL_UNEXECUTED_V1,
    AUDIT_EVENT_V1,
    GOVERNANCE_CATALOGUE_V1,
    TENANT_V1,
    MESSAGE_FEEDBACK_V1,
    DASHBOARD_ROLLUP_V1,
)
"""Every published view, in dependency order.

The migration creates them in this order and drops them in reverse. Ordered rather than sorted:
PostgreSQL records a dependency when one view selects from another, and although none does today,
an alphabetical list would make the first one that did fail on downgrade rather than on review.
"""
