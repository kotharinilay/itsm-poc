"""The ServiceNow connector. **The only path to the system of record.**

Spec §22, `FR-EXT-001` through `FR-EXT-007`. ServiceNow is the enterprise ITSM system of record;
this adapter owns every read and write to it, stamps the organisation on every record, and keeps
rate limits, retries, backoff and idempotency **inside** the adapter rather than in callers.

**RagCore never calls ServiceNow.** It calls this service through APIM (`FR-INTEG-012`), and this
service calls ServiceNow. That is the whole point of the boundary, and it is enforced outside this
file — by the removed connector code in RagCore, by the withdrawn Key Vault role, and by
`build/scripts/check-boundaries.sh`.

**In the scaffold this reaches the inert reference connector, not a real instance.** Spec
`FR-DEMO-014` forbids any sample flow from producing a real external effect, and the clarification
of 2026-09-18 settled that the synchronous system-of-record path runs against the same inert
fixture. The destination comes from the connector registry either way, so pointing it at a real
instance later is a configuration change rather than a code change — which is exactly the property
the registry exists to give.

**Write-backs are idempotent** (`FR-EXT-004`): a retried write MUST NOT double-post. The derived
idempotency key is carried on every state-changing call, and the adapter never invents one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from integrations.egress.http import EgressError, OutboundRequest
from integrations.execution.normalization import BoundaryValidationError, normalize_case_result

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping
    from uuid import UUID

    from integrations.credentials.resolver import TenantCredentialResolver
    from integrations.domain.catalogue import ConnectorBinding
    from integrations.egress.http import ResilientCaller

__all__ = ["CaseOperationResult", "ServiceNowAdapter"]

logger = logging.getLogger(__name__)

CONNECTOR_ID: Final = "servicenow"

# The organisation's discriminator WITHIN the shared instance (spec §22.2). An external system
# identifier, not an identity claim, and never accepted from a request — it is derived here from the
# trusted organisation the caller recovered from durable state.
_TENANT_FIELD: Final = "u_synthia_tenant"

_IDEMPOTENCY_HEADER: Final = "X-Idempotency-Key"
_CORRELATION_HEADER: Final = "X-Correlation-Id"


@dataclass(frozen=True, slots=True)
class CaseOperationResult:
    """The outcome of one system-of-record operation.

    Attributes:
        succeeded: Whether the call completed. **Not proof the effect happened** — that distinction
            is why the platform records verification separately from success.
        external_reference: The case identifier ServiceNow returned, where it returned one.
        payload: The normalized body. Contract-checked at the boundary; **data**, never instruction.
    """

    succeeded: bool
    external_reference: str | None
    payload: Mapping[str, object]


class ServiceNowAdapter:
    """All ServiceNow traffic, behind one boundary."""

    def __init__(self, caller: ResilientCaller, credentials: TenantCredentialResolver) -> None:
        """Bind the adapter.

        Args:
            caller: The one outbound HTTP path, with its explicit timeout and resilience policy.
            credentials: Per-organisation credential resolution. **The only path to a secret.**
        """
        self._caller = caller
        self._credentials = credentials

    async def create_case(
        self,
        binding: ConnectorBinding,
        tenant_id: UUID,
        parameters: Mapping[str, object],
        idempotency_key: str,
        correlation_id: str,
    ) -> CaseOperationResult:
        """Create a case, idempotently.

        Synchronous because the platform must know the outcome before proceeding: a session that
        cannot commit a case cannot enter Resolution Mode (spec §22.5). That is the one
        system-of-record operation whose blocking nature is settled; the rest are recorded as
        unresolved in ADR-0007 and are not guessed at here.

        Args:
            binding: Where and how, from the registry. **The destination comes from here.**
            tenant_id: The organisation, recovered from durable state. Stamped on the record.
            parameters: The case fields, as data.
            idempotency_key: The **derived** key. Carried so a retried write cannot double-post
                (`FR-EXT-004`).
            correlation_id: The journey, carried onto the outbound call so the vendor's own logs can
                be lined up with the platform's.

        Returns:
            The outcome, normalized.

        Raises:
            EgressError: When the call could not be completed at all.
            BoundaryValidationError: When the response is malformed, oversized or off-contract —
                rejected at the boundary rather than passed inward (`FR-EXT-021`).
        """
        credential = await self._credentials.resolve(tenant_id, binding.identity.catalogue_id)

        body = {
            **parameters,
            # Tenant stamping is the adapter's job and happens on every record (spec §22.2). Written
            # last so a caller-supplied key of the same name cannot override it — the shared
            # instance's row-level isolation depends on this field being the platform's word.
            _TENANT_FIELD: str(tenant_id),
        }

        request = OutboundRequest(
            method="POST",
            url=binding.destination,
            headers={
                # Revealed as late as possible, straight into the header map that is handed to the
                # client. Never assigned to a named local, because a named local is what ends up in
                # a traceback.
                "Authorization": f"Bearer {credential.reveal()}",
                _IDEMPOTENCY_HEADER: idempotency_key,
                _CORRELATION_HEADER: correlation_id,
                "Content-Type": "application/json",
            },
            json_body=body,
        )

        # NOT RETRIABLE. Case creation is side-effecting, and a failed authorized action requires
        # fresh human authorization rather than an automatic retry (spec FR-EXEC-006). The
        # idempotency key protects a retry the *far side* sees; it does not license one here.
        try:
            response = await self._caller.send(request, retriable=False)
        except EgressError:
            logger.warning(
                "ServiceNow case creation could not be completed",
                extra={"correlationId": correlation_id, "connector": CONNECTOR_ID},
            )
            raise

        if not response.succeeded:
            # A non-2xx is a failure, not an exception: the platform records the attempt and
            # escalates. Raising would lose the status, which is the one piece an operator needs.
            return CaseOperationResult(
                succeeded=False, external_reference=None, payload={"status": response.status_code}
            )

        normalized = normalize_case_result(response.payload)
        return CaseOperationResult(
            succeeded=True,
            external_reference=normalized.external_reference,
            payload=normalized.payload,
        )


__all__ += ["BoundaryValidationError"]
