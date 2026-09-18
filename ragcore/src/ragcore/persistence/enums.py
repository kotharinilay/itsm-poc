"""PostgreSQL enum types, bound to the domain enums they store.

**One definition per concept, and the domain owns it.** Every type below is built from a domain
``Enum`` rather than from a list of strings, so adding a session state in
:mod:`ragcore.domain.work` and forgetting the database is a mypy error rather than a row that
fails to insert in production.

**The stored spelling is the member's value, not its Python name.** ``values_callable`` is what
makes that true, and it is not cosmetic: ``SessionState.AWAITING_USER`` is ``awaiting_user`` in
the specification, in the graph state literals, in the published views, and in the monolith's
``LowerSnakeCaseEnumConverter``. SQLAlchemy's default would have stored ``AWAITING_USER`` and
broken all four at once.

**Native types, created once, shared by every table that uses them.** ``create_type=False``
appears nowhere here; instead each type is declared with ``checkfirst`` semantics at migration
time (see ``migrations/versions/``), because two tables referencing ``verification_outcome`` must
reference the *same* PostgreSQL type — otherwise a join across them needs a cast, and a view that
casts loses the type's own protection against a value nobody defined.

**Published views expose these as ``text``, never as the native type.** The monolith reads them
through a ``ValueConverter<TEnum, string>`` and an unrecognised value must throw at the read
rather than arrive as a default. Casting at the view boundary is what keeps the native type on
the write side and a plain string on the read side.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from sqlalchemy import Enum as SAEnum

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
from ragcore.persistence.base import PLATFORM_SCHEMA


def pg_enum[E: Enum](enum_type: type[E], name: str) -> SAEnum:
    """Build the PostgreSQL enum type for a domain enum.

    Args:
        enum_type: The domain enum. Its **values** become the stored spellings.
        name: The PostgreSQL type name, in the ``platform`` schema.

    Returns:
        The SQLAlchemy type, ready to be used as a column type or referenced by a migration.
    """
    return SAEnum(
        enum_type,
        name=name,
        schema=PLATFORM_SCHEMA,
        values_callable=lambda members: [member.value for member in members],
        native_enum=True,
        create_type=True,
        validate_strings=True,
    )


TENANT_STATUS: Final = pg_enum(TenantStatus, "tenant_status")
"""Admission state. Work does not execute when this is not ``active`` (spec FR-EXEC-003)."""

SESSION_STATE: Final = pg_enum(SessionState, "session_state")
"""The nine states (spec FR-SESS-015) — **not** a four-value convenience enum."""

SENDER_KIND: Final = pg_enum(SenderKind, "sender_kind")
"""Who authored a message. ``staff`` never confers requester authority (spec FR-SURF-009)."""

FEEDBACK_SIGNAL: Final = pg_enum(FeedbackSignal, "feedback_signal")
"""A quality signal. Never read by governance, retrieval or execution."""

WORK_ITEM_STATE: Final = pg_enum(WorkItemState, "work_item_state")
"""The durable authority record's lifecycle."""

APPROVAL_STATE: Final = pg_enum(ApprovalState, "approval_state")
"""Where a work item stands against its approval requirement."""

APPROVAL_VERDICT: Final = pg_enum(ApprovalVerdict, "approval_verdict")
"""What a human decided. Two members — there is deliberately no ``expired`` to write.

The narrower type is what makes approval-by-timeout unrepresentable rather than merely prohibited
(spec FR-INTR-008). Expiry is a property of the *work item*, and lives in
:data:`APPROVAL_STATE`.
"""

CONSENT_VERDICT: Final = pg_enum(ConsentVerdict, "consent_verdict")
"""An explicit authenticated decision, never inferred from chat text (spec FR-SESS-011)."""

OPERATION_STATUS: Final = pg_enum(OperationStatus, "operation_status")
"""The lifecycle of one proposed or executed operation."""

EXECUTION_TREATMENT: Final = pg_enum(ExecutionTreatment, "execution_treatment")
"""Written by deterministic governance only — never from model output (spec FR-AGENT-004)."""

VERIFICATION_OUTCOME: Final = pg_enum(VerificationOutcome, "verification_outcome")
"""What the platform knows. ``client_attested`` is a claim, not a confirmed resolution."""

INTEGRATION_JOB_STATUS: Final = pg_enum(IntegrationJobStatus, "integration_job_status")
"""Where an instruction to the Integrations Service has got to. **Never an authority state** — the
authority lives on the work item (ADR-0007)."""

INTEGRATION_RESULT_STATUS: Final = pg_enum(IntegrationResultStatus, "integration_result_status")
"""Whether the operation ran. The detail — unentitled, unreachable — lives on the execution record
in the Integrations Service's own schema, not here."""

EXECUTION_METHOD: Final = pg_enum(ExecutionMethod, "execution_method")
"""How a consequential action was performed, or ``none`` when none was."""

CAPABILITY_KIND: Final = pg_enum(CapabilityKind, "capability_kind")
"""Whether a catalogue entry reads state or changes it."""

RISK_TIER: Final = pg_enum(RiskTier, "risk_tier")
"""Non-destructive tiers only. The destructive taxonomy is an open ADR-0004 item."""

INGESTION_RUN_STATE: Final = pg_enum(IngestionRunState, "ingestion_run_state")
"""The twelfth context's run lifecycle."""

ALL_ENUM_TYPES: Final[tuple[SAEnum, ...]] = (
    TENANT_STATUS,
    SESSION_STATE,
    SENDER_KIND,
    FEEDBACK_SIGNAL,
    WORK_ITEM_STATE,
    APPROVAL_STATE,
    APPROVAL_VERDICT,
    CONSENT_VERDICT,
    OPERATION_STATUS,
    EXECUTION_TREATMENT,
    VERIFICATION_OUTCOME,
    EXECUTION_METHOD,
    CAPABILITY_KIND,
    RISK_TIER,
    INGESTION_RUN_STATE,
)
"""Every type revision ``0001`` declares.

Enumerated so the first migration creates them in one place and the final downgrade drops them in
one place. A type left behind by an incomplete downgrade makes the next upgrade fail with
``type already exists`` — which is the failure ``test_up_down_consistency`` exists to catch.

**`INTEGRATION_JOB_STATUS` and `INTEGRATION_RESULT_STATUS` are deliberately absent**, and that is
not an oversight. They arrived with revision ``0022`` and are created and dropped there. Adding them
to this tuple would make revision ``0001`` create them, and ``0022`` would then fail on an existing
database with exactly the ``type already exists`` error this tuple exists to prevent — so a type
belongs here only if the first migration is the one that declares it.
"""
