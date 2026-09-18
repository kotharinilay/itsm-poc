"""The local development seam. **A gateway substitute, never a provider shortcut.**

A developer without an AI Gateway needs the process to start and the graph to run. There are two
ways to give them that, and only one of them is safe.

The unsafe one is a provider client behind ``if environment == "local"``. It works immediately, and
it puts a second model egress in the codebase — one with a provider endpoint in it, one an
application-layer caller could reach, and one that ships, because the branch that selects it is
configuration and configuration differs per environment. The single-egress rule then holds
everywhere except the environment where the code was written.

The safe one is this: a second implementation of
:class:`~ragcore.model.egress.ModelEgressPort` that **is not a model client at all**.
It reaches no provider, holds no endpoint and needs no credential. Application code cannot tell it
from the gateway, which is the point — there is no configuration in which a caller bypasses the
seam, because there is nothing on the other side of the seam to bypass it to.

**It refuses to be constructed outside local development.** Not because the environment name is an
authority — it is not, and no decision in this platform turns on it — but because this class
answers model calls without a model, and a deployment that silently used it would be a deployment
producing placeholder text and metering nothing. The constructor check is what turns that from a
quiet degradation into a container that does not start.

**What it returns is honest** (constitution Principle IX). The text says plainly that no model was
called and the embedding is a deterministic hash-derived vector, not a semantic one. A plausible
sentence and a random vector would let a developer build against behaviour that does not exist, and
retrieval quality measured against noise is worse than no measurement.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Final

from ragcore.model.egress import (
    ModelEgressError,
    ModelPurpose,
    ModelRequest,
    ModelResponse,
)

_log: Final = logging.getLogger(__name__)

SERVED_BY: Final = "local-development-seam"
"""What every response from this class is stamped with, so its origin is never in doubt."""

EMBEDDING_DIMENSIONS: Final = 16
"""Deliberately far too few to be mistaken for a real embedding.

A 1536-dimension vector of noise looks like an embedding in every log, dashboard and debugger. A
sixteen-dimension one announces itself the moment anybody looks.
"""

PLACEHOLDER_COMPLETION: Final = (
    "[local development seam] No model was called. This process has no AI Gateway configured, "
    "and RagCore reaches no model provider directly — the gateway is the platform's single model "
    "egress. Configure SYNTHIA_GATEWAY_BASE_URL to exercise a real completion."
)
"""What a completion returns. It states what happened rather than imitating a model."""


class LocalDevelopmentEgress:
    """A gateway-shaped stand-in for a developer machine. **It calls no model.**

    Satisfies :class:`~ragcore.model.egress.ModelEgressPort`, and satisfying it is the
    entire contribution: application code, the agent loop and every adapter continue to hold a
    :class:`~ragcore.application.ports.ModelPort` backed by an egress, so no code path exists that
    would reach a provider when the gateway is absent.
    """

    def __init__(self, *, environment: str) -> None:
        """Construct the seam, refusing any environment but local.

        Args:
            environment: The validated environment name from settings.

        Raises:
            ModelEgressError: When ``environment`` is anything other than ``local``. A deployed
                process that fell back to this would answer without a model, meter nothing and look
                entirely healthy while doing it.
        """
        if environment != "local":
            raise ModelEgressError(
                f"the local development model seam cannot be used in the {environment!r} "
                "environment. It calls no model and meters nothing; a deployed process must reach "
                "the AI Gateway. Configure SYNTHIA_GATEWAY_BASE_URL."
            )

        self._environment = environment
        _log.warning(
            "Model calls are served by the local development seam. NO MODEL IS CALLED and no "
            "tokens are metered; completions are placeholder text and embeddings are deterministic "
            "hashes. Configure SYNTHIA_GATEWAY_BASE_URL to reach the AI Gateway."
        )

    async def send(self, request: ModelRequest) -> ModelResponse:
        """Answer a model call without calling a model.

        Args:
            request: The call, validated exactly as the gateway would validate it — so a call site
                that omits the organisation fails on a laptop rather than in staging.

        Returns:
            A response stamped :data:`SERVED_BY`, never ``ai-gateway``.
        """
        if request.purpose is ModelPurpose.COMPLETION:
            return ModelResponse(text=PLACEHOLDER_COMPLETION, served_by=SERVED_BY)

        return ModelResponse(
            embedding=_deterministic_vector(request.input_text), served_by=SERVED_BY
        )


def _deterministic_vector(text: str) -> list[float]:
    """A stable vector derived from the text by hashing.

    Deterministic so that the same input embeds identically across runs — which is what makes a
    retrieval test repeatable. It carries **no semantic information**: two texts meaning the same
    thing land nowhere near each other, and nothing should be concluded from a similarity score
    computed over these.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[index] / 255.0 for index in range(EMBEDDING_DIMENSIONS)]
