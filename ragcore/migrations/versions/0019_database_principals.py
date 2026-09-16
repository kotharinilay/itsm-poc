"""Three database principals, with three disjoint sets of rights.

Revision ID: 0019_database_principals
Revises: 0018_published_views

**This is where schema ownership stops being a convention** (ADR-0003, ``contracts/read-views.md``).

========================= ==========================================================
Principal                 Rights
========================= ==========================================================
``synthia_migrator``      DDL. Owns the schema. The gated job runs as this and
                          nothing else ever does.
``synthia_ragcore``       ``SELECT``, ``INSERT``, ``UPDATE``, ``DELETE`` on tables —
                          **except** ``audit_event``, which is insert-and-read only.
                          No DDL, so a process that tried to migrate at startup
                          fails rather than succeeding at the wrong moment.
``synthia_monolith``      ``SELECT`` on the published views. **No table access at
                          all**, so a query that reached past the read contract
                          fails at the database rather than working until somebody
                          notices.
========================= ==========================================================

**Append-only audit is a grant, not a rule.** ``synthia_ragcore`` holds ``INSERT`` and ``SELECT``
on ``audit_event`` and neither ``UPDATE`` nor ``DELETE``. A record cannot be amended or removed
before ``retain_until`` because the principal writing it has no statement that could.

**Retention and erasure need ``DELETE``**, and they have it on every table except ``audit_event``.
That is the honest shape: expiring chat content is a hard delete (spec FR-SESS-007), erasure is a
hard delete (spec FR-AUDIT-006), and audit survives both (spec FR-AUDIT-004). Audit's own expiry
past ``retain_until`` is a separate, privileged job — it is not something the runtime may do.

**Roles are created ``NOLOGIN`` and carry no password.** Authentication is Entra managed identity;
a password in a migration would be a credential in source control, which the constitution prohibits
outright. Deployment grants the managed identity membership of the role it needs.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019_database_principals"
down_revision: str | None = "0018_published_views"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"

MIGRATOR = "synthia_migrator"
RAGCORE = "synthia_ragcore"
MONOLITH = "synthia_monolith"

AUDIT_TABLE = "audit_event"

WRITABLE_TABLES: tuple[str, ...] = (
    "tenant_mapping",
    "chat_session",
    "message",
    "session_step",
    "feedback",
    "work_item",
    "governance_record",
    "tenant_entitlement",
    "operation",
    "approval",
    "consent",
    "outbox_message",
    "idempotency_record",
    "ingestion_run",
)
"""Every table the runtime may write. ``audit_event`` is absent, and that absence is the control."""

PUBLISHED_VIEWS: tuple[str, ...] = (
    "vw_session_summary_v1",
    "vw_session_message_v1",
    "vw_session_step_v1",
    "vw_work_item_v1",
    "vw_approval_queue_v1",
    "vw_approval_unexecuted_v1",
    "vw_audit_event_v1",
    "vw_governance_catalogue_v1",
    "vw_tenant_v1",
    "vw_message_feedback_v1",
    "vw_dashboard_rollup_v1",
)
"""Exactly what the monolith may read. Listed rather than granted by wildcard: ``ALL TABLES IN
SCHEMA`` would silently include the next table somebody adds, which is how a read contract becomes
table access without anybody deciding to allow it."""

# noqa on the two interpolations in this file: an identifier — a role name, a schema name, a
# view name — cannot be a bind parameter in PostgreSQL DDL or DCL, so there is no parameterised
# form of GRANT to prefer. Every value interpolated below is a module-level constant declared in
# this file; none reaches here from a request, a row, or the environment.
CREATE_ROLES: tuple[str, ...] = tuple(
    f"""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
            CREATE ROLE {role} NOLOGIN;
        END IF;
    END
    $$
    """  # noqa: S608 — a DCL identifier cannot be bound; see the note above
    for role in (MIGRATOR, RAGCORE, MONOLITH)
)
"""Idempotent, because roles are cluster-wide: a second database in the same cluster running these
migrations must not fail on a role the first one created."""


def upgrade() -> None:
    """Create the three roles and grant each exactly what it needs."""
    for statement in CREATE_ROLES:
        op.execute(statement)

    # The migrator holds every right on the schema. Everything below narrows from here.
    #
    # Ownership itself is not transferred here. The job already connects as the principal that
    # created these objects, and `ALTER SCHEMA ... OWNER TO` inside a revision would hand the
    # schema to a role the running session may not be a member of — turning a grant migration
    # into one that can only be run by a superuser and can never be undone.
    op.execute(f"GRANT ALL ON SCHEMA {SCHEMA} TO {MIGRATOR}")

    # USAGE on the schema is not access to anything in it; it is permission to name it.
    op.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO {RAGCORE}")
    op.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO {MONOLITH}")

    for table in WRITABLE_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {SCHEMA}.{table} TO {RAGCORE}")

    # Append-only. No UPDATE, no DELETE — the two statements that could rewrite history.
    op.execute(f"GRANT SELECT, INSERT ON {SCHEMA}.{AUDIT_TABLE} TO {RAGCORE}")

    # `outbox_message.sequence` is GENERATED ALWAYS AS IDENTITY, which is backed by a sequence the
    # inserting principal must be allowed to advance.
    op.execute(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA {SCHEMA} TO {RAGCORE}")

    for view in PUBLISHED_VIEWS:
        op.execute(f"GRANT SELECT ON {SCHEMA}.{view} TO {MONOLITH}")

    # No default privileges are configured, and that is the intended state: a table added by a
    # later revision arrives with no grants, so it is neither writable by the runtime nor readable
    # by the monolith until a revision says so in as many words.


def downgrade() -> None:
    """Revoke everything, then drop the roles.

    Revoking first is not tidiness: PostgreSQL refuses to drop a role that still owns or is granted
    anything, so a downgrade that went straight to ``DROP ROLE`` would fail.
    """
    for view in PUBLISHED_VIEWS:
        op.execute(f"REVOKE SELECT ON {SCHEMA}.{view} FROM {MONOLITH}")  # noqa: S608

    op.execute(f"REVOKE USAGE ON ALL SEQUENCES IN SCHEMA {SCHEMA} FROM {RAGCORE}")
    op.execute(f"REVOKE ALL ON {SCHEMA}.{AUDIT_TABLE} FROM {RAGCORE}")

    for table in WRITABLE_TABLES:
        op.execute(f"REVOKE ALL ON {SCHEMA}.{table} FROM {RAGCORE}")

    op.execute(f"REVOKE USAGE ON SCHEMA {SCHEMA} FROM {MONOLITH}")
    op.execute(f"REVOKE USAGE ON SCHEMA {SCHEMA} FROM {RAGCORE}")
    op.execute(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM {MIGRATOR}")

    for role in (MONOLITH, RAGCORE, MIGRATOR):
        op.execute(f"DROP ROLE IF EXISTS {role}")
