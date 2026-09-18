"""The `integration` schema: connector registry and connector bindings.

Revision ID: 0020_integration_schema
Revises: 0019_database_principals

**One Alembic project, two schemas** (ADR-0003 as extended by ADR-0007). The Integrations Service is
a separate deployable, but it does not get a separate migration history: two histories against one
database would need an ordering discipline nothing enforces. The gated job applies both.

**Why the connector binding is here and not in `governance_record`.** A capability is described by
two different contracts that change for different reasons and are owned by different authorities:

* ``platform.governance_record`` says **whether and by whom** a capability may be used — treatment,
  accepted roles, risk tier. That is deterministic governance's decision (constitution Principle
  III), and it stays with RagCore.
* ``integration.connector_binding`` says **how** it runs — connector, endpoint, signing profile,
  idempotency policy. That is the Integrations Service's.

Neither table existed with the other's columns, so nothing is split here: the binding is greenfield.
The join is ``(catalogue_id, catalogue_version)``, which is what stops a binding silently applying
to a version nobody approved.

**The endpoint lives in the registry and nowhere else** (spec FR-EXT-018). A destination derived
from parameters, model output or retrieved content is the egress hole the whole governance model
exists to close, so the only place a URL may come from is a row here.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020_integration_schema"
down_revision: str | None = "0019_database_principals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "integration"

CREATE_SCHEMA = "CREATE SCHEMA IF NOT EXISTS integration"

CREATE_CONNECTOR_KIND = """\
CREATE TYPE integration.connector_kind AS ENUM ('native', 'mcp')"""

CREATE_IDEMPOTENCY_POLICY = """\
CREATE TYPE integration.idempotency_policy AS ENUM ('derived_key', 'none')"""

CREATE_CONNECTOR = """\
CREATE TABLE integration.connector (
    connector_id VARCHAR(64) NOT NULL,
    kind integration.connector_kind NOT NULL,
    base_endpoint VARCHAR(512) NOT NULL,
    is_reference_fixture BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_connector PRIMARY KEY (connector_id),
    -- A base endpoint is required and must be absolute. An empty or relative one would be resolved
    -- against something, and that something would be whatever the HTTP client defaulted to.
    CONSTRAINT ck_connector_endpoint_is_absolute
        CHECK (base_endpoint ~ '^https://')
)"""

CREATE_CONNECTOR_BINDING = """\
CREATE TABLE integration.connector_binding (
    catalogue_id VARCHAR(128) NOT NULL,
    catalogue_version INTEGER NOT NULL,
    connector_id VARCHAR(64) NOT NULL,
    operation_path VARCHAR(512) NOT NULL,
    signing_profile VARCHAR(512),
    idempotency_policy integration.idempotency_policy NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_connector_binding PRIMARY KEY (catalogue_id, catalogue_version),
    CONSTRAINT fk_connector_binding_connector
        FOREIGN KEY (connector_id) REFERENCES integration.connector (connector_id),
    -- The catalogue version starts at one, matching platform.governance_record. A binding for
    -- version zero would join to nothing and would be discovered only at execution.
    CONSTRAINT ck_connector_binding_version_starts_at_one CHECK (catalogue_version >= 1),
    -- A signing profile is a KEY VAULT REFERENCE, never a value. Anything that looks like inline
    -- key material is refused at the database, because a secret in a config table is a secret in
    -- every backup, every replica and every query log that touched the row.
    CONSTRAINT ck_connector_binding_signing_profile_is_a_reference
        CHECK (signing_profile IS NULL OR signing_profile !~ '(BEGIN|PRIVATE KEY|password|secret=)')
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_connector_is_reference_fixture "
    "ON integration.connector (is_reference_fixture)",
    "CREATE INDEX ix_connector_binding_connector_id "
    "ON integration.connector_binding (connector_id)",
)


def upgrade() -> None:
    """Create the schema, its enums, its tables and their indexes."""
    op.execute(CREATE_SCHEMA)
    op.execute(CREATE_CONNECTOR_KIND)
    op.execute(CREATE_IDEMPOTENCY_POLICY)
    op.execute(CREATE_CONNECTOR)
    op.execute(CREATE_CONNECTOR_BINDING)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop them in reverse dependency order.

    The schema itself is dropped only if empty: a later revision may have added a table this one
    does not know about, and taking it down with `CASCADE` would destroy data this revision never
    created.
    """
    op.execute("DROP TABLE IF EXISTS integration.connector_binding")
    op.execute("DROP TABLE IF EXISTS integration.connector")
    op.execute("DROP TYPE IF EXISTS integration.idempotency_policy")
    op.execute("DROP TYPE IF EXISTS integration.connector_kind")
    op.execute("DROP SCHEMA IF EXISTS integration RESTRICT")
