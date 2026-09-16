"""work_item: the durable authority record.

Revision ID: 0007_work_item
Revises: 0006_feedback

The partial index on ``expires_at`` serves the expiry sweeper, which asks one question —
which authorized items have run out of time — and would otherwise scan executed and
cancelled rows that answer none of it. The immutability guard is a separate revision.

**``session_id`` carries no foreign key, and that is the decision rather than an omission.** The
work item follows audit retention — seven years — while its session follows chat retention at
ninety days from the terminal state. A foreign key would force them to share one window:
``RESTRICT`` makes the ninety-day sweep impossible, and ``CASCADE`` or ``SET NULL`` destroys the
authority record or its identity along with the conversation. Expiring a conversation must not take
the record of what was authorized in it (spec FR-AUDIT-004). ``UNIQUE`` still enforces the 1:1.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_work_item"
down_revision: str | None = "0006_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "work_item"

CREATE_TABLE = """\
CREATE TABLE platform.work_item (
    work_item_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    session_id UUID NOT NULL,
    requested_by_oid UUID NOT NULL,
    case_reference VARCHAR(128),
    governed_action VARCHAR(128),
    target JSONB,
    state platform.work_item_state NOT NULL,
    approval_state platform.approval_state NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    claimed_at TIMESTAMP WITH TIME ZONE,
    claimed_by VARCHAR(256),
    outcome JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_work_item PRIMARY KEY (work_item_id),
    CONSTRAINT ck_work_item_a_claim_names_its_claimant CHECK ((claimed_at IS NULL) = (claimed_by IS NULL)),
    CONSTRAINT fk_work_item_tenant_id FOREIGN KEY(tenant_id) REFERENCES platform.tenant_mapping (tenant_id),
    CONSTRAINT uq_work_item_session_id UNIQUE (session_id)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_work_item_expires_at ON platform.work_item (expires_at) WHERE expires_at IS NOT NULL AND claimed_at IS NULL",
    "CREATE INDEX ix_work_item_tenant_id_claimed_at ON platform.work_item (tenant_id, claimed_at) WHERE claimed_at IS NOT NULL",
    "CREATE INDEX ix_work_item_tenant_id_state ON platform.work_item (tenant_id, state)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
