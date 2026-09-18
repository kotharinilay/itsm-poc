"""Execution records and the Integrations Service's own outbox.

Revision ID: 0023_integration_execution
Revises: 0022_integration_job

Two tables in the `integration` schema, and one uniqueness constraint that **is** a platform
guarantee rather than merely supporting one.

**`execution_record.idempotency_key` is UNIQUE, and that uniqueness IS idempotency boundary 2**
(spec §29.4). The key is *derived* — a deterministic function of organisation, work item and
operation — never random, so a redelivered command derives the same key, loses the insert, and no
second external effect occurs. The database is the arbiter, not a check-then-act in application code
that two replicas can both pass.

**The two boundaries live in different deployables now, and both remain required.** The atomic claim
on the work item stays with the authority record in RagCore; this key protects the far side. Neither
substitutes for the other: the claim stops two executors starting, the key stops one executor's
retry landing twice.

**Append-only.** An attempt is never rewritten; a second attempt is a second row. A table that
updated in place could not answer "what did we actually try", which is the question an execution
record exists for.

**Its own outbox** (constitution §Idempotency and messaging). A result row becomes durable in the
same transaction as the execution record, and a dispatcher publishes it afterwards. Without that, a
crash between "the external effect happened" and "we told RagCore" loses the only evidence it did.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023_integration_execution"
down_revision: str | None = "0022_integration_job"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "integration"
INTEGRATIONS = "synthia_integrations"
TABLES: tuple[str, ...] = ("execution_record", "outbox_message")

CREATE_OUTCOME = """\
CREATE TYPE integration.execution_outcome AS ENUM (
    'succeeded',
    'failed',
    'refused_unentitled',
    'refused_unregistered',
    'refused_version',
    'refused_window',
    'unreachable'
)"""

CREATE_EXECUTION_RECORD = """\
CREATE TABLE integration.execution_record (
    execution_id UUID NOT NULL,
    job_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    connector_id VARCHAR(64) NOT NULL,
    catalogue_id VARCHAR(128) NOT NULL,
    catalogue_version INTEGER NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    external_reference VARCHAR(256),
    outcome integration.execution_outcome NOT NULL,
    verification platform.verification_outcome NOT NULL,
    normalized_result JSONB,
    correlation_id VARCHAR(128) NOT NULL,
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,

    CONSTRAINT pk_execution_record PRIMARY KEY (execution_id),

    -- IDEMPOTENCY BOUNDARY 2. Not an index for speed: this constraint is the guarantee. A
    -- redelivered command derives the same key and loses the insert, so at most one external
    -- effect occurs however many times the message arrives.
    CONSTRAINT uq_execution_record_idempotency_key UNIQUE (idempotency_key),

    CONSTRAINT ck_execution_record_version_starts_at_one CHECK (catalogue_version >= 1),

    -- A REFUSAL NEVER CLAIMS A SERVER-CONFIRMED OUTCOME. Nothing was attempted externally, so
    -- there was nothing to confirm - and `server_confirmed` is the one value that may be reported
    -- to a user as resolved (ADR-0004).
    CONSTRAINT ck_execution_record_refusal_is_not_confirmed CHECK (
        outcome NOT IN ('refused_unentitled', 'refused_unregistered', 'refused_version',
                        'refused_window', 'unreachable')
        OR verification <> 'server_confirmed'
    )
)"""

CREATE_OUTBOX = """\
CREATE TABLE integration.outbox_message (
    message_id UUID NOT NULL,
    job_id UUID NOT NULL,
    kind VARCHAR(64) NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    dispatched_at TIMESTAMP WITH TIME ZONE,
    attempts INTEGER DEFAULT 0 NOT NULL,
    undispatchable BOOLEAN DEFAULT FALSE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,

    CONSTRAINT pk_integration_outbox PRIMARY KEY (message_id),

    -- THE ROW CARRIES NO PAYLOAD, AND THAT IS THE CONTRACT (spec §27.2). A published message is
    -- jobId, correlationId and kind. There is deliberately no `body` column here: a column able to
    -- hold one is a column somebody eventually puts a tenant or a result in.
    CONSTRAINT ck_integration_outbox_attempts_bounded CHECK (attempts >= 0 AND attempts <= 10)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_execution_record_job_id ON integration.execution_record (job_id)",
    "CREATE INDEX ix_execution_record_tenant_id ON integration.execution_record (tenant_id)",
    # Partial: the dispatcher asks only for undispatched, still-dispatchable rows.
    "CREATE INDEX ix_integration_outbox_pending ON integration.outbox_message (created_at) "
    "WHERE dispatched_at IS NULL AND undispatchable IS FALSE",
)


def upgrade() -> None:
    """Create the tables, their indexes and the Integrations principal's grants."""
    op.execute(CREATE_OUTCOME)
    op.execute(CREATE_EXECUTION_RECORD)
    op.execute(CREATE_OUTBOX)
    for statement in CREATE_INDEXES:
        op.execute(statement)

    for table in TABLES:
        op.execute(  # noqa: S608 — a DCL identifier cannot be bound; every value is a constant
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {SCHEMA}.{table} TO {INTEGRATIONS}"
        )

    # NO GRANT TO synthia_ragcore, and that is deliberate rather than an omission. RagCore learns an
    # outcome from the four result columns on its own job row, which it already owns - not by
    # reading this service's internal tables. Granting it here would make the `integration` schema a
    # shared surface and give the two services a second coupling point nobody designed.


def downgrade() -> None:
    """Revoke, then drop in reverse dependency order."""
    for table in TABLES:
        op.execute(f"REVOKE ALL ON {SCHEMA}.{table} FROM {INTEGRATIONS}")  # noqa: S608

    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.outbox_message")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.execution_record")
    op.execute("DROP TYPE IF EXISTS integration.execution_outcome")
