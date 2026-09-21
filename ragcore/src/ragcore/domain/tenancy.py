"""Tenant admission. The trusted binding between a request and an organisation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ragcore.domain.identifiers import EntraTenantId, TenantId


class TenantStatus(Enum):
    """Platform admission state for a customer organisation."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDED = "offboarded"


class TenantSource(Enum):
    """How a tenant came to be in scope.

    Recorded so the provenance of a tenant binding is visible in audit rather than inferred.
    These three are the only legitimate provenances; there is no fourth.
    """

    END_USER_IDENTITY = "end_user_identity"
    """Derived from the end user's own validated ``tid``, then admitted by the registry."""

    WORK_ITEM = "work_item"
    """Read from the durable work item a staff action or execution targets."""

    PLATFORM_OBJECT = "platform_object"
    """Read from the durable platform object a staff action operates on."""


@dataclass(frozen=True, slots=True)
class TenantContext:
    """The trusted tenant binding for one unit of work.

    **Tenant context MUST NEVER be accepted from an untrusted client field** (A1
    §4.5). Construct through the ``from_*`` classmethods, each of which names its
    provenance — there is deliberately no ``from_request``, no ``from_header`` and no
    ``parse``. If a caller holds a tenant identifier that came from a client and wants a
    context for it, this API gives them nowhere to go. That is the intended outcome.
    """

    tenant_id: TenantId
    entra_tenant_id: EntraTenantId
    status: TenantStatus
    source: TenantSource

    @property
    def is_admitted(self) -> bool:
        """Whether work may execute for this organisation.

        Approved work MUST NOT execute if the target organisation is no longer active
        (spec FR-EXEC-003). Checked at execution rather than only at admission, because a
        suspension can land between the two.
        """
        return self.status is TenantStatus.ACTIVE

    @classmethod
    def from_admitted_identity(
        cls, tenant_id: TenantId, entra_tenant_id: EntraTenantId, status: TenantStatus
    ) -> TenantContext:
        """Admit an end user against registry state resolved from their own validated ``tid``."""
        return cls(tenant_id, entra_tenant_id, status, TenantSource.END_USER_IDENTITY)

    @classmethod
    def from_work_item(
        cls, tenant_id: TenantId, entra_tenant_id: EntraTenantId, status: TenantStatus
    ) -> TenantContext:
        """Bind the tenant of a durable work item, for Workload execution and resume.

        The Workload never carries customer-tenant authority of its own; the tenant comes from
        the work item.
        """
        return cls(tenant_id, entra_tenant_id, status, TenantSource.WORK_ITEM)

    @classmethod
    def from_platform_object(
        cls, tenant_id: TenantId, entra_tenant_id: EntraTenantId, status: TenantStatus
    ) -> TenantContext:
        """Bind the tenant of the platform object a staff action targets.

        A staff token's ``tid`` is the Operator tenant and is **never** the customer target.
        """
        return cls(tenant_id, entra_tenant_id, status, TenantSource.PLATFORM_OBJECT)
