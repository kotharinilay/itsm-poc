"""feedback: revisable, and never an input to a decision.

Revision ID: 0006_feedback
Revises: 0005_session_step

The unique constraint on ``(message_id, given_by_oid)`` is the whole of 'only the current
signal counts' (spec FR-SESS-010): a revision updates rather than inserting a second row.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_feedback"
down_revision: str | None = "0005_session_step"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "feedback"

CREATE_TABLE = """\
CREATE TABLE platform.feedback (
    feedback_id UUID NOT NULL,
    message_id UUID NOT NULL,
    session_id UUID NOT NULL,
    given_by_oid UUID NOT NULL,
    signal platform.feedback_signal NOT NULL,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_feedback PRIMARY KEY (feedback_id),
    CONSTRAINT uq_feedback_message_id_given_by_oid UNIQUE (message_id, given_by_oid),
    CONSTRAINT fk_feedback_message_id FOREIGN KEY(message_id) REFERENCES platform.message (message_id) ON DELETE CASCADE,
    CONSTRAINT fk_feedback_session_id FOREIGN KEY(session_id) REFERENCES platform.chat_session (session_id) ON DELETE CASCADE
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_feedback_tenant_id_session_id ON platform.feedback (tenant_id, session_id)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
