"""audit_event: append-only, retained independently of what it describes.

Revision ID: 0013_audit_event
Revises: 0012_consent

``work_item_id`` is deliberately not a foreign key: audit outlives the rows it describes by
years, and a reference that could cascade is a reference that could delete the evidence.
The append-only grant is applied in the grants revision.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_audit_event"
down_revision: str | None = "0012_consent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "audit_event"

CREATE_TABLE = """\
CREATE TABLE platform.audit_event (
    audit_id UUID NOT NULL,
    work_item_id UUID,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    action VARCHAR(128) NOT NULL,
    requested_by_oid UUID,
    approved_by_oid UUID,
    executed_by VARCHAR(256) NOT NULL,
    execution_method platform.execution_method NOT NULL,
    outcome VARCHAR(256) NOT NULL,
    verification platform.verification_outcome,
    correlation_id VARCHAR(128) NOT NULL,
    retain_until TIMESTAMP WITH TIME ZONE NOT NULL,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_audit_event PRIMARY KEY (audit_id)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_audit_event_retain_until ON platform.audit_event (retain_until)",
    "CREATE INDEX ix_audit_event_tenant_id_occurred_at ON platform.audit_event (tenant_id, occurred_at DESC)",
    "CREATE INDEX ix_audit_event_tenant_id_work_item_id ON platform.audit_event (tenant_id, work_item_id) WHERE work_item_id IS NOT NULL",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
