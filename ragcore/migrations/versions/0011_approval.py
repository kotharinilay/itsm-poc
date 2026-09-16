"""approval: at most one per case, first valid verdict wins.

Revision ID: 0011_approval
Revises: 0010_operation

The unique constraint on ``work_item_id`` is the entire mechanism (spec FR-INTR-010): a
second decider loses the insert rather than overwriting a decision, so the outcome is
settled by the database rather than by whichever request committed last.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011_approval"
down_revision: str | None = "0010_operation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "approval"

CREATE_TABLE = """\
CREATE TABLE platform.approval (
    approval_id UUID NOT NULL,
    work_item_id UUID NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL,
    decided_at TIMESTAMP WITH TIME ZONE,
    decided_by_oid UUID,
    decided_by_roles TEXT[],
    verdict platform.approval_verdict,
    expires_at TIMESTAMP WITH TIME ZONE,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_approval PRIMARY KEY (approval_id),
    CONSTRAINT ck_approval_a_decision_names_its_decider_and_verdict CHECK ((decided_at IS NULL) = (verdict IS NULL) AND (decided_at IS NULL) = (decided_by_oid IS NULL)),
    CONSTRAINT uq_approval_work_item_id UNIQUE (work_item_id),
    CONSTRAINT fk_approval_work_item_id FOREIGN KEY(work_item_id) REFERENCES platform.work_item (work_item_id)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_approval_tenant_id_decided_at ON platform.approval (tenant_id, decided_at) WHERE decided_at IS NOT NULL",
    "CREATE INDEX ix_approval_tenant_id_requested_at ON platform.approval (tenant_id, requested_at) WHERE decided_at IS NULL",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
