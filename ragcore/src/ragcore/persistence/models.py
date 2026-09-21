"""Every table in the ``platform`` schema.

**RagCore owns this schema outright** (ADR-0001, ADR-0003). The .NET monolith holds ``SELECT`` on
the published ``vw_*_v1`` views and nothing else — no table access, no DDL, no migrations. The
views are in :mod:`ragcore.persistence.views`; the grants that make the separation real are in the
final migration.

**What is not here, and why.**

*Checkpoints.* ``langgraph.*`` is created and versioned by the checkpointer's own ``setup()``. No
class here maps it, no foreign key crosses into it, and Alembic excludes the schema from
autogenerate (research R-004). The work item is the authority record; a checkpoint is working
state. That separation is the structural reason a misbehaving agent cannot retarget approved work:
it can write its own working state all it likes and still cannot reach the row that authorizes.

*Case content.* ServiceNow remains the system of record for the case. This schema holds a
``case_reference`` and never a copy of the case, because two stores holding the same case is two
stores that disagree about it.

*Retrieval content.* The AI Search index is **derived**. A lost index is rebuilt by re-running
ingestion, not restored from backup, which is why ``ingestion_run`` records a watermark and no
document body.

*Memory.* The scaffold defines no agent-memory entity. ``data-model.md`` names none, and a table
invented here would be speculative capability no requirement needs (P-8), reported as though it
were real (H-1).
Durable working state is the checkpoint, and it already has an owner.

*Scripts.* Script metadata and version are not a separate table: they are ``governance_record``'s
``commands``, ``content_hash`` and ``version`` columns. A script that executed is a catalogue entry
that was approved at a version, and giving it its own table would create a second place a command
set could be defined — one of which would not be governed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ragcore.domain.governance import (
    CapabilityKind,
    ExecutionMethod,
    ExecutionTreatment,
    IntegrationJobStatus,
    IntegrationResultStatus,
    RiskTier,
    VerificationOutcome,
)
from ragcore.domain.ingestion import IngestionRunState
from ragcore.domain.tenancy import TenantStatus
from ragcore.domain.work import (
    ApprovalState,
    ApprovalVerdict,
    ConsentVerdict,
    FeedbackSignal,
    OperationStatus,
    SenderKind,
    SessionState,
    WorkItemState,
)
from ragcore.persistence import enums
from ragcore.persistence.base import (
    PLATFORM_SCHEMA,
    Attributed,
    Audited,
    Base,
    Sequenced,
    TenantScoped,
    Versioned,
    metadata,
)


def _fk(target: str) -> str:
    """Schema-qualify a foreign-key target.

    Args:
        target: ``table.column`` within the platform schema.

    Returns:
        The fully qualified reference. Written out rather than left to the metadata's default
        schema, because an unqualified reference silently resolves against ``search_path`` — and
        the migration job and the runtime do not share one.
    """
    return f"{PLATFORM_SCHEMA}.{target}"


# ---------------------------------------------------------------------------
# Tenant registry — the admission decision, and the only accepted external key
# ---------------------------------------------------------------------------


class TenantMapping(Audited, Attributed, Versioned, Base):
    """Binds a validated Entra tenant identifier to its platform representation.

    **This table is the trusted platform state a tenant binding derives from.** ``entra_tid`` is
    the only value that may be matched against a token-derived tenant (A1 §4.5),
    and a staff caller's own ``tid`` is the Operator tenant — **never** the customer target. A
    staff action resolves its target organisation by reading the durable platform object it
    operates on and taking that row's ``tenant_id``; it never reads one from the request. See
    :class:`~ragcore.domain.tenancy.TenantContext`, which gives a caller holding a client-supplied
    tenant identifier nowhere to go.

    No region column: single region by decision (spec FR-SURF-015).
    """

    __tablename__ = "tenant_mapping"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    """The platform's own identifier. Every tenant-scoped row keys on this, not on ``entra_tid``."""

    entra_tid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    """The validated ``tid``. Unique, because two platform tenants claiming one Entra tenant would
    make admission ambiguous in exactly the direction that leaks data."""

    display_name: Mapped[str] = mapped_column(String(256), nullable=False)

    status: Mapped[TenantStatus] = mapped_column(enums.TENANT_STATUS, nullable=False)
    """Work does not execute when this is not ``active`` (spec FR-EXEC-003) — checked at execution
    as well as at admission, because a suspension can land between the two."""

    retention_overrides: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    """Per-class overrides. **A missing override never means unbounded retention**: the platform
    default applies (spec FR-SESS-008), which is why this is nullable and the sweeper resolves a
    default rather than skipping a class it finds no entry for."""

    __table_args__ = (
        Index("ix_tenant_mapping_status", "status"),
        {"schema": PLATFORM_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Session context — conversation, messages, the step trail, feedback
# ---------------------------------------------------------------------------


class ChatSession(TenantScoped, Audited, Attributed, Versioned, Base):
    """One conversation. 1:1 with a work item.

    A session exists only once a genuine problem is articulated — a greeting creates nothing
    (spec FR-SESS-003), which is why there is no ``draft`` state and no row to clean up.
    """

    __tablename__ = "chat_session"

    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(_fk("tenant_mapping.tenant_id")), nullable=False
    )

    requester_oid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    """The Entra ``oid`` of the end user who owns the session."""

    state: Mapped[SessionState] = mapped_column(enums.SESSION_STATE, nullable=False)
    """One of nine. The three ``awaiting_*`` states persist indefinitely — losing the realtime
    connection changes nothing about them (spec FR-SESS-016)."""

    case_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """A reference into the system of record, set when the triage gate fires. **A reference, not a
    copy**: ServiceNow owns the case."""

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    content_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """**Null while active** (spec FR-SESS-020). Set on the transition to a terminal state, to that
    instant plus the organisation's retention window. Null means *not yet eligible*, never *keep
    forever* — the column is only ever read alongside a terminal ``state``."""

    __table_args__ = (
        Index("ix_chat_session_tenant_id_state", "tenant_id", "state"),
        Index(
            "ix_chat_session_tenant_id_requester_oid_created_at",
            "tenant_id",
            "requester_oid",
            text("created_at DESC"),
        ),
        # Partial: the retention sweeper's only query, and an index over the rows it never
        # visits would be pure write cost on the hot conversational path.
        Index(
            "ix_chat_session_content_expires_at",
            "content_expires_at",
            postgresql_where=text("content_expires_at IS NOT NULL"),
        ),
        {"schema": PLATFORM_SCHEMA},
    )


class Message(TenantScoped, Audited, Versioned, Base):
    """One turn in a conversation.

    A ``staff`` message is valid only while the session is ``staff_controlled``, and its presence
    **never confers requester authority** (spec FR-SURF-009) — which is why ``sender_kind`` has
    three members rather than an ``is_agent`` flag.

    Removed with the session's content retention. **Audit is unaffected** (spec FR-AUDIT-004):
    expiring a conversation must not remove the record of what was decided in it.
    """

    __tablename__ = "message"

    message_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(_fk("chat_session.session_id"), ondelete="CASCADE"),
        nullable=False,
    )
    """``ON DELETE CASCADE`` because retention and erasure are hard deletes: a message whose
    session is gone is orphaned content, and leaving it behind would defeat both."""

    sender_kind: Mapped[SenderKind] = mapped_column(enums.SENDER_KIND, nullable=False)

    sender_oid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    """Null for ``agent``: no principal authored it, and writing a synthetic identifier would put
    a non-existent actor into the one place actor identity is read from."""

    body: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index(
            "ix_message_tenant_id_session_id_created_at",
            "tenant_id",
            "session_id",
            "created_at",
        ),
        CheckConstraint(
            "(sender_kind = 'agent') = (sender_oid IS NULL)",
            name="agent_messages_carry_no_principal",
        ),
        {"schema": PLATFORM_SCHEMA},
    )


class SessionStep(TenantScoped, Audited, Versioned, Base):
    """One entry in the progress trail a client renders while work is in flight.

    **Present because the read contract requires it.** ``contracts/read-views.md`` publishes
    ``vw_session_step_v1`` and the monolith's ``SessionStepRow`` reads it, but ``data-model.md``
    names no table behind it. Recorded here rather than resolved by quietly dropping the view,
    which would have left a published contract with nothing underneath it.

    **Carries no authority field** — no treatment, no verdict, no target. A step says *something is
    happening*; it never says *this was allowed*. Follows chat-content retention, because a step
    trail describes a conversation and expires with it.
    """

    __tablename__ = "session_step"

    step_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(_fk("chat_session.session_id"), ondelete="CASCADE"),
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    """A machine-readable step kind, for the client to localise. Not free prose from the model."""

    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    """A short, client-safe description."""

    __table_args__ = (
        Index(
            "ix_session_step_tenant_id_session_id_created_at",
            "tenant_id",
            "session_id",
            "created_at",
        ),
        {"schema": PLATFORM_SCHEMA},
    )


class Feedback(TenantScoped, Audited, Versioned, Base):
    """A per-message thumbs signal (spec FR-SESS-009).

    **Revisable, not accumulating.** The unique constraint on ``(message_id, given_by_oid)`` is the
    mechanism: a change updates the existing row, a withdrawal deletes it, and only the current
    signal counts (spec FR-SESS-010). Without the constraint, "only the current signal counts"
    would be a rule about how callers behave.

    **MUST NOT be read by governance, retrieval or execution.** It is a quality signal and is never
    an input to a decision. Aggregate figures derived for reporting are retained independently, so
    expiring signals does not erase reporting history.
    """

    __tablename__ = "feedback"

    feedback_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    message_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(_fk("message.message_id"), ondelete="CASCADE"),
        nullable=False,
    )

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(_fk("chat_session.session_id"), ondelete="CASCADE"),
        nullable=False,
    )

    given_by_oid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    """Must be the session's own ``requester_oid``. Enforced by the repository, which reads the
    session in the same transaction — a check constraint cannot reach another table."""

    signal: Mapped[FeedbackSignal] = mapped_column(enums.FEEDBACK_SIGNAL, nullable=False)

    __table_args__ = (
        UniqueConstraint("message_id", "given_by_oid", name="uq_feedback_message_id_given_by_oid"),
        Index("ix_feedback_tenant_id_session_id", "tenant_id", "session_id"),
        {"schema": PLATFORM_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Work — the durable authority record
# ---------------------------------------------------------------------------


class WorkItem(TenantScoped, Audited, Attributed, Versioned, Base):
    """The durable authority record. Everything consequential reads authority from here.

    **Six fields are immutable**: ``tenant_id``, ``session_id``, ``requested_by_oid``,
    ``case_reference``, ``governed_action`` and ``target`` — the last three once set. Immutability
    is enforced **at the database permission boundary**, by a trigger, not by application
    convention (A1 §12.2, spec FR-EXEC-008). An application-side check protects
    only the paths that remember to call it.

    **The claim is idempotency boundary 1** — a conditional update on ``claimed_at IS NULL``, which
    is what absorbs the duplicate trigger that at-least-once delivery guarantees will arrive.
    Boundary 2 is ``idempotency_record``, which protects the external system. Both are required;
    neither substitutes for the other.

    Expiry (``now >= expires_at``) makes the item non-executable, and that is **not an error**
    (spec FR-EXEC-001). A failed execution does not re-fire; it requires fresh authorization
    (spec FR-EXEC-006).
    """

    __tablename__ = "work_item"

    work_item_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(_fk("tenant_mapping.tenant_id")), nullable=False
    )
    """**Immutable.** The Workload carries no customer-tenant authority of its own; it reads the
    tenant from this column, so a column that could change is a route to retargeting approved work
    at another organisation."""

    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    """1:1 with the session. **Immutable, and deliberately not a foreign key.**

    The work item follows *audit* retention — seven years — while its session follows *chat*
    retention at ninety days from the terminal state. A foreign key would force them to share one
    window: ``RESTRICT`` makes the ninety-day sweep impossible, and ``CASCADE`` or ``SET NULL``
    destroys the authority record or its identity along with the conversation. Either way,
    expiring a conversation would take the record of what was authorized in it
    (spec FR-AUDIT-004).

    Same reasoning as ``audit_event.work_item_id``, and the same conclusion: a reference that can
    cascade is a reference that can delete the evidence. The 1:1 guarantee survives without the
    constraint, because ``unique`` is what actually enforces it.
    """

    requested_by_oid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    """**Immutable.** Who asked. Consent is only valid from this principal."""

    case_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """**Immutable once set.** A reference into ServiceNow, which remains the case system of
    record."""

    governed_action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """**Immutable once set.** The catalogue id a human authorized."""

    target: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    """**Immutable once set.** What the action acts upon."""

    state: Mapped[WorkItemState] = mapped_column(enums.WORK_ITEM_STATE, nullable=False)

    approval_state: Mapped[ApprovalState] = mapped_column(enums.APPROVAL_STATE, nullable=False)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """Set on authorization. The execution validity window — bounded above at fifteen minutes by
    configuration that cannot be raised."""

    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(256), nullable=True)

    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    """The result, plus what verification actually established."""

    __table_args__ = (
        Index("ix_work_item_tenant_id_state", "tenant_id", "state"),
        # Partial: the expiry sweeper asks one question — which authorized items have run out of
        # time — and an index over executed and cancelled rows would answer none of it.
        Index(
            "ix_work_item_expires_at",
            "expires_at",
            postgresql_where=text("expires_at IS NOT NULL AND claimed_at IS NULL"),
        ),
        Index(
            "ix_work_item_tenant_id_claimed_at",
            "tenant_id",
            "claimed_at",
            postgresql_where=text("claimed_at IS NOT NULL"),
        ),
        CheckConstraint(
            "(claimed_at IS NULL) = (claimed_by IS NULL)",
            name="a_claim_names_its_claimant",
        ),
        {"schema": PLATFORM_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Governance — the catalogue, entitlement, and the operations bound to them
# ---------------------------------------------------------------------------


class GovernanceRecord(Audited, Attributed, Base):
    """The operation catalogue. One row per catalogue entry **per version**.

    **No optimistic-concurrency column, and this is why.** ``version`` here is half the primary
    key, not a row counter: a catalogue entry is never edited in place — a change is a new
    ``(catalogue_id, version)`` row, and the old one stays exactly as it was because an approval
    granted against it must keep meaning what it meant. Adding a second ``row_version`` would be a
    concurrency mechanism on a row that structurally cannot be updated. This is the second named
    departure from the convention in ``data-model.md`` §Conventions, alongside
    ``idempotency_record``; both are named, and neither is a precedent.

    **Not tenant-scoped.** The catalogue is platform-wide. *Entitlement* is the tenant-scoped half
    and lives in :class:`TenantEntitlement` — and a capability is callable only when registered
    here **and** entitled to the organisation. Discovery never confers entitlement
    (spec FR-EXT-014).

    **Script metadata lives here**, in ``commands``, ``content_hash`` and the key's own ``version``.
    A predefined script is a catalogue entry that was approved at a version; ``content_hash`` binds
    what was approved to what executes, so a catalogue edit between approval and execution cannot
    silently change what a human agreed to.
    """

    __tablename__ = "governance_record"

    catalogue_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Composite key with ``catalogue_id``. Bound at proposal time and carried through approval."""

    kind: Mapped[CapabilityKind] = mapped_column(enums.CAPABILITY_KIND, nullable=False)

    default_treatment: Mapped[ExecutionTreatment] = mapped_column(
        enums.EXECUTION_TREATMENT, nullable=False
    )
    """Deterministic policy reads this. **Model output never writes it** (spec FR-AGENT-004)."""

    accepted_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    """Evaluated by **set intersection**; order is meaningless. An empty array denies everyone,
    which is the correct default for an entry whose roles nobody has declared yet."""

    is_reference_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False)
    """True for the four reference fixtures. They are inert, are excluded from production
    configuration, and **MUST NEVER** be counted as or allowed to become a real defined capability
    (`.claude/rules/10-principles.md` H-2)."""

    requires_elevation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    """**Constrained to false by the database.** Alpha permits no elevation (ADR-0004), and a
    CHECK constraint is what makes that a property of the store rather than of the loader."""

    risk_tier: Mapped[RiskTier] = mapped_column(enums.RISK_TIER, nullable=False)

    commands: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    """Disclosed **in full** in the approval payload. An approver who cannot see the command set
    is not approving the command set."""

    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """Binds what was approved to what executes."""

    verification_tool: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """Null means the outcome can only be ``client_attested`` — a claim, not a confirmed
    resolution, and it MUST NOT be presented as one (spec FR-AGENT-008)."""

    __table_args__ = (
        CheckConstraint("requires_elevation = false", name="alpha_permits_no_elevation"),
        CheckConstraint("version >= 1", name="catalogue_versions_start_at_one"),
        Index("ix_governance_record_is_reference_fixture", "is_reference_fixture"),
        {"schema": PLATFORM_SCHEMA},
    )


class TenantEntitlement(TenantScoped, Audited, Attributed, Versioned, Base):
    """Which organisation may use which capability. **There is no global toolset.**

    Keyed on ``catalogue_id`` without a version: an organisation is entitled to a *capability*, and
    binding entitlement to a version would mean every catalogue edit silently revoked it.
    """

    __tablename__ = "tenant_entitlement"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(_fk("tenant_mapping.tenant_id"), ondelete="CASCADE"),
        primary_key=True,
    )

    catalogue_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    """Defaults to ``false``. A row that appeared without a decision denies rather than permits."""

    credential_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    """A Key Vault reference — **never a secret value**, and never exposed by a published view
    (spec FR-EXT-016, ``contracts/read-views.md`` rule 2)."""

    __table_args__ = (
        Index(
            "ix_tenant_entitlement_tenant_id_catalogue_id",
            "tenant_id",
            "catalogue_id",
            postgresql_where=text("enabled"),
        ),
        {"schema": PLATFORM_SCHEMA},
    )


class Operation(TenantScoped, Audited, Attributed, Versioned, Base):
    """A proposed or executed action within a session."""

    __tablename__ = "operation"

    operation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    work_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(_fk("work_item.work_item_id")), nullable=False
    )

    catalogue_id: Mapped[str] = mapped_column(String(128), nullable=False)
    catalogue_version: Mapped[int] = mapped_column(Integer, nullable=False)
    """Bound at proposal time. The composite foreign key below is what stops a catalogue row being
    deleted out from under an operation that references it."""

    treatment: Mapped[ExecutionTreatment] = mapped_column(enums.EXECUTION_TREATMENT, nullable=False)
    """**Written by deterministic governance only — never by model output** (spec FR-AGENT-004)."""

    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True)
    """Idempotency boundary 2 — carried to the external system. Nullable because an operation that
    never reached execution never needed one, and unique because two operations sharing a key would
    make the replay ambiguous in the direction that acts twice."""

    status: Mapped[OperationStatus] = mapped_column(enums.OPERATION_STATUS, nullable=False)

    verification: Mapped[VerificationOutcome | None] = mapped_column(
        enums.VERIFICATION_OUTCOME, nullable=True
    )
    """Null until execution records one. ``client_attested`` MUST NOT be presented as confirmed
    resolution (spec FR-AGENT-008, ADR-0004)."""

    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["catalogue_id", "catalogue_version"],
            [_fk("governance_record.catalogue_id"), _fk("governance_record.version")],
            name="fk_operation_catalogue_id_catalogue_version",
        ),
        Index("ix_operation_tenant_id_work_item_id", "tenant_id", "work_item_id"),
        Index("ix_operation_tenant_id_status", "tenant_id", "status"),
        {"schema": PLATFORM_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Human decisions — approval and consent, which are not interchangeable
# ---------------------------------------------------------------------------


class Approval(TenantScoped, Audited, Attributed, Versioned, Base):
    """A staff verdict on a consequential operation.

    **At most one approval per case**, enforced by the unique constraint on ``work_item_id``. That
    constraint is the whole of "first valid verdict wins" (spec FR-INTR-010): a second decider
    loses the insert rather than overwriting a decision, so the outcome is settled by the database
    rather than by whichever request happened to commit last.

    **There is no system-generated verdict and no approval by timeout** (spec FR-INTR-008).
    ``verdict`` holds two members and neither of them is ``expired``; expiry is a property of the
    work item, not a decision anyone made.
    """

    __tablename__ = "approval"

    approval_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    work_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(_fk("work_item.work_item_id")),
        nullable=False,
        unique=True,
    )

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    decided_by_oid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    """The deciding staff identity. Only a holder of ``technician`` may decide."""

    decided_by_roles: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    """The role set held **at decision time**, captured rather than re-derived. A role removed
    afterwards must not retroactively change what the record says was authorized."""

    verdict: Mapped[ApprovalVerdict | None] = mapped_column(enums.APPROVAL_VERDICT, nullable=True)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """``decided_at`` plus fifteen minutes."""

    __table_args__ = (
        # Partial: the staff approval queue is exactly the undecided rows, and it is read far more
        # often than the decided history it would otherwise scan past.
        Index(
            "ix_approval_tenant_id_requested_at",
            "tenant_id",
            "requested_at",
            postgresql_where=text("decided_at IS NULL"),
        ),
        Index(
            "ix_approval_tenant_id_decided_at",
            "tenant_id",
            "decided_at",
            postgresql_where=text("decided_at IS NOT NULL"),
        ),
        CheckConstraint(
            "(decided_at IS NULL) = (verdict IS NULL) "
            "AND (decided_at IS NULL) = (decided_by_oid IS NULL)",
            name="a_decision_names_its_decider_and_verdict",
        ),
        {"schema": PLATFORM_SCHEMA},
    )


class Consent(TenantScoped, Audited, Versioned, Base):
    """An end user's agreement to an operation on their own account or device.

    **Never satisfies a ``STAFF_APPROVAL`` requirement** (spec FR-INTR-007). The two live in
    separate tables for that reason: a single ``decision`` table with a ``kind`` column is one
    ``WHERE`` clause away from treating them as interchangeable.

    Consent is an explicit authenticated action and is **never inferred from chat text**
    (spec FR-SESS-011). An affirmative message produces no row here.
    """

    __tablename__ = "consent"

    consent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    work_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(_fk("work_item.work_item_id")), nullable=False
    )

    consented_by_oid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    """Must equal the work item's ``requested_by_oid``. Checked by the repository against the
    durable row, in the same transaction — not against anything the request asserted."""

    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    verdict: Mapped[ConsentVerdict] = mapped_column(enums.CONSENT_VERDICT, nullable=False)

    __table_args__ = (
        Index("ix_consent_tenant_id_work_item_id", "tenant_id", "work_item_id"),
        {"schema": PLATFORM_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Audit — append-only, and retained independently of everything it describes
# ---------------------------------------------------------------------------


class AuditEvent(TenantScoped, Audited, Versioned, Base):
    """A durable business or security record. **Append-only.**

    No update and no delete before ``retain_until``, enforced by grant rather than by convention:
    the runtime principal holds ``INSERT`` and ``SELECT`` on this table and nothing else.

    **Retention is independent of chat retention.** Expiring a conversation must not remove the
    record of what was decided in it (spec FR-AUDIT-004) — which is why ``work_item_id`` is a plain
    column with no foreign key, and why nothing cascades into this table.

    **Denials, expiries and escalations are recorded as durably as permissions**
    (spec FR-AUDIT-003). Credentials never appear here — only stable principal identifiers and
    non-secret references.
    """

    __tablename__ = "audit_event"

    audit_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    work_item_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    """The case this concerns, where it concerns one. **Deliberately not a foreign key**: audit
    outlives the rows it describes by years, and a reference that could cascade is a reference that
    could delete the evidence."""

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    action: Mapped[str] = mapped_column(String(128), nullable=False)

    requested_by_oid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    """The actor chain — who asked,"""

    approved_by_oid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    """— who approved,"""

    executed_by: Mapped[str] = mapped_column(String(256), nullable=False)
    """— and who actually did it. Not nullable: every event has an executing principal, even when
    it is the platform refusing something."""

    execution_method: Mapped[ExecutionMethod] = mapped_column(
        enums.EXECUTION_METHOD, nullable=False
    )

    outcome: Mapped[str] = mapped_column(String(256), nullable=False)

    verification: Mapped[VerificationOutcome | None] = mapped_column(
        enums.VERIFICATION_OUTCOME, nullable=True
    )

    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    """Ties this record to its request and its traces. Bounded, because an unbounded value that
    reaches a log sink is a log-injection vector."""

    retain_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """``occurred_at`` plus seven years by default, overridable per organisation."""

    __table_args__ = (
        Index("ix_audit_event_tenant_id_occurred_at", "tenant_id", text("occurred_at DESC")),
        Index(
            "ix_audit_event_tenant_id_work_item_id",
            "tenant_id",
            "work_item_id",
            postgresql_where=text("work_item_id IS NOT NULL"),
        ),
        Index("ix_audit_event_retain_until", "retain_until"),
        {"schema": PLATFORM_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Messaging and execution boundaries
# ---------------------------------------------------------------------------


class OutboxMessage(TenantScoped, Sequenced, Audited, Versioned, Base):
    """The transactional outbox (research R-017).

    **The row commits in the same transaction as the state change it describes.** Two separate
    writes, however close together, are the bug this prevents: a crash between them either loses a
    trigger or fires one for a change that rolled back.

    Publication is at-least-once by construction, so **every consumer is idempotent** — the work
    item's atomic claim is what absorbs the duplicate.

    **The payload carries opaque identifiers and correlation only.** No tenant, requester, role,
    action, target or approval state (``contracts/triggers.md``). A consumer reads authority from
    the durable record, not from the message that woke it, which is why a forged or replayed
    trigger cannot authorize anything.
    """

    __tablename__ = "outbox_message"

    outbox_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    kind: Mapped[str] = mapped_column(String(128), nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """Null until published."""

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    """Past the configured ceiling the row is surfaced to a human rather than retried forever."""

    __table_args__ = (
        # Partial, and the only index the dispatcher needs: it asks for undispatched rows in
        # sequence order and never looks at the published ones again.
        Index(
            "ix_outbox_message_sequence",
            "sequence",
            postgresql_where=text("dispatched_at IS NULL"),
        ),
        {"schema": PLATFORM_SCHEMA},
    )


class IdempotencyRecord(TenantScoped, Audited, Base):
    """Idempotency boundary 2 — protecting the **external** system.

    A repeated request with the same key returns the original outcome rather than acting again.
    Boundary 1 remains the atomic claim on the work item, which protects the platform. Both are
    required; neither substitutes for the other.

    **No ``version`` column — the one named exemption from optimistic concurrency**
    (``data-model.md`` §Conventions). The row is inserted once, at claim time, and updated exactly
    once, when ``outcome`` is written. Its primary key already serialises every concurrent writer,
    so a version column would be a second concurrency mechanism on a row that structurally cannot
    have two live writers. ``tests/concurrency/test_optimistic.py`` asserts both halves: that this
    table has no ``version``, and that every other one does.
    """

    __tablename__ = "idempotency_record"

    idempotency_key: Mapped[str] = mapped_column(String(256), primary_key=True)
    """Deterministic, derived from the operation. Not random: a key that differed between a request
    and its retry would make the record answer a question nobody asked."""

    operation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(_fk("operation.operation_id")), nullable=False
    )

    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    """The original result, replayed on a repeat. Null between claim and completion — which is the
    window a repeat must wait on rather than act in."""

    __table_args__ = (
        Index("ix_idempotency_record_tenant_id_operation_id", "tenant_id", "operation_id"),
        {"schema": PLATFORM_SCHEMA},
    )


# ---------------------------------------------------------------------------
# The Integrations Service seam (ADR-0007)
# ---------------------------------------------------------------------------


class IntegrationJob(TenantScoped, Audited, Attributed, Versioned, Base):
    """The durable instruction handed to the Integrations Service.

    **This is what lets the Service Bus command stay opaque** (spec §21.6.5, `FR-INTEG-014`).
    RagCore writes the capability, its version and its parameters here in the same transaction as
    the state change; the message carries only ``job_id``, correlation context and a routing kind.

    ```text
    The message causes work to happen.
    The durable job record provides the instruction, the authority and the tenant context.
    ```

    **It lives in ``platform`` rather than in ``integration`` because RagCore owns it**, and the
    Integrations Service reaches it through a **column-scoped grant**: ``SELECT`` on the row, and
    ``UPDATE`` on the four ``result_*`` columns and nothing else (revision ``0022``). It cannot
    alter ``catalogue_id``, ``catalogue_version``, ``parameters`` or ``tenant_id`` — a service able
    to rewrite its own instruction could execute an operation other than the one governance
    authorized, which is a hard failure (`.claude/rules/80-security-ops.md` §80.3). The refusal
    comes from PostgreSQL, not from
    application restraint.

    **The four result columns are how RagCore learns the outcome without reading the other
    service's schema.** It holds no grant on ``integration``, and these columns exist so it needs
    none: the coupling between the two stays one directed edge plus a queue, rather than a shared
    table.
    """

    __tablename__ = "integration_job"

    job_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    work_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        # CASCADE for the same reason the session tables use it: erasure is a **hard delete**
        # (spec FR-AUDIT-006), and an instruction left behind after the work item it belonged to
        # was erased is one organisation's data surviving a deletion that reported success.
        ForeignKey(_fk("work_item.work_item_id"), ondelete="CASCADE"),
        nullable=False,
    )
    operation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    """The operation within the work item. Part of the derived idempotency key, because one work
    item may carry more than one operation and a key without it would make two distinct actions
    look like retries of each other."""

    catalogue_id: Mapped[str] = mapped_column(String(128), nullable=False)
    catalogue_version: Mapped[int] = mapped_column(Integer, nullable=False)
    """Bound at selection, so the far side can refuse a mismatch rather than silently running
    whatever is current. An approval bound a version."""

    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    """The arguments, as **data**. The destination comes from the connector registry and never from
    here (spec `FR-EXT-018`)."""

    status: Mapped[IntegrationJobStatus] = mapped_column(
        enums.INTEGRATION_JOB_STATUS, nullable=False, server_default="created"
    )

    result_status: Mapped[IntegrationResultStatus | None] = mapped_column(
        enums.INTEGRATION_RESULT_STATUS, nullable=True
    )
    result_verification: Mapped[VerificationOutcome | None] = mapped_column(
        enums.VERIFICATION_OUTCOME, nullable=True
    )
    """What the Integrations Service **observed**. RagCore draws the conclusion: a
    ``client_attested`` outcome MUST NOT be presented to a user as confirmed resolution
    (ADR-0004)."""

    result_execution_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    result_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """The execution window, from the authority record. Expiry is a normal outcome and produces no
    execution (spec §29.5)."""

    __table_args__ = (
        Index("ix_integration_job_work_item_id", "work_item_id"),
        Index("ix_integration_job_tenant_id", "tenant_id"),
        Index(
            "ix_integration_job_in_flight",
            "expires_at",
            postgresql_where=text("status IN ('created', 'dispatched')"),
        ),
        CheckConstraint(
            "(result_status IS NULL AND result_recorded_at IS NULL) "
            "OR (result_status IS NOT NULL AND result_recorded_at IS NOT NULL)",
            name="ck_integration_job_result_is_whole",
        ),
        CheckConstraint("catalogue_version >= 1", name="ck_integration_job_version_starts_at_one"),
        {"schema": PLATFORM_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Ingestion — the twelfth bounded context
# ---------------------------------------------------------------------------


class IngestionRun(TenantScoped, Audited, Versioned, Base):
    """One incremental acquisition pass (research R-021).

    **Runs are idempotent**: re-running from a watermark MUST NOT duplicate documents. The
    retrieval index is *derived*, so a lost index is rebuilt by re-running ingestion rather than
    restored — which is the reason this table records a watermark and no document body.

    **Ingestion never writes authority.** Nothing here references a work item, and nothing here can.
    """

    __tablename__ = "ingestion_run"

    run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(_fk("tenant_mapping.tenant_id"), ondelete="CASCADE"),
        nullable=False,
    )
    """Every ingested record is tenant-stamped, and so is the run that produced it."""

    source: Mapped[str] = mapped_column(String(256), nullable=False)

    watermark: Mapped[str | None] = mapped_column(String(512), nullable=True)
    """The resume point. Null on a first run, and null is *start from the beginning* rather than
    *nothing to do*."""

    document_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    state: Mapped[IngestionRunState] = mapped_column(enums.INGESTION_RUN_STATE, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_ingestion_run_tenant_id_source_started_at",
            "tenant_id",
            "source",
            text("started_at DESC"),
        ),
        {"schema": PLATFORM_SCHEMA},
    )


TENANT_SCOPED_TABLES: Final[tuple[str, ...]] = (
    "tenant_mapping",
    "chat_session",
    "message",
    "session_step",
    "feedback",
    "work_item",
    "tenant_entitlement",
    "operation",
    "approval",
    "consent",
    "audit_event",
    "outbox_message",
    "idempotency_record",
    "ingestion_run",
)
"""Every table carrying ``tenant_id``.

Enumerated so ``tests/isolation/`` can assert the property table-by-table and name the one that
regressed. ``governance_record`` is the only table absent, and it is absent because the catalogue
is platform-wide — entitlement, which is the tenant-scoped half, has its own row above.
"""


def _table(name: str) -> Table:
    """Resolve a mapped table by name, as a :class:`~sqlalchemy.Table`.

    ``Model.__table__`` is typed ``FromClause``, which is true of a mapper in general and untrue of
    every class in this module. Resolving through the metadata gives the precise type, so the
    repositories can be strictly typed without a cast at each call site — and a typo in a name
    fails here, at import, rather than at the first query that uses it.
    """
    return metadata.tables[f"{PLATFORM_SCHEMA}.{name}"]


TENANT_MAPPING: Final[Table] = _table("tenant_mapping")
CHAT_SESSION: Final[Table] = _table("chat_session")
MESSAGE: Final[Table] = _table("message")
SESSION_STEP: Final[Table] = _table("session_step")
FEEDBACK: Final[Table] = _table("feedback")
WORK_ITEM: Final[Table] = _table("work_item")
GOVERNANCE_RECORD: Final[Table] = _table("governance_record")
TENANT_ENTITLEMENT: Final[Table] = _table("tenant_entitlement")
OPERATION: Final[Table] = _table("operation")
APPROVAL: Final[Table] = _table("approval")
CONSENT: Final[Table] = _table("consent")
AUDIT_EVENT: Final[Table] = _table("audit_event")
OUTBOX_MESSAGE: Final[Table] = _table("outbox_message")
IDEMPOTENCY_RECORD: Final[Table] = _table("idempotency_record")
INTEGRATION_JOB: Final[Table] = _table("integration_job")
INGESTION_RUN: Final[Table] = _table("ingestion_run")

TABLES_BY_NAME: Final[dict[str, Table]] = {table.name: table for table in metadata.sorted_tables}
"""Every table, keyed by unqualified name.

Exists for the two callers that work over a *list* of tables rather than one — erasure and the
isolation tests. Built from the metadata rather than hand-written, so a table added above cannot be
missed by an erasure that iterates this, which is exactly the omission that would leave one
organisation's rows behind after a deletion reported success.
"""
