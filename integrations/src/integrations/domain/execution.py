"""Execution domain types. **What was attempted, and separately what is known.**

Pure model: no I/O, no framework, no provider type.

**Two facts, two fields, and keeping them apart is the whole design.** "The call returned 200" and
"the effect happened" are different, and a system that stores one field for both will report the
first as the second on the day they differ — which is the day it matters.

`FR-AGENT-008` names the three things the platform may conclude, and this service reports the
observation while **RagCore draws the conclusion** (`FR-INTEG-009`). A service that both acted and
judged its own success would be relabelling an attestation as a confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping

__all__ = ["ExecutionOutcome", "ExecutionRecord", "VerificationOutcome"]


class ExecutionOutcome(Enum):
    """What happened to the attempt.

    The four refusals are distinct rather than one denial because **each needs a different operator
    action**, and an operator told only "refused" learns nothing about whether to entitle an
    organisation, register a capability, publish a newer version or fix a system.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    """The connector was reached and the call did not succeed. The far side's fault or ours."""

    REFUSED_UNENTITLED = "refused_unentitled"
    REFUSED_UNREGISTERED = "refused_unregistered"
    REFUSED_VERSION = "refused_version"
    REFUSED_WINDOW = "refused_window"
    """Authority expired, was cancelled, or the organisation is no longer active."""

    UNREACHABLE = "unreachable"
    """Entitled, but the system could not be reached. **Distinct from not entitled**
    (`FR-EXT-022`), and neither is presented to a user as a failure of their request."""

    @property
    def is_refusal(self) -> bool:
        """Whether nothing was attempted externally.

        A refusal means the platform's own rules said no **before** any call, so there is no
        external effect to reconcile and nothing that could be server-confirmed.
        """
        return self in {
            ExecutionOutcome.REFUSED_UNENTITLED,
            ExecutionOutcome.REFUSED_UNREGISTERED,
            ExecutionOutcome.REFUSED_VERSION,
            ExecutionOutcome.REFUSED_WINDOW,
            ExecutionOutcome.UNREACHABLE,
        }


class VerificationOutcome(Enum):
    """What the platform **knows** about the effect, as distinct from what it attempted."""

    SERVER_CONFIRMED = "server_confirmed"
    """A server-side read agreed. **The only outcome reportable to a user as resolved.**"""

    CLIENT_ATTESTED = "client_attested"
    """Nobody checked. The call said it worked. MUST NOT be presented as confirmed resolution
    (ADR-0004)."""

    CONTRADICTED = "contradicted"
    """A server-side read disagreed. Treated as failure — a claim the platform has actively
    disproved is worse than one it never checked."""


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    """One attempt against one external system. **Append-only; a retry is a second row.**

    Attributes:
        execution_id: This attempt.
        job_id: The instruction it was carrying out. The correlation back to the originating work.
        tenant_id: The organisation, recovered from the durable job record.
        connector_id: Which external system.
        catalogue_id: The capability, and `catalogue_version` the version in force.
        idempotency_key: The **derived** key this attempt carried. Unique across the table — that
            uniqueness is idempotency boundary 2.
        external_reference: The far side's own identifier, where it returned one.
        outcome: What happened.
        verification: What is known. Reported as an observation; RagCore draws the conclusion.
        normalized_result: Contract-checked provider output. **Data**, never instruction. MUST NOT
            carry credentials, tokens or another organisation's information.
        correlation_id: The journey.
    """

    job_id: UUID
    tenant_id: UUID
    connector_id: str
    catalogue_id: str
    catalogue_version: int
    idempotency_key: str
    outcome: ExecutionOutcome
    verification: VerificationOutcome
    correlation_id: str
    attempted_at: datetime
    external_reference: str | None = None
    normalized_result: Mapping[str, object] | None = None
    completed_at: datetime | None = None
    execution_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Refuse a record that claims more than it can know.

        Raises:
            ValueError: When a refusal claims `server_confirmed`. Nothing was attempted externally,
                so there was nothing to confirm — and `server_confirmed` is the single value that
                may be reported to a user as resolved. The database carries the same constraint;
                this catches it at the call site, where the message can name the caller.
        """
        if self.outcome.is_refusal and self.verification is VerificationOutcome.SERVER_CONFIRMED:
            raise ValueError(
                f"an execution refused as {self.outcome.value} cannot be server_confirmed: "
                "nothing was attempted, so there was nothing to confirm."
            )
