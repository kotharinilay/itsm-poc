"""The MCP boundary. **Discovery never confers entitlement.**

A tool appearing on an MCP server does not become callable. It becomes callable when it is
registered in the governance catalogue and entitled to the organisation in question — both of which
happen in the platform, neither of which happens here (spec FR-EXT-014, §21.2). MCP-discovered
tools inherit exactly the same governance as native ones; there is no separate path, no lighter
check and no exception.

**The rule is enforced by the types, because a rule enforced by discipline is enforced until it is
inconvenient.** Two methods, and the gap between them is the control:

* :meth:`McpToolClient.discover` returns :class:`AdvertisedTool` — a name, a system and a
  description the third party wrote. It carries **no treatment, no accepted roles and no
  entitlement**, so there is no field a caller can read to decide whether to proceed. It is
  advertising, and it is typed as advertising.
* :meth:`McpToolClient.invoke` takes an :class:`~ragcore.domain.identifiers.OperationIdentity` —
  a catalogue identifier and the version in force. There is no overload taking an
  :class:`AdvertisedTool`, so an advertised tool cannot be passed to the method that calls it. Going
  from one to the other means going through the catalogue, which is the point.

**Invocation is reached past the gate, never from the agent loop.** This client executes; it never
decides. An *action* capability MUST NOT be callable directly from the agent loop (spec FR-EXT-013),
and the composition root binds this behind
:class:`~ragcore.application.ports.ToolExecutionPort`, which the execution node reaches only after
governance has permitted the operation.

**Credentials are per organisation.** Resolved from ``tenant_entitlement.credential_reference``
through Key Vault at the point of use. There is no platform-wide credential for any MCP-backed
system, and the third parties reached this way — ServiceNow, OneLogin, Duo — are deliberately absent
from ``build/policy/azure-identity.json``: they are not Azure resources, and their credentials are
governed by the entitlement row rather than by a managed identity.

**Server output is data.** It is size-checked and contract-checked here before it reaches the agent
loop (spec FR-EXT-021), and it never becomes an instruction, a destination or a source of authority.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ragcore.domain.governance import VerificationOutcome
from ragcore.integrations.http import IntegrationError, OutboundRequest, ResilientHttpCaller
from ragcore.integrations.validation import (
    BoundaryValidationError,
    as_data,
    optional_text,
    require_object,
    require_text,
)

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Sequence

    from ragcore.config.settings import IntegrationSettings
    from ragcore.domain.identifiers import CorrelationId, IdempotencyKey, OperationIdentity
    from ragcore.domain.tenancy import TenantContext
    from ragcore.integrations.credentials import TenantCredentialResolver

_log: Final = logging.getLogger(__name__)

MAX_ADVERTISED_TOOLS: Final = 200
"""The ceiling on one server's advertisement.

Bounded because the list is third-party input like any other, and an unbounded one is an unbounded
allocation driven by something outside the platform.
"""


class McpServerNotConfiguredError(IntegrationError):
    """No endpoint is configured for this system.

    A refusal rather than a default. A client that fell back to a shared endpoint would be reaching
    one organisation's target system with another organisation's work.
    """

    def __init__(self, system: str) -> None:
        super().__init__(system, "no MCP server endpoint is configured for this system")


@dataclass(frozen=True, slots=True)
class AdvertisedTool:
    """One tool an MCP server claims to offer. **Not a capability this platform can call.**

    Satisfies :class:`~ragcore.application.ports.AdvertisedCapability`.

    Frozen and deliberately impoverished: no treatment, no roles, no entitlement, no catalogue
    identifier. There is nothing here to act on, which is what makes "discovery is not entitlement"
    a property of the type rather than a sentence in a review comment.
    """

    system: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class McpInvocationResult:
    """What came back from invoking a governed capability.

    Satisfies :class:`~ragcore.application.ports.ExecutionResult`.

    ``succeeded`` says the *call* worked. ``verification`` says what the platform actually knows
    about the *effect*, and the two are not the same claim: a server that returns 200 has reported a
    result, not proved one. Defaulting to ``CLIENT_ATTESTED`` is the honest position — a
    server-confirmed outcome requires a separate read tool, and claiming more than the platform
    knows is what constitution Principle VIII prohibits.
    """

    succeeded: bool
    verification: VerificationOutcome
    detail: str = ""


def parse_server_urls(configured: str) -> dict[str, str]:
    """Read the ``system=url`` server list from configuration.

    Args:
        configured: The comma-separated list, for example
            ``onelogin=https://mcp.example/onelogin,duo=https://mcp.example/duo``.

    Returns:
        System name to endpoint.

    Raises:
        ValueError: When an entry is malformed or an endpoint is not https. Refused at startup
            rather than at first use: a typo here means one organisation's capability silently
            never resolves, which looks like an entitlement problem and is not.
    """
    servers: dict[str, str] = {}

    for entry in configured.split(","):
        candidate = entry.strip()
        if not candidate:
            continue

        system, separator, url = candidate.partition("=")
        if not separator or not system.strip() or not url.strip():
            raise ValueError(
                f"an MCP server entry must be 'system=url', got {candidate!r}. "
                "Listing a server enables discovery and nothing else; entitlement is decided in "
                "the governance catalogue."
            )
        if not url.strip().startswith("https://"):
            raise ValueError(f"an MCP server endpoint must be https, got {url.strip()!r}")

        servers[system.strip()] = url.strip().rstrip("/")

    return servers


class McpToolClient:
    """The one path to an MCP-backed target system.

    Satisfies :class:`~ragcore.application.ports.CapabilityDiscoveryPort` and, for invocation,
    :class:`~ragcore.application.ports.ToolExecutionPort`.
    """

    def __init__(
        self,
        settings: IntegrationSettings,
        caller: ResilientHttpCaller,
        credentials: TenantCredentialResolver,
    ) -> None:
        """Bind the client to its configured servers.

        Args:
            settings: Where the servers are. Addresses, never credentials.
            caller: The shared resilient HTTP caller.
            credentials: Per-organisation credential resolution, through Key Vault.

        Raises:
            ValueError: When the configured server list is malformed.
        """
        self._settings = settings
        self._caller = caller
        self._credentials = credentials
        self._servers = parse_server_urls(settings.mcp_server_urls)

    async def discover(self, tenant: TenantContext, system: str) -> Sequence[AdvertisedTool]:
        """List what a system advertises. **Nothing returned here is callable.**

        Args:
            tenant: The organisation, whose credential is used to ask.
            system: The system's platform name.

        Returns:
            The advertisements, bounded by :data:`MAX_ADVERTISED_TOOLS`.

        Raises:
            McpServerNotConfiguredError: When no endpoint is configured for the system.
            TransientIntegrationError: When the server is unreachable. **Not an empty list**:
                "advertises nothing" and "could not be asked" are different facts, and collapsing
                them would report an outage as a shrunken toolset.
        """
        endpoint = self._endpoint_for(system)
        credential = await self._credentials.resolve(tenant, system)

        response = await self._caller.send(
            system,
            OutboundRequest(
                method="POST",
                url=f"{endpoint}/tools/list",
                timeout_seconds=self._settings.request_timeout_seconds,
                headers={
                    "Authorization": f"Bearer {credential.reveal()}",
                    "Content-Type": "application/json",
                },
                json_body={},
            ),
        )

        body = require_object(system, response.json())
        advertised = body.get("tools")

        if not isinstance(advertised, list):
            raise BoundaryValidationError(system, "the discovery response carries no tool list")
        if len(advertised) > MAX_ADVERTISED_TOOLS:
            raise BoundaryValidationError(
                system, f"the server advertised {len(advertised)} tools, above the bounded limit"
            )

        tools: list[AdvertisedTool] = []
        for item in advertised:
            fields = require_object(system, item)
            tools.append(
                AdvertisedTool(
                    system=system,
                    name=require_text(system, fields, "name", limit=256),
                    # The third party wrote this, so it is marked as data at the point it enters.
                    # It is shown to operators and never read as an instruction.
                    description=as_data(optional_text(system, fields, "description") or ""),
                )
            )

        return tools

    async def invoke(
        self,
        tenant: TenantContext,
        identity: OperationIdentity,
        parameters: object,
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> McpInvocationResult:
        """Invoke a capability that governance has already authorized.

        **This method executes; it never decides.** It takes an
        :class:`~ragcore.domain.identifiers.OperationIdentity` — a catalogue identifier and the
        version approved — and there is deliberately no overload taking an :class:`AdvertisedTool`.
        An advertised tool therefore cannot be invoked without passing through the catalogue.

        Args:
            tenant: The organisation, from trusted context.
            identity: The catalogue entry and the version in force when it was proposed.
            parameters: The arguments, already validated by the caller.
            idempotency_key: Idempotency boundary 2 — protects the **external** system.
            correlation_id: The journey.

        Returns:
            What the platform knows: whether the call succeeded, and separately what it can verify.

        Raises:
            McpServerNotConfiguredError: When no endpoint is configured for the owning system.
            TransientIntegrationError: When the server is unreachable. **The caller does not
                re-fire**: a failed authorized action requires fresh human authorization
                (ADR-0002), and a transport retry of a side-effecting call is not that.
        """
        system = identity.catalogue_id.partition(".")[0]
        endpoint = self._endpoint_for(system)
        credential = await self._credentials.resolve(tenant, system)

        response = await self._caller.send(
            system,
            OutboundRequest(
                method="POST",
                url=f"{endpoint}/tools/call",
                timeout_seconds=self._settings.request_timeout_seconds,
                headers={
                    "Authorization": f"Bearer {credential.reveal()}",
                    "Content-Type": "application/json",
                    "X-Synthia-Idempotency-Key": str(idempotency_key),
                    "X-Correlation-Id": str(correlation_id),
                },
                json_body={
                    "name": identity.catalogue_id,
                    "version": identity.version,
                    "arguments": parameters,
                },
            ),
        )

        body = require_object(system, response.json())

        return McpInvocationResult(
            succeeded=body.get("isError") is not True,
            # CLIENT_ATTESTED regardless of what the server said about itself. A server-confirmed
            # outcome requires the platform to have read the effect back through a verification
            # tool; a success field in the response is the server's claim about its own work.
            verification=VerificationOutcome.CLIENT_ATTESTED,
            detail=as_data(optional_text(system, body, "summary", limit=1024) or ""),
        )

    def _endpoint_for(self, system: str) -> str:
        """The configured endpoint for one system.

        Raises:
            McpServerNotConfiguredError: When none is configured. There is no shared fallback.
        """
        endpoint = self._servers.get(system)

        if not endpoint:
            raise McpServerNotConfiguredError(system)

        return endpoint
