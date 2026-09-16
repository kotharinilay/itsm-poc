"""operation: proposals and executions, bound to a catalogue version.

Revision ID: 0010_operation
Revises: 0009_tenant_entitlement

The composite foreign key to ``(catalogue_id, version)`` is what stops a catalogue row
being deleted out from under an operation that references it.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_operation"
down_revision: str | None = "0009_tenant_entitlement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "operation"

CREATE_TABLE = """\
CREATE TABLE platform.operation (
    operation_id UUID NOT NULL,
    work_item_id UUID NOT NULL,
    catalogue_id VARCHAR(128) NOT NULL,
    catalogue_version INTEGER NOT NULL,
    treatment platform.execution_treatment NOT NULL,
    parameters JSONB NOT NULL,
    idempotency_key VARCHAR(256),
    status platform.operation_status NOT NULL,
    verification platform.verification_outcome,
    executed_at TIMESTAMP WITH TIME ZONE,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_operation PRIMARY KEY (operation_id),
    CONSTRAINT fk_operation_catalogue_id_catalogue_version FOREIGN KEY(catalogue_id, catalogue_version) REFERENCES platform.governance_record (catalogue_id, version),
    CONSTRAINT fk_operation_work_item_id FOREIGN KEY(work_item_id) REFERENCES platform.work_item (work_item_id),
    CONSTRAINT uq_operation_idempotency_key UNIQUE (idempotency_key)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_operation_tenant_id_status ON platform.operation (tenant_id, status)",
    "CREATE INDEX ix_operation_tenant_id_work_item_id ON platform.operation (tenant_id, work_item_id)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
