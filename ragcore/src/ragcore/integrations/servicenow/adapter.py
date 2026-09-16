"""ServiceNow. **The single owning boundary for every call to the system of record.**

All traffic to a given external system passes through one boundary, and that system's own concepts
do not leak into the platform's model (spec FR-EXT-011). Two consequences are visible in the code
below and both are deliberate.

*Nothing outside this module names ServiceNow.* The port the platform holds is
:class:`~ragcore.application.ports.CaseSystemPort`, whose signatures mention a case reference and
facts. ``sys_id``, ``incident``, ``u_`` prefixes and table names appear here and nowhere else.

*The system of record is not an authority.* It holds the case; it does not hold approvals. An
inbound state change from it is an untrusted signal that MUST NOT set platform state and MUST NOT
authorize execution (spec FR-EXT-005, FR-EXT-006). This adapter therefore has no read method that
returns a decision, and no method here returns anything the gate consults.

**Idempotent by construction.** A retried write MUST NOT double-post (spec FR-EXT-004). The
idempotency key is a required parameter with no default, carried as a correlation header the
instance deduplicates on and reused verbatim on replay. A key generated inside this adapter would be
a new key on every attempt, which is the same as having none.

**Queue and replay, not fail and lose.** A transient failure is queued
(:mod:`ragcore.integrations.servicenow.queue`) and reported as queued — never as success. An outage
does not block the agent loop, and a session whose case has not committed does not proceed to
resolution (spec FR-EXT-007). Those are two different callers' decisions, which is why this returns
a receipt rather than a boolean.

**Credentials are per organisation.** Resolved from
``tenant_entitlement.credential_reference`` through Key Vault at the point of use, revealed into the
request header and nowhere else (spec FR-EXT-016). There is no platform-wide ServiceNow credential
in settings, in this module, or anywhere else — one would be the same credential for every
organisation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ragcore.integrations.http import (
    IntegrationError,
    OutboundRequest,
    ResilientHttpCaller,
    TransientIntegrationError,
)
from ragcore.integrations.servicenow.queue import PendingCaseWrite

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping

    from ragcore.application.ports import ClockPort
    from ragcore.config.settings import IntegrationSettings
    from ragcore.domain.identifiers import CorrelationId, IdempotencyKey
    from ragcore.domain.tenancy import TenantContext
    from ragcore.integrations.credentials import TenantCredentialResolver
    from ragcore.integrations.servicenow.queue import CaseWriteQueuePort

_log: Final = logging.getLogger(__name__)

SYSTEM: Final = "servicenow"
"""The pool name, the credential key, and the name this integration is known by."""

IDEMPOTENCY_HEADER: Final = "X-Synthia-Idempotency-Key"
"""What makes a retried write the same write.

Sent on every attempt including replays, with the key the caller supplied. The instance-side
deduplication is what actually prevents the double-post; this header is what gives it something to
deduplicate on.
"""


@dataclass(frozen=True, slots=True)
class CaseWriteOutcome:
    """What the platform knows about one case write.

    Satisfies :class:`~ragcore.application.ports.CaseWriteReceipt`. Three states rather than a
    boolean, because "queued" is neither success nor failure and a caller needs to tell them apart:
    the agent loop continues on a queued write, and the session still does not resolve.
    """

    committed: bool
    queued: bool


class ServiceNowAdapter:
    """The system of record, behind one boundary.

    Satisfies :class:`~ragcore.application.ports.CaseSystemPort`.
    """

    def __init__(
        self,
        settings: IntegrationSettings,
        caller: ResilientHttpCaller,
        credentials: TenantCredentialResolver,
        queue: CaseWriteQueuePort,
        clock: ClockPort,
    ) -> None:
        """Bind the adapter to its instance and its collaborators.

        Args:
            settings: Where the instance is. **An address, never a credential.**
            caller: The shared resilient HTTP caller.
            credentials: Per-organisation credential resolution, through Key Vault.
            queue: Where a write waits out an outage.
            clock: The current instant. A port, so the queued-at timestamp is testable and nothing
                here calls ``datetime.now``.
        """
        self._settings = settings
        self._caller = caller
        self._credentials = credentials
        self._queue = queue
        self._clock = clock

    async def record_progress(
        self,
        tenant: TenantContext,
        case_reference: str,
        facts: Mapping[str, str],
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> CaseWriteOutcome:
        """Write session progress to the case, idempotently.

        Args:
            tenant: The organisation, from trusted context. Selects the credential.
            case_reference: The case in the system of record.
            facts: What to write, in platform vocabulary.
            idempotency_key: Required, no default. What makes a retry safe.
            correlation_id: The journey this write belongs to.

        Returns:
            A receipt. ``committed`` when the instance accepted it; ``queued`` when the instance
            was unreachable and the write is held for replay.

        Raises:
            CredentialNotEntitledError: When the organisation holds no ServiceNow credential. Not
                queued — a write that could never be authorized is not waiting on an outage, and
                queueing it would hide a configuration defect behind a retry that never succeeds.
            PermanentIntegrationError: When the instance refused the write. Not queued, for the same
                reason: replaying a rejected write produces the same rejection.
        """
        instance = self._settings.servicenow_instance_url.strip().rstrip("/")

        if not instance:
            raise IntegrationError(SYSTEM, "no ServiceNow instance is configured")

        # Resolved per organisation, as late as possible, and revealed exactly once — while handing
        # it to the request. The SecretValue itself never reaches a log line or a span, because
        # every rendering path on it redacts.
        credential = await self._credentials.resolve(tenant, SYSTEM)

        request = OutboundRequest(
            method="POST",
            url=f"{instance}/api/now/table/incident/{case_reference}/progress",
            timeout_seconds=self._settings.request_timeout_seconds,
            headers={
                "Authorization": f"Bearer {credential.reveal()}",
                "Content-Type": "application/json",
                IDEMPOTENCY_HEADER: str(idempotency_key),
                "X-Correlation-Id": str(correlation_id),
            },
            json_body={"facts": dict(facts)},
        )

        try:
            await self._caller.send(SYSTEM, request)
        except TransientIntegrationError:
            # The system of record is unreachable. The write survives, the loop continues, and the
            # session does not resolve — all three, which is why this returns rather than raises and
            # why the receipt says `queued` rather than `committed`.
            await self._queue.enqueue(
                PendingCaseWrite(
                    tenant_id=tenant.tenant_id,
                    case_reference=case_reference,
                    facts=dict(facts),
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    queued_at=self._clock.now(),
                )
            )
            _log.warning(
                "The system of record was unreachable; the case write is queued for replay. "
                "correlation=%s",
                correlation_id,
            )
            return CaseWriteOutcome(committed=False, queued=True)

        return CaseWriteOutcome(committed=True, queued=False)

    async def uncommitted_writes(self, tenant: TenantContext) -> int:
        """How many of this organisation's case writes are still waiting.

        **This is the question a session asks before resolving.** A non-zero answer means the case
        does not yet reflect what happened, which FR-EXT-007 says must stop resolution and be told
        to the user — not silently retried until it looks fine.
        """
        return await self._queue.pending_for(tenant.tenant_id)
