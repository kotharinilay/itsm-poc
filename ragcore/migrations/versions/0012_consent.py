"""consent: an explicit authenticated action, never inferred from chat.

Revision ID: 0012_consent
Revises: 0011_approval

A separate table from ``approval`` on purpose. A single decision table with a kind column
is one WHERE clause away from treating consent as satisfying a staff approval
(spec FR-INTR-007).

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012_consent"
down_revision: str | None = "0011_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "consent"

CREATE_TABLE = """\
CREATE TABLE platform.consent (
    consent_id UUID NOT NULL,
    work_item_id UUID NOT NULL,
    consented_by_oid UUID NOT NULL,
    decided_at TIMESTAMP WITH TIME ZONE NOT NULL,
    verdict platform.consent_verdict NOT NULL,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_consent PRIMARY KEY (consent_id),
    CONSTRAINT fk_consent_work_item_id FOREIGN KEY(work_item_id) REFERENCES platform.work_item (work_item_id)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_consent_tenant_id_work_item_id ON platform.consent (tenant_id, work_item_id)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
