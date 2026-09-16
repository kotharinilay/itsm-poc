"""Model access. **The AI Gateway is the single egress, and this package is the only door to it.**

    RagCore → AI Gateway → model provider

Never ``RagCore → Azure OpenAI`` and never ``RagCore → Foundry``. The rule is enforced in four
independent places, which is what makes it a property rather than a convention:

1. **Identity.** ``id-synthia-ragcore`` holds no Foundry role assignment at all
   (``build/infra/identity/managed-identities.json``). A direct provider call would fail to
   authenticate even if the code existed.
2. **Type.** :class:`~ragcore.integrations.model.egress.ModelEgressPort` is what the adapter holds,
   and the only implementations are the gateway client and the local development seam.
3. **Test.** ``ragcore/tests/architecture/test_no_direct_model_call.py`` asserts that no module
   outside this package names a provider SDK, a provider endpoint or a model deployment.
4. **Configuration.** ``ModelGatewaySettings`` has no ``provider``, no ``api_key`` and no
   ``model_endpoint`` field, and ``build/policy/azure-identity.json`` names all three as forbidden
   for the ``foundry`` resource.

The local development seam (:mod:`ragcore.integrations.model.local`) exists so that the first of
those is never weakened for convenience: a developer without a gateway gets a gateway-shaped
substitute that calls no model, rather than a provider client behind an environment branch.
"""

from __future__ import annotations

from ragcore.integrations.model.adapter import GatewayModelAdapter
from ragcore.integrations.model.egress import (
    ModelBudgetExceededError,
    ModelEgressError,
    ModelEgressPort,
    ModelPurpose,
    ModelRequest,
    ModelResponse,
)
from ragcore.integrations.model.gateway import AiGatewayEgress, GatewayNotConfiguredError
from ragcore.integrations.model.local import LocalDevelopmentEgress

__all__ = [
    "AiGatewayEgress",
    "GatewayModelAdapter",
    "GatewayNotConfiguredError",
    "LocalDevelopmentEgress",
    "ModelBudgetExceededError",
    "ModelEgressError",
    "ModelEgressPort",
    "ModelPurpose",
    "ModelRequest",
    "ModelResponse",
]
