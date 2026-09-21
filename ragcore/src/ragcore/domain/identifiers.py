"""Domain identifiers.

Every value that carries business meaning gets its own type rather than travelling as a bare
``str`` or ``UUID`` (.claude/rules/10-principles.md P-20). The point is not ceremony: a
``WorkItemId`` and a
``SessionId`` are both UUIDs, they are 1:1 with each other, and passing one where the other belongs
is a mistake that type-checks perfectly if both are ``UUID``.

This module imports nothing outside the standard library, like everything under ``domain/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EntraTenantId:
    """The Entra tenant identifier (``tid``) of a validated human token."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class PrincipalId:
    """The Entra object identifier (``oid``) of the acting user or workload principal."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class TenantId:
    """The platform's own identifier for a customer organisation.

    Distinct from :class:`EntraTenantId` on purpose. The Entra ``tid`` is what a token carries;
    this is what platform state is keyed by. Only the tenant registry maps one to the other, and
    that mapping is the admission decision.
    """

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class CorrelationId:
    """Originates at the public edge, propagates through every tier.

    Appears on every log record, trace, notification, trigger and audit record, so one user
    request can be followed across an asynchronous, suspendable flow (spec FR-OPS-001).
    """

    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class WorkItemId:
    """The durable authority record for a chat session."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class SessionId:
    """One conversation between an end user and the platform. Opaque to clients."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class OperationId:
    """A single proposed or executed action within a session."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ApprovalId:
    """A staff member's recorded decision authorising a consequential operation."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ConsentId:
    """An end user's recorded agreement to an operation on their own account or device."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class IntegrationJobId:
    """One written instruction to the Integrations Service (ADR-0007).

    **An opaque platform identifier of the same class as a work identifier.** It names a durable
    row; it carries no organisation, actor, capability or authority, and it grants nothing on its
    own. That is precisely what lets the command message carry it and nothing else: the consumer
    reads its instruction from the row this names, never from the message that delivered it.

    Distinct from :class:`WorkItemId` as a **type**, not merely by convention. Both wrap a ``UUID``,
    and a command carrying a work identifier where a job identifier belongs would deserialise
    perfectly and then name the wrong row. A separate type makes that swap a type error at the call
    site rather than a lookup failure in a worker.
    """

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class AuditEventId:
    """A durable business or security record, distinct from telemetry."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class MessageId:
    """A single turn in a conversation."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class OperationIdentity:
    """A catalogue entry bound to the version in force when it was proposed.

    The version is part of the identity because an approval binds the operation version it was
    granted against. A catalogue edit between approval and execution must not silently change what
    a human authorised.
    """

    catalogue_id: str
    version: int

    def __str__(self) -> str:
        return f"{self.catalogue_id}@{self.version}"


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """A deterministic key that makes an external effect happen at most once.

    Idempotency boundary 2, protecting the **external** system. Boundary 1 is the atomic claim on
    the work item, which protects the platform. Both are required; neither substitutes for the
    other.
    """

    value: str

    def __str__(self) -> str:
        return self.value


CORRELATION_ID_MAX_LENGTH: Final = 128
"""Upper bound on an accepted correlation identifier.

A correlation identifier is diagnostic data, never authority — but it reaches log sinks and audit
records, so an unbounded value is a log-injection vector.
"""
