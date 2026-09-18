"""Microsoft Graph — directory and productivity, behind one boundary (spec `FR-EXT-008`).

Relocated from RagCore by T289; behaviour unchanged from T130. **RagCore no longer reaches Graph**,
and the reason is the same one that moved ServiceNow: a directory read is a call to an external
system, and every such call belongs to this service (ADR-0007, `FR-INTEG-016`).

**Read-only by interface, not by intention.** Graph can create, modify and delete a great deal, and
every verb this adapter exposes is a capability reachable without passing the governance gate. It
therefore declares one read, and a directory *write* does not belong here at all — it belongs in the
governance catalogue as an action capability, executed through the ordinary governed path once
treatment and approval have been decided (spec `FR-EXT-013`).

**Managed identity, and the scope is the whole story.** Graph is reached with an Entra token for
``https://graph.microsoft.com/.default``, minted by this service's own credential. What the process
may actually do is decided by the application permissions granted to ``id-synthia-integrations`` —
centrally revocable, visible without reading application configuration, and nothing to exfiltrate.
There is no client secret here; ``build/policy/azure-identity.json`` names that credential type as
forbidden everywhere.

**No per-organisation credential, and that is not an inconsistency.** ServiceNow and the MCP-backed
targets resolve a tenant credential because each organisation holds its own account there. Graph is
reached as the platform itself, so there is nothing to resolve — and taking a
:class:`~integrations.credentials.resolver.TenantCredentialResolver` here anyway, unused, would
suggest a per-organisation secret exists for Graph when none does.

**Graph's vocabulary stops at the boundary check.** ``userPrincipalName``, ``@odata.context`` and
``id`` are read by
:func:`~integrations.execution.normalization.normalize_directory_profile` and nowhere else.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from integrations.egress.http import EgressError, OutboundRequest
from integrations.execution.normalization import normalize_directory_profile

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from uuid import UUID

    from azure.core.credentials_async import AsyncTokenCredential

    from integrations.domain.catalogue import ConnectorBinding
    from integrations.egress.http import ResilientCaller
    from integrations.execution.normalization import NormalizedProfile

__all__ = ["GRAPH_SCOPE", "MicrosoftGraphAdapter"]

logger = logging.getLogger(__name__)

CONNECTOR_ID: Final = "graph"

GRAPH_SCOPE: Final = "https://graph.microsoft.com/.default"
"""The application scope. What it grants is decided by role assignment, not by this string."""

_CORRELATION_HEADER: Final = "X-Correlation-Id"

# A directory read is on the reasoning path and must not hold it open. Distinct from the
# side-effecting timeouts: a read that is slow can be abandoned, a write that is slow cannot.
_READ_TIMEOUT_SECONDS: Final = 10.0

_NOT_FOUND: Final = 404


class MicrosoftGraphAdapter:
    """Directory reads through Microsoft Graph, behind one boundary."""

    def __init__(self, caller: ResilientCaller, credential: AsyncTokenCredential) -> None:
        """Bind the adapter to Graph.

        Args:
            caller: The one outbound HTTP path, with its explicit timeout and resilience policy.
            credential: The Azure credential, **injected rather than constructed**. A module that
                reached for the ambient credential itself could not be tested without one, and the
                test that could not run is the test that proves the token is scoped.
        """
        self._caller = caller
        self._credential = credential

    async def lookup_principal(
        self,
        binding: ConnectorBinding,
        tenant_id: UUID,
        principal_id: str,
        correlation_id: str,
    ) -> NormalizedProfile | None:
        """Resolve directory facts about one principal.

        Args:
            binding: Where and how, from the registry. **The destination comes from here** and never
                from a parameter, model output or retrieved content (`FR-EXT-018`).
            tenant_id: The organisation, recovered from durable state. Present because every
                connector entry point in this service is organisation-scoped by signature — there
                is no overload omitting it, so an unscoped call is not something a caller can
                express.
            principal_id: The principal, from trusted context. **Never from a client request and
                never from model or retrieved content.**
            correlation_id: The journey, carried onto the outbound call.

        Returns:
            The profile, or ``None`` when the directory does not know them. ``None`` is an absence
            of information and is **never** read as an authorization outcome.

        Raises:
            EgressError: When Graph could not be reached. Reported as temporarily unavailable,
                distinctly from not entitled (`FR-EXT-022`) — two different operator actions.
            BoundaryValidationError: When the response does not match its contract.
        """
        del tenant_id

        token = await self._credential.get_token(GRAPH_SCOPE)

        request = OutboundRequest(
            method="GET",
            url=f"{binding.destination}/{principal_id}?$select=displayName,mail",
            headers={
                # Revealed straight into the header map, never assigned to a named local — a named
                # local is what ends up in a traceback.
                "Authorization": f"Bearer {token.token}",
                _CORRELATION_HEADER: correlation_id,
            },
            timeout_seconds=_READ_TIMEOUT_SECONDS,
        )

        # RETRIABLE, unlike every write in this package. A directory read has no effect to
        # duplicate, so the rule that forbids re-firing a side-effecting call does not reach it.
        try:
            response = await self._caller.send(request, retriable=True)
        except EgressError:
            logger.warning(
                "Graph directory lookup could not be completed",
                extra={"correlationId": correlation_id, "connector": CONNECTOR_ID},
            )
            raise

        if response.status_code == _NOT_FOUND:
            # An answer, not a failure: the directory does not know this principal.
            return None

        if not response.succeeded:
            # Every other non-2xx is a genuine problem and is raised rather than returned as
            # `None` — a caller handed `None` cannot tell "unknown principal" from "Graph is
            # broken", and the tempting reading of the ambiguity is the wrong one.
            raise EgressError(
                f"Graph returned {response.status_code} for a directory read. Reported as "
                "unavailable rather than as an unknown principal; those are different facts."
            )

        return normalize_directory_profile(response.payload)
