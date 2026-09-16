"""Microsoft Graph — directory and productivity, behind one boundary (spec FR-EXT-008).

**Read-only by interface, not by intention.** Graph can create, modify and delete a great deal, and
every verb this adapter exposes is a capability reachable without passing the governance gate.
:class:`~ragcore.application.ports.DirectoryPort` therefore declares one read, and a directory
*write* does not belong here at all — it belongs in the governance catalogue as an action
capability, invoked through :class:`~ragcore.application.ports.ToolExecutionPort` once treatment and
approval have been decided (spec FR-EXT-013).

**Managed identity, and the scope is the whole story.** Graph is reached with an Entra token for
``https://graph.microsoft.com/.default``, minted by the shared process credential. What this
process may actually do is decided by the application permissions granted to
``id-synthia-ragcore`` — centrally revocable, visible without reading application configuration, and
nothing to exfiltrate. There is no client secret here; ``build/policy/azure-identity.json`` names
that credential type as forbidden everywhere.

**Graph's vocabulary stops here.** ``userPrincipalName``, ``@odata.context`` and ``id`` appear in
this module and nowhere else. What leaves is a :class:`DirectoryProfileRecord` in platform terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from ragcore.infrastructure.azure_credentials import azure_credential
from ragcore.integrations.http import (
    OutboundRequest,
    PermanentIntegrationError,
    ResilientHttpCaller,
)
from ragcore.integrations.validation import optional_text, require_object, require_text

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.settings import IntegrationSettings
    from ragcore.domain.identifiers import PrincipalId
    from ragcore.domain.tenancy import TenantContext

SYSTEM: Final = "graph"
GRAPH_SCOPE: Final = "https://graph.microsoft.com/.default"
"""The application scope. What it grants is decided by role assignment, not by this string."""


@dataclass(frozen=True, slots=True)
class DirectoryProfileRecord:
    """Directory facts in platform terms.

    Satisfies :class:`~ragcore.application.ports.DirectoryProfile`. Deliberately two fields: the
    platform's identity comes from the validated token at the edge (constitution Principle I), so
    what the directory adds is presentation detail, not identity. A profile carrying roles or group
    membership would be a second source of authorization beside the closed header contract.
    """

    display_name: str
    mail: str | None


class MicrosoftGraphAdapter:
    """Directory reads through Microsoft Graph.

    Satisfies :class:`~ragcore.application.ports.DirectoryPort`.
    """

    def __init__(
        self,
        settings: IntegrationSettings,
        caller: ResilientHttpCaller,
        credential: Any | None = None,  # noqa: ANN401 — the concrete type needs the SDK imported
    ) -> None:
        """Bind the adapter to Graph.

        Args:
            settings: Where Graph is. A well-known address.
            caller: The shared resilient HTTP caller.
            credential: The Azure credential. The shared process credential when omitted.
        """
        self._settings = settings
        self._caller = caller
        self._credential = credential

    async def lookup_principal(
        self, tenant: TenantContext, principal_id: PrincipalId
    ) -> DirectoryProfileRecord | None:
        """Resolve directory facts about one principal.

        Args:
            tenant: The organisation, from trusted context. Present because every port method in
                this platform is tenant-scoped by interface — there is no overload that omits it,
                so an unscoped call is not something a caller can express.
            principal_id: The principal, from trusted context. **Never from a client request and
                never from model or retrieved content** (spec FR-EXT-018).

        Returns:
            The profile, or ``None`` when the directory does not know them. ``None`` is an absence
            of information and is never read as an authorization outcome.

        Raises:
            TransientIntegrationError: When Graph is unreachable. Reported as temporarily
                unavailable, distinctly from not entitled (spec FR-EXT-022).
            BoundaryValidationError: When the response does not match its contract.
        """
        del tenant

        base = self._settings.graph_base_url.rstrip("/")
        credential = self._credential if self._credential is not None else azure_credential()
        token = await credential.get_token(GRAPH_SCOPE)

        request = OutboundRequest(
            method="GET",
            url=f"{base}/users/{principal_id}?$select=displayName,mail",
            timeout_seconds=self._settings.request_timeout_seconds,
            headers={"Authorization": f"Bearer {token.token}"},
        )

        try:
            response = await self._caller.send(SYSTEM, request)
        except PermanentIntegrationError as error:
            # 404 is an answer, not a failure: the directory does not know this principal. Every
            # other permanent status is a genuine problem and is raised.
            if "404" in str(error):
                return None
            raise

        body = require_object(SYSTEM, response.json())

        return DirectoryProfileRecord(
            display_name=require_text(SYSTEM, body, "displayName", limit=256),
            mail=optional_text(SYSTEM, body, "mail", limit=320),
        )
