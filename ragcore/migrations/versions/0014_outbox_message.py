"""outbox_message: the transactional outbox.

Revision ID: 0014_outbox_message
Revises: 0013_audit_event

``sequence`` is GENERATED ALWAYS so no writer can choose its own publication order.
``occurred_at`` cannot carry the ordering: rows committed together share a ``now()``.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014_outbox_message"
down_revision: str | None = "0013_audit_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "outbox_message"

CREATE_TABLE = """\
CREATE TABLE platform.outbox_message (
    outbox_id UUID NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    kind VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    dispatched_at TIMESTAMP WITH TIME ZONE,
    attempts INTEGER DEFAULT 0 NOT NULL,
    tenant_id UUID NOT NULL,
    sequence BIGINT GENERATED ALWAYS AS IDENTITY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_outbox_message PRIMARY KEY (outbox_id),
    CONSTRAINT uq_outbox_message_sequence UNIQUE (sequence)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_outbox_message_sequence ON platform.outbox_message (sequence) WHERE dispatched_at IS NULL",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
