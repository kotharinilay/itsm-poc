"""idempotency_record: boundary 2, and the one exemption from optimistic concurrency.

Revision ID: 0015_idempotency_record
Revises: 0014_outbox_message

**No ``version`` column.** The row is inserted once and updated exactly once; its primary
key already serialises every concurrent writer, so a version column would be a second
concurrency mechanism on a row that cannot have two live writers (data-model.md).

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015_idempotency_record"
down_revision: str | None = "0014_outbox_message"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "idempotency_record"

CREATE_TABLE = """\
CREATE TABLE platform.idempotency_record (
    idempotency_key VARCHAR(256) NOT NULL,
    operation_id UUID NOT NULL,
    outcome JSONB,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_idempotency_record PRIMARY KEY (idempotency_key),
    CONSTRAINT fk_idempotency_record_operation_id FOREIGN KEY(operation_id) REFERENCES platform.operation (operation_id)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_idempotency_record_tenant_id_operation_id ON platform.idempotency_record (tenant_id, operation_id)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
