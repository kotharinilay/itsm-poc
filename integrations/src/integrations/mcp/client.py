"""The MCP boundary. **Discovery never confers entitlement.**

A tool appearing on an MCP server does not become callable. It becomes callable when it is
registered in the governance catalogue **and** entitled to the organisation — both of which happen
in the platform, neither of which happens here (spec `FR-EXT-014`, §21.2). MCP-discovered tools
inherit exactly the same governance as native ones: no separate path, no lighter check, no
exception.

**The rule is enforced by the types, because a rule enforced by discipline is enforced until it is
inconvenient.** Two methods, and the gap between them is the control:

* :meth:`McpClient.discover` returns :class:`AdvertisedTool` — a name, a system and a description
  the third party wrote. It carries **no treatment, no accepted roles and no entitlement**, so there
  is no field a caller can read to decide whether to proceed. It is advertising, and it is typed as
  advertising.
* :meth:`McpClient.invoke` takes a :class:`~integrations.domain.catalogue.ConnectorBinding` — a
  registry row naming the destination. **There is no overload taking an `AdvertisedTool`**, so an
  advertised tool cannot be passed to the method that calls it. Going from one to the other means
  going through the catalogue and the access re-check, which is the point.

**Server output is data.** It is size-checked and contract-checked before it leaves this module
(`FR-EXT-021`), and it never becomes an instruction, a destination, an identity, an organisation or
a source of authority.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from integrations.egress.http import OutboundRequest
from integrations.execution.normalization import (
    BoundaryValidationError,
    normalize_tool_result,
)

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping, Sequence
    from uuid import UUID

    from integrations.credentials.resolver import TenantCredentialResolver
    from integrations.domain.catalogue import ConnectorBinding
    from integrations.egress.http import ResilientCaller

__all__ = ["AdvertisedTool", "McpClient", "McpToolResult"]

logger = logging.getLogger(__name__)

_CORRELATION_HEADER: Final = "X-Correlation-Id"
_IDEMPOTENCY_HEADER: Final = "X-Idempotency-Key"


@dataclass(frozen=True, slots=True)
class AdvertisedTool:
    """A capability an MCP server says it has. **Advertising, and typed as advertising.**

    Note what is absent and cannot be added without changing this type: treatment, accepted roles,
    entitlement, risk tier. A caller holding one of these has nothing to read that would justify
    invoking it — which is what makes "discovery is not entitlement" a property rather than a rule
    somebody has to remember.

    Attributes:
        name: What the server calls it. **Not a catalogue identifier**, and deliberately named
            differently so the two are not confused at a call site.
        system: The connector that advertised it.
        description: Prose the third party wrote. Displayed to an operator considering
            registration; never parsed, and never an input to a decision.
    """

    name: str
    system: str
    description: str


@dataclass(frozen=True, slots=True)
class McpToolResult:
    """What an MCP server returned, already normalized.

    Attributes:
        succeeded: Whether the invocation completed. **Not proof the effect happened.**
        external_reference: The server's own identifier for the result, where it returns one.
        payload: The contract-checked body. Data.
    """

    succeeded: bool
    external_reference: str | None
    payload: Mapping[str, object]


class McpClient:
    """The client half of every MCP conversation."""

    def __init__(self, caller: ResilientCaller, credentials: TenantCredentialResolver) -> None:
        """Bind the client.

        Args:
            caller: The one outbound HTTP path, with its explicit timeout and resilience policy.
            credentials: Per-organisation credential resolution. **There is no platform-wide
                credential for any MCP-backed system**, and this is the only way to a value.
        """
        self._caller = caller
        self._credentials = credentials

    async def discover(
        self, binding: ConnectorBinding, tenant_id: UUID, correlation_id: str
    ) -> Sequence[AdvertisedTool]:
        """Ask a server what it offers.

        **Nothing here becomes callable.** The return type carries no entitlement and no treatment,
        and there is no method on this class that accepts one.

        Args:
            binding: The connector to ask. From the registry.
            tenant_id: The organisation whose credential is used.
            correlation_id: The journey.

        Returns:
            What the server advertised. An empty sequence when it advertises nothing or answers
            unusably — **an absence, not an error**: a server with nothing to offer is ordinary,
            and raising would make an empty catalogue look like an outage.
        """
        credential = await self._credentials.resolve(tenant_id, binding.identity.catalogue_id)

        request = OutboundRequest(
            method="GET",
            url=binding.destination,
            headers={
                "Authorization": f"Bearer {credential.reveal()}",
                _CORRELATION_HEADER: correlation_id,
            },
        )
        # A discovery call is a READ: retriable, because re-reading changes nothing.
        response = await self._caller.send(request, retriable=True)
        if not response.succeeded:
            return ()

        raw = response.payload.get("tools")
        if not isinstance(raw, list):
            return ()

        return tuple(
            AdvertisedTool(
                name=str(entry.get("name", "")),
                system=binding.connector_id,
                description=str(entry.get("description", "")),
            )
            for entry in raw
            if isinstance(entry, dict) and entry.get("name")
        )

    async def invoke(
        self,
        binding: ConnectorBinding,
        tenant_id: UUID,
        parameters: Mapping[str, object],
        idempotency_key: str | None,
        correlation_id: str,
    ) -> McpToolResult:
        """Invoke a **registered, entitled** capability.

        Reached only past the access and policy re-check. This method executes; it never decides.

        Args:
            binding: Where and how, from the registry. **The destination comes from here** — there
                is no parameter, host or path override in this signature, and adding one would be
                the egress hole `FR-EXT-018` exists to close.
            tenant_id: The organisation, recovered from the durable job record.
            parameters: The arguments, as data.
            idempotency_key: The derived key, or ``None`` for a capability whose policy is `NONE`.
            correlation_id: The journey, carried onto the outbound call.

        Returns:
            The normalized result.

        Raises:
            EgressError: When the call could not be completed.
            BoundaryValidationError: When the response is malformed, oversized or off-contract.
        """
        credential = await self._credentials.resolve(tenant_id, binding.identity.catalogue_id)

        headers = {
            "Authorization": f"Bearer {credential.reveal()}",
            _CORRELATION_HEADER: correlation_id,
            "Content-Type": "application/json",
        }
        if idempotency_key is not None:
            headers[_IDEMPOTENCY_HEADER] = idempotency_key

        request = OutboundRequest(
            method="POST",
            url=binding.destination,
            headers=headers,
            json_body={"arguments": dict(parameters)},
        )

        # NOT RETRIABLE. An MCP invocation past the gate is side-effecting as far as this service
        # can know, and a failed authorized action requires fresh human authorization rather than
        # an automatic retry (spec FR-EXEC-006). The idempotency key protects a retry the FAR SIDE
        # sees; it does not license one here.
        response = await self._caller.send(request, retriable=False)

        if not response.succeeded:
            return McpToolResult(succeeded=False, external_reference=None, payload={})

        try:
            normalized = normalize_tool_result(response.payload)
        except BoundaryValidationError:
            logger.warning(
                "MCP server output rejected at the boundary",
                extra={"correlationId": correlation_id, "connector": binding.connector_id},
            )
            raise

        return McpToolResult(
            succeeded=True,
            external_reference=normalized.external_reference,
            payload=normalized.payload,
        )
