"""Azure SignalR data plane — **a leaf on every consequential path, never a link**.

This channel may tell a client that something exists or has changed. It may never carry, imply or
trigger a decision (spec FR-IDENT-005). Three consequences follow, and all three are structural
rather than remembered:

1. **It carries no authority.** The envelope holds no tenant, role, approval state, target or
   command content — only kinds and opaque identifiers. A client that read authority from a
   notification would be trusting a push it cannot authenticate the contents of.
2. **It authorizes nothing.** There is no code path from a delivered notification to a state change.
   A decision arrives through an authenticated request that identifies the decider, or it does not
   arrive.
3. **A missed notification costs nothing.** Every outcome is recoverable by reading back through
   the API. That is asserted rather than assumed: a sample flow reaches an identical outcome with no
   client connected, because the notification is a leaf and the read is the source of truth.

**Managed identity, no access key.** The data plane is reached with an Entra token for
``https://signalr.azure.com/.default`` (research R-002). ``build/policy/azure-identity.json`` names
``AccessKey`` as forbidden configuration for this resource, and the security tests enforce it. The
role is ``SignalR App Server`` — narrow on purpose: ``SignalR Service Owner`` would also grant key
generation, and a key is the one credential that would let this channel be driven by something other
than this platform.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import httpx

from ragcore.domain.envelopes import NotificationEnvelope
from ragcore.domain.identifiers import PrincipalId
from ragcore.infrastructure.azure_credentials import azure_credential

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.settings import NotificationSettings

_log: Final = logging.getLogger(__name__)

SIGNALR_SCOPE: Final = "https://signalr.azure.com/.default"
"""The data-plane scope. A token for this and nothing broader."""

API_VERSION: Final = "2022-11-01"


@dataclass(frozen=True, slots=True)
class NotificationPayload:
    """What actually goes on the wire.

    Built from :class:`~ragcore.domain.envelopes.NotificationEnvelope` by :func:`payload_for`, which
    is the single place deciding what a client may see — so "the channel carries no authority" is
    one function to review rather than every call site.
    """

    kind: str
    occurred_at: str
    correlation_id: str
    session_id: str | None = None
    work_item_id: str | None = None


def payload_for(envelope: NotificationEnvelope) -> dict[str, Any]:
    """The wire form of a notification.

    Deliberately narrow: kinds and opaque identifiers only. No tenant, no principal, no role, no
    approval state, no target, no command content, and no message body. A client learns *that*
    something changed and reads *what* through the API, under its own identity — which is the only
    path where the read is authorized.

    Args:
        envelope: The domain envelope.

    Returns:
        The JSON-serialisable payload.
    """
    payload: dict[str, Any] = {
        "kind": envelope.kind.value,
        "occurredAt": envelope.occurred_at.isoformat(),
        "correlationId": str(envelope.correlation_id),
    }

    if envelope.session_id is not None:
        payload["sessionId"] = str(envelope.session_id)
    if envelope.work_item_id is not None:
        payload["workItemId"] = str(envelope.work_item_id)

    return payload


class SignalRNotifier:
    """Delivers notifications to one user's group, authenticated by managed identity.

    Satisfies :class:`~ragcore.application.ports.NotificationPort`.

    **Delivery failure is logged, not raised.** A flow must reach the same outcome whether or not
    the client is connected and whether or not the service is reachable; raising here would let a
    realtime outage fail a durable state change that had already succeeded. The client recovers by
    reading back — which is the property this channel is designed around, exercised rather than
    merely claimed.
    """

    def __init__(
        self,
        settings: NotificationSettings,
        client: httpx.AsyncClient | None = None,
        credential: Any | None = None,  # noqa: ANN401 — the concrete type needs the SDK imported
    ) -> None:
        """Bind the notifier to an endpoint and hub.

        Args:
            settings: The notification settings. There is no key field to pass.
            client: An HTTP client. Constructed per call when omitted; supplying one is how a test
                asserts on the request without a network.
            credential: The Azure credential. The shared process credential when omitted.
        """
        self._settings = settings
        self._client = client
        self._credential = credential

    async def notify_user(self, principal_id: PrincipalId, envelope: NotificationEnvelope) -> None:
        """Deliver a notification to one user.

        **Notification only.** This path never authorizes anything, and there is no return value a
        caller could mistake for a decision.

        Args:
            principal_id: The recipient, from trusted context. Never from a client request.
            envelope: What to deliver.
        """
        if not self._settings.is_configured:
            # Not an error. A scaffold without a SignalR endpoint still reaches every outcome,
            # because the notification is a leaf; the client reads back instead.
            _log.debug("Realtime delivery is not configured; skipping notification.")
            return

        url = (
            f"{self._settings.endpoint.rstrip('/')}/api/hubs/{self._settings.hub}"
            f"/users/{principal_id}/:send?api-version={API_VERSION}"
        )

        try:
            token = await self._access_token()
            client = self._client if self._client is not None else httpx.AsyncClient()
            try:
                response = await client.post(
                    url,
                    json=payload_for(envelope),
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
                response.raise_for_status()
            finally:
                if self._client is None:
                    await client.aclose()
        except Exception:  # noqa: BLE001 — see the class docstring: delivery must not fail the flow
            _log.warning(
                "Realtime notification was not delivered; the outcome remains readable through the "
                "API. kind=%s correlation=%s",
                envelope.kind.value,
                envelope.correlation_id,
                exc_info=True,
            )

    async def _access_token(self) -> str:
        """Fetch a data-plane token for this process's managed identity."""
        credential = self._credential if self._credential is not None else azure_credential()
        token = await credential.get_token(SIGNALR_SCOPE)
        return str(token.token)
