"""The model adapter. **Domain types on one side, the gateway seam on the other.**

Satisfies :class:`~ragcore.application.ports.ModelPort`, which the agent loop, retrieval and
ingestion all hold. Everything above this line speaks
:class:`~ragcore.domain.tenancy.TenantContext` and
:class:`~ragcore.domain.identifiers.CorrelationId`; everything below speaks
:class:`~ragcore.integrations.model.egress.ModelRequest`. Neither vocabulary crosses, which is what
keeps a provider swap from reaching the agent loop (spec FR-OPS-009).

**The adapter is a translation, not a policy.** It applies no budget, no cache, no routing and no
content safety — all four live at the AI Gateway, where they apply to every caller rather than to
the callers that remembered. What it does apply is the one rule the gateway cannot: the
organisation on the wire is the one from trusted context, so a model call is always metered against
the organisation whose work it serves.

**The output is a proposal, never an authorization** (constitution Principle III). Nothing returned
here is read as a treatment, a role or a destination, and the paths that would allow it do not
exist — governance reads the catalogue, and an outbound destination is never derived from model
output (spec FR-EXT-018).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ragcore.integrations.model.egress import ModelPurpose, ModelRequest
from ragcore.integrations.validation import as_data

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.domain.identifiers import CorrelationId
    from ragcore.domain.tenancy import TenantContext
    from ragcore.integrations.model.egress import ModelEgressPort


class GatewayModelAdapter:
    """Model access for the whole platform, routed exclusively through the AI Gateway.

    Satisfies :class:`~ragcore.application.ports.ModelPort`.

    **It takes an egress and cannot construct one.** There is no default, no lazily built client
    and no ``if`` selecting a provider: whichever egress this adapter holds was chosen in the
    composition root, which is the one module allowed to choose.
    """

    def __init__(self, egress: ModelEgressPort) -> None:
        """Bind the adapter to the egress the composition root selected.

        Args:
            egress: The AI Gateway client in every deployed environment, or the local development
                seam on a developer machine. Both are gateways as far as this class is concerned,
                and it has no way to ask which it holds.
        """
        self._egress = egress

    async def complete(
        self, tenant: TenantContext, prompt: str, correlation_id: CorrelationId
    ) -> str:
        """Produce a completion.

        Args:
            tenant: The organisation, from trusted context. What the call is metered against.
            prompt: The prompt.
            correlation_id: The journey this call belongs to.

        Returns:
            The completion — **a proposal, never an authorization**, and marked as data at the
            point it leaves this adapter.

        Raises:
            ModelBudgetExceededError: When the organisation's budget refused the call. Surfaced to
                the user as a limit, never as a failure of their request (spec FR-OPS-006).
            ModelEgressError: When the gateway could not produce a result.
        """
        response = await self._egress.send(
            ModelRequest(
                tenant_id=str(tenant.tenant_id.value),
                correlation_id=str(correlation_id),
                purpose=ModelPurpose.COMPLETION,
                input_text=prompt,
            )
        )
        return as_data(response.text)

    async def embed(self, tenant: TenantContext, text: str) -> Sequence[float]:
        """Produce an embedding.

        Routed through the gateway like every other model call. An embedding call made directly to
        a provider would be an unmetered model call, and a single egress that some calls skip is
        not a single egress.

        Args:
            tenant: The organisation, for metering.
            text: The text to embed.

        Returns:
            The vector.
        """
        response = await self._egress.send(
            ModelRequest(
                tenant_id=str(tenant.tenant_id.value),
                # An embedding is not a user journey of its own; it belongs to the organisation's
                # ingestion or retrieval work. The organisation identifier is reused rather than a
                # second identifier invented, so the gateway still meters every call.
                correlation_id=str(tenant.tenant_id.value),
                purpose=ModelPurpose.EMBEDDING,
                input_text=text,
            )
        )
        return response.embedding
