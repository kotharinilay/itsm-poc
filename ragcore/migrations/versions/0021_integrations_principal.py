"""The Integrations Service's read contract and its database principal.

Revision ID: 0021_integrations_principal
Revises: 0020_integration_schema

**A fourth principal, with a fourth disjoint set of rights** (extending revision ``0019``):

========================== =========================================================
Principal                  Rights
========================== =========================================================
``synthia_integrations``   ``SELECT``, ``INSERT``, ``UPDATE``, ``DELETE`` on the
                           ``integration`` schema, which it owns.
                           ``SELECT`` on **two** published views and nothing else in
                           ``platform``. **No base-table access at all**, so a query
                           that reached past the read contract fails at the database
                           rather than working until somebody notices.
========================== =========================================================

**It holds no write grant anywhere in `platform`.** The one write it will ever have there is
column-scoped to the result fields of ``integration_job``, added by the revision that creates that
table. Until then the shape is simply: it writes its own schema and reads two views.

**Why it cannot see the other nine views.** Not tidiness — least privilege with a specific threat in
mind. ``vw_session_message_v1`` carries conversation content and ``vw_audit_event_v1`` carries the
actor chain; the Integrations Service needs neither, and a component holding connector credentials
is the last one that should also be able to read every customer's transcripts. The grant loop below
iterates ``INTEGRATION_READ_VIEWS``, not ``ALL_VIEWS``, and the two are separate tuples in
:mod:`ragcore.persistence.views` for exactly this reason.

**Conversely the monolith is not granted `vw_connector_credential_ref_v1`.** That view exists
because the access check and the credential lookup are different questions; the monolith asks
neither.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ragcore.persistence.views import INTEGRATION_READ_VIEWS

revision: str = "0021_integrations_principal"
down_revision: str | None = "0020_integration_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLATFORM_SCHEMA = "platform"
INTEGRATION_SCHEMA = "integration"
INTEGRATIONS = "synthia_integrations"

INTEGRATION_TABLES: tuple[str, ...] = ("connector", "connector_binding")


def upgrade() -> None:
    """Create the views, the principal, and its grants."""
    for view in INTEGRATION_READ_VIEWS:
        op.create_entity(view)

    # The role is created here if absent so a fresh environment is self-contained, and its password
    # is never set here: the principal authenticates as a managed identity, so there is no password
    # to set and nothing in this file that could hold one.
    # S608 is suppressed for the same reason revision 0019 suppresses it: a DCL identifier — a role
    # name, a schema, a table — CANNOT be a bound parameter in PostgreSQL. Every interpolated value
    # here is a module-level constant in this file, not input, so there is nothing a caller could
    # influence.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{INTEGRATIONS}') THEN
                CREATE ROLE {INTEGRATIONS} NOLOGIN;
            END IF;
        END
        $$
        """  # noqa: S608 — a DCL identifier cannot be bound; every value is a constant above
    )

    # USAGE on both schemas. Without it on `platform`, even a granted view is unreachable — and the
    # error names the schema rather than the view, which sends the reader to the wrong place.
    op.execute(f"GRANT USAGE ON SCHEMA {PLATFORM_SCHEMA} TO {INTEGRATIONS}")
    op.execute(f"GRANT USAGE ON SCHEMA {INTEGRATION_SCHEMA} TO {INTEGRATIONS}")

    # Its own schema: full DML, no DDL. A process that tried to migrate at startup fails rather
    # than succeeding at the wrong moment — the migration job is the only DDL path (ADR-0003).
    for table in INTEGRATION_TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE "
            f"ON {INTEGRATION_SCHEMA}.{table} TO {INTEGRATIONS}"
        )

    # TWO views in `platform`, and nothing else. Not ALL_VIEWS.
    for view in INTEGRATION_READ_VIEWS:
        op.execute(f"GRANT SELECT ON {PLATFORM_SCHEMA}.{view.signature} TO {INTEGRATIONS}")


def downgrade() -> None:
    """Revoke, then drop the views. The role itself is left in place.

    A role may own objects in another database or be referenced by a managed-identity mapping this
    revision cannot see, so dropping it is not this migration's decision to make. Revoking is.
    """
    for view in INTEGRATION_READ_VIEWS:
        op.execute(f"REVOKE SELECT ON {PLATFORM_SCHEMA}.{view.signature} FROM {INTEGRATIONS}")  # noqa: S608

    for table in INTEGRATION_TABLES:
        op.execute(
            f"REVOKE SELECT, INSERT, UPDATE, DELETE "
            f"ON {INTEGRATION_SCHEMA}.{table} FROM {INTEGRATIONS}"
        )

    op.execute(f"REVOKE USAGE ON SCHEMA {INTEGRATION_SCHEMA} FROM {INTEGRATIONS}")
    op.execute(f"REVOKE USAGE ON SCHEMA {PLATFORM_SCHEMA} FROM {INTEGRATIONS}")

    for view in reversed(INTEGRATION_READ_VIEWS):
        op.drop_entity(view)
