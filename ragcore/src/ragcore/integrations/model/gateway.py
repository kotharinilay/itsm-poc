"""The AI Gateway client. **The one place this platform sends a model call.**

RagCore holds no model provider role at all — ``build/infra/identity/managed-identities.json``
grants ``id-synthia-ragcore`` no Foundry access, and says why in as many words: a Foundry role here
would be a second path to a provider that bypasses the gateway's metering, budgets and content
safety. So this client is not the *preferred* route to a model. It is the only one that works.

**Managed identity in both directions, and no key anywhere.** This process presents an Entra token
for the gateway's scope; the gateway presents its own managed identity onward to Foundry
(``build/policy/azure-identity.json``, resources ``foundry`` and ``keyvault``). There is no
``api_key``, no ``AzureKeyCredential`` and no ``OPENAI_API_KEY`` in this module, in settings, or in
any manifest — the policy names all three as forbidden configuration for this resource, and the
security tests enforce it against this source.

**What the gateway does that this client deliberately does not.** Provider routing, per-organisation
token metering in provider-neutral units, budgets and throttles, semantic cache, and bidirectional
content safety all live in ``build/infra/ai-gateway/policy.xml``. None of them is implemented here,
and that is not laziness: a budget enforced by the caller is a budget the caller can decline to
enforce. This client supplies the two things the gateway needs in order to apply them — the
organisation and the correlation — and consumes the result.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from ragcore.infrastructure.azure_credentials import azure_credential
from ragcore.integrations.http import (
    IntegrationError,
    OutboundRequest,
    PermanentIntegrationError,
    ResilientHttpCaller,
)
from ragcore.integrations.model.egress import (
    ModelBudgetExceededError,
    ModelEgressError,
    ModelPurpose,
    ModelRequest,
    ModelResponse,
)
from ragcore.integrations.validation import require_object, require_text

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.settings import ModelGatewaySettings

_log: Final = logging.getLogger(__name__)

SYSTEM: Final = "ai-gateway"
"""The pool name and the name this integration is known by in errors and telemetry."""

TENANT_HEADER: Final = "X-Synthia-Organisation"
"""The counter key the gateway meters, budgets and throttles on.

Named as a header rather than carried in the body because the gateway's policies read it before the
body is parsed — a budget that could only be applied after deserialising a prompt would have already
paid for the prompt.
"""

CORRELATION_HEADER: Final = "X-Correlation-Id"
"""The journey a metered token belongs to (spec FR-OPS-001)."""


class GatewayNotConfiguredError(ModelEgressError):
    """No gateway is configured, and no provider is going to be reached instead.

    Fails closed and says so. The tempting alternative — fall back to a provider endpoint when the
    gateway is absent — is the single-egress rule with an ``except`` clause, and it would be
    exercised on exactly the deployment where nobody checked.
    """


class AiGatewayEgress:
    """Sends model calls to the AI Gateway as this process's managed identity.

    Satisfies :class:`~ragcore.integrations.model.egress.ModelEgressPort`.

    **This class knows no provider.** It has no model name, no deployment name, no provider base
    URL and no branch on any of them. What it posts is a purpose, an organisation and some text;
    what comes back is a result the gateway has already metered and content-checked.
    """

    def __init__(
        self,
        settings: ModelGatewaySettings,
        caller: ResilientHttpCaller,
        credential: Any | None = None,  # noqa: ANN401 — the concrete type needs the SDK imported
    ) -> None:
        """Bind the client to a gateway.

        Args:
            settings: The gateway settings. There is deliberately no key field to pass.
            caller: The shared resilient HTTP caller. Not an ``AsyncClient`` — a client built here
                would be one this process pools nowhere and times out by its own rules.
            credential: The Azure credential. The shared process credential when omitted; supplied
                by a test so the token path is exercised without an Azure sign-in.
        """
        self._settings = settings
        self._caller = caller
        self._credential = credential

    async def send(self, request: ModelRequest) -> ModelResponse:
        """Send one model call through the gateway.

        Args:
            request: The call. Carries the organisation it is metered against.

        Returns:
            The gateway's response.

        Raises:
            GatewayNotConfiguredError: When no gateway base URL is configured.
            ModelBudgetExceededError: When the organisation's budget or rate limit refused it —
                distinct from a failure, because a throttle MUST NOT be presented to the user as a
                failure of their request (spec FR-OPS-006).
            ModelEgressError: When the gateway could not produce a usable result.
        """
        base_url = self._settings.base_url.strip().rstrip("/")

        if not base_url:
            raise GatewayNotConfiguredError(
                "No AI Gateway is configured. Set SYNTHIA_GATEWAY_BASE_URL. There is no provider "
                "endpoint to fall back to: the gateway is the platform's only model egress, and a "
                "fallback would bypass metering, budgets and content safety."
            )

        outbound = OutboundRequest(
            method="POST",
            url=f"{base_url}/{request.purpose.value}",
            timeout_seconds=self._settings.request_timeout_seconds,
            headers=await self._headers(request),
            json_body={"input": request.input_text},
        )

        try:
            response = await self._caller.send(SYSTEM, outbound)
        except PermanentIntegrationError as error:
            # 403 is how `llm-token-limit` reports an exhausted quota and 429 how it reports an
            # exceeded rate; the latter is classified transient and has already been retried.
            if "403" in str(error):
                raise ModelBudgetExceededError(
                    "the organisation's model budget refused this call"
                ) from None
            raise ModelEgressError("the AI Gateway refused this call") from None
        except IntegrationError:
            # The transport error is not chained: it can carry the gateway URL and response detail,
            # and this exception reaches the agent loop and the logs.
            raise ModelEgressError("the AI Gateway did not respond") from None

        return self._read(request.purpose, response.json())

    async def _headers(self, request: ModelRequest) -> dict[str, str]:
        """The headers the gateway's policies read.

        The organisation and the correlation are headers rather than body fields because the
        metering, budget and throttle policies run before the body is deserialised.
        """
        headers = {
            TENANT_HEADER: request.tenant_id,
            CORRELATION_HEADER: request.correlation_id,
            "Content-Type": "application/json",
        }

        scope = self._settings.entra_scope.strip()
        if scope:
            credential = self._credential if self._credential is not None else azure_credential()
            token = await credential.get_token(scope)
            headers["Authorization"] = f"Bearer {token.token}"

        return headers

    def _read(self, purpose: ModelPurpose, payload: object) -> ModelResponse:
        """Validate and read the gateway's response.

        Checked at the boundary rather than trusted: the gateway is platform-owned, but what it
        returns has passed through a provider, and a provider contract change is exactly the
        malformed output FR-EXT-021 refuses.

        Raises:
            BoundaryValidationError: When the response does not match its contract.
        """
        body = require_object(SYSTEM, payload)
        served_from_cache = body.get("servedFromCache") is True

        if served_from_cache:
            # Attribution, not suppression. A cached response is a legitimate answer; what
            # FR-OPS-010 requires is that it be attributable and not bypass the checks a fresh
            # response passes — the latter is the gateway's ordering, which applies content safety
            # to a cache hit as it does to a completion.
            _log.debug("The AI Gateway served this call from its semantic cache.")

        if purpose is ModelPurpose.COMPLETION:
            return ModelResponse(
                text=require_text(SYSTEM, body, "output"),
                served_from_cache=served_from_cache,
            )

        vector = body.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ModelEgressError("the AI Gateway returned no embedding for an embedding call")
        if not all(isinstance(value, int | float) for value in vector):
            raise ModelEgressError("the AI Gateway returned a non-numeric embedding")

        return ModelResponse(
            embedding=[float(value) for value in vector],
            served_from_cache=served_from_cache,
        )
