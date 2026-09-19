"""The Integrations Service client. **RagCore's only route to an external system — through APIM.**

ADR-0007, specification §21.6. RagCore reaches no external system: it calls the Integrations
Service, which owns every connector, every credential and every egress path. This module is that
call.

**It goes through the gateway, and there is no internal address here.** Specification §13.4 forbids
a direct service-to-service route — not pod to pod, not container to container, not by internal
name. The base URL configured for this client is the **public edge** address, and APIM re-derives
identity on the hop. `build/scripts/check-boundaries.sh` fails the build if a base address naming
the Integrations Service directly appears anywhere in this tree.

**App-only, on the workload audience, with its own application role.** RagCore authenticates as
itself; it does not forward a user token here. The organisation is therefore **not** carried on the
call — it is recovered by the far side from the durable object the opaque identifier names
(`FR-INTEG-018`). That is why every method below takes a `session_id` and none takes a tenant.

**This client is not an authority.** It returns what the far side reported. It does not decide
whether an operation was permitted, and there is no method here that could — a refusal comes back as
an outcome, not as a decision RagCore then re-interprets.

**Reuses RagCore's existing outbound stack** (:mod:`ragcore.egress.http`) rather than adding a
second one: the same pool, the same explicit-timeout rule, the same transient/permanent
classification. A second HTTP path would be a second place "which statuses are worth retrying" gets
answered, and only one of the answers would ever be tested.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlencode

from ragcore.egress.http import (
    IntegrationError,
    OutboundRequest,
    PermanentIntegrationError,
)
from ragcore.infrastructure.azure_credentials import azure_credential

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping
    from uuid import UUID

    from ragcore.domain.identifiers import CorrelationId, IdempotencyKey
    from ragcore.egress.http import ResilientHttpCaller

__all__ = ["CaseOperationOutcome", "IntegrationsClient", "IntegrationsClientSettings"]

_log = logging.getLogger(__name__)

SYSTEM: Final = "integrations"
"""Selects the connection pool and names the error. Not a credential key: this hop authenticates
with a managed identity, and there is no per-organisation secret involved in reaching a sibling
platform service."""

CATALOGUE_PATH: Final = "/api/workload/v1/integrations/catalogue"
CASE_OPERATIONS_PATH: Final = "/api/workload/v1/integrations/case-operations"

_CORRELATION_HEADER: Final = "X-Correlation-Id"

# A catalogue read is on the reasoning path; a case creation blocks entry to Resolution Mode. Both
# are bounded well inside the fifteen-minute window, which now spans two hops rather than one.
_READ_TIMEOUT_SECONDS: Final = 10.0
_WRITE_TIMEOUT_SECONDS: Final = 15.0


@dataclass(frozen=True, slots=True)
class IntegrationsClientSettings:
    """Where the Integrations Service is reached.

    Attributes:
        gateway_base_url: **The public edge address**, not an internal one. Every application call
            traverses Front Door, the WAF and APIM; a value naming the container app directly is the
            bypass the boundary check exists to catch. Must be https — :class:`OutboundRequest`
            refuses anything else at construction.
        entra_scope: The token scope APIM validates on the workload audience. Required: APIM runs
            ``validate-azure-ad-token`` on this route, so a call without a token never arrives.
    """

    gateway_base_url: str
    entra_scope: str

    def __post_init__(self) -> None:
        """Refuse a base URL that is not the edge.

        Raises:
            ValueError: When the URL is not https, or names an internal Container Apps address.
                Refused here so the failure names the configuration rather than appearing later as
                a puzzling 403 from a service that was never reached.
        """
        if not self.gateway_base_url.startswith("https://"):
            raise ValueError(
                f"the Integrations base URL must be https, got {self.gateway_base_url!r}."
            )
        if ".internal." in self.gateway_base_url:
            raise ValueError(
                "the Integrations base URL names an internal address. Every application call "
                "traverses Front Door, the WAF and APIM; there is no direct route (spec §13.4)."
            )
        if not self.entra_scope.strip():
            raise ValueError(
                "the Integrations client needs a token scope: APIM refuses an unauthenticated call "
                "on the workload audience."
            )


@dataclass(frozen=True, slots=True)
class CaseOperationOutcome:
    """What the Integrations Service reported.

    Attributes:
        succeeded: Whether the system-of-record operation completed.
        external_reference: The case identifier, where one was returned.
        refused: ``True`` when the far side refused on access or policy grounds. **Distinct from a
            failure**: a refusal means the platform's own rules said no and a human must change
            configuration; a failure means the far side broke. Conflating them sends an operator to
            the wrong system.
    """

    succeeded: bool
    external_reference: str | None
    refused: bool


class IntegrationsClient:
    """Calls the Integrations Service, through the gateway, as the workload principal."""

    def __init__(
        self,
        settings: IntegrationsClientSettings,
        caller: ResilientHttpCaller,
        credential: Any | None = None,  # noqa: ANN401 — the concrete type needs the SDK imported
    ) -> None:
        """Bind the client.

        Args:
            settings: The edge address and the token scope.
            caller: The shared resilient caller, so this call obeys the same timeout and
                classification policy as every other outbound call.
            credential: An ``AsyncTokenCredential``. Omitted in every deployed process, which then
                uses the one shared managed-identity credential; supplied by tests.
        """
        self._settings = settings
        self._caller = caller
        self._credential = credential

    async def _headers(self, correlation_id: CorrelationId) -> dict[str, str]:
        """The headers every call carries: the journey, and RagCore's own workload token.

        **The token is RagCore's, app-only, from its managed identity.** No user token is forwarded,
        and no organisation is sent — the far side recovers that from the object named. APIM
        validates the token and the workload application role, then re-derives the identity
        contract on the hop. Without it every call was refused at the gateway with a 401.

        The token is placed in a header and nowhere else: never logged, never returned.
        """
        credential = self._credential if self._credential is not None else azure_credential()
        token = await credential.get_token(self._settings.entra_scope)
        return {
            _CORRELATION_HEADER: str(correlation_id),
            "Authorization": f"Bearer {token.token}",
        }

    def _url(self, path: str, query: Mapping[str, str] | None = None) -> str:
        base = self._settings.gateway_base_url.rstrip("/")
        return f"{base}{path}?{urlencode(dict(query))}" if query else f"{base}{path}"

    async def read_catalogue(
        self, session_id: UUID, correlation_id: CorrelationId
    ) -> Mapping[str, Any]:
        """Read the capability set for the organisation owning a session.

        Args:
            session_id: The opaque session identifier. **No organisation is sent** — the far side
                recovers it from the durable session row.
            correlation_id: The journey, carried across the gateway hop.

        Returns:
            The catalogue response body.

        Raises:
            IntegrationError: When the call could not be completed. A read may be retried by the
                caller; the resilient caller has already retried transient transport failure.
        """
        request = OutboundRequest(
            method="GET",
            url=self._url(CATALOGUE_PATH, {"sessionId": str(session_id)}),
            timeout_seconds=_READ_TIMEOUT_SECONDS,
            headers=await self._headers(correlation_id),
        )
        response = await self._caller.send(SYSTEM, request)
        body = response.json()
        return body if isinstance(body, dict) else {}

    async def create_case(
        self,
        session_id: UUID,
        catalogue_id: str,
        catalogue_version: int,
        parameters: Mapping[str, object],
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> CaseOperationOutcome:
        """Create a case through the Integrations Service.

        Synchronous because the platform must know the outcome before proceeding: a session that
        cannot commit a case cannot enter Resolution Mode (specification §22.5).

        Args:
            session_id: The opaque session identifier, from which the far side recovers the
                organisation.
            catalogue_id: The capability.
            catalogue_version: Its version. Sent explicitly so the far side can refuse a mismatch
                rather than silently running whatever is current.
            parameters: The case fields, as data.
            idempotency_key: The **derived** key, so a retried write cannot double-post.
            correlation_id: The journey.

        Returns:
            The outcome, distinguishing refusal from failure.

        Raises:
            TransientIntegrationError: When the transport failed. **The caller MUST NOT re-fire a
                side-effecting call on this** — it says the transport failed and says nothing about
                whether the effect happened (ADR-0002).
        """
        request = OutboundRequest(
            method="POST",
            url=self._url(CASE_OPERATIONS_PATH),
            timeout_seconds=_WRITE_TIMEOUT_SECONDS,
            headers=await self._headers(correlation_id),
            json_body={
                "sessionId": str(session_id),
                "catalogueId": catalogue_id,
                "catalogueVersion": catalogue_version,
                "idempotencyKey": str(idempotency_key),
                "parameters": dict(parameters),
            },
        )

        try:
            response = await self._caller.send(SYSTEM, request)
        except PermanentIntegrationError:
            # A 4xx that is not 429. On this hop that means the far side APPLIED ITS RULES and said
            # no — not entitled, not registered, version mismatch, no binding. Returned as a refusal
            # rather than re-raised, because a refusal is an expected outcome the caller must handle
            # and an exception here would be caught somewhere generic and logged as a system fault.
            _log.info(
                "Integrations refused the case operation. catalogue=%s version=%d",
                catalogue_id,
                catalogue_version,
                extra={"correlationId": str(correlation_id)},
            )
            return CaseOperationOutcome(succeeded=False, external_reference=None, refused=True)
        except IntegrationError:
            # Transient. Reported outward, NEVER re-fired here: a failed authorized action requires
            # fresh human authorization (spec FR-EXEC-006).
            _log.warning(
                "Integrations case operation could not be completed",
                extra={"correlationId": str(correlation_id), "system": SYSTEM},
            )
            raise

        payload = response.json()
        body: Mapping[str, Any] = payload if isinstance(payload, dict) else {}
        reference = body.get("externalReference")
        return CaseOperationOutcome(
            succeeded=bool(body.get("succeeded", False)),
            external_reference=reference if isinstance(reference, str) else None,
            refused=False,
        )
