"""The model egress seam. **The only shape a model call can take in this platform.**

Every model call passes through a single brokering point and no component reaches a provider
directly (spec FR-OPS-007). That rule needs somewhere to be true, and this module is it: a
:class:`ModelEgressPort` is what :class:`~ragcore.model.adapter.GatewayModelAdapter`
holds, and the only implementations are the AI Gateway client and the local development seam. There
is no third, and a provider SDK cannot satisfy this protocol without first being written to look
like a gateway — which is a code review, not an accident.

**The request names a purpose, not a model and not a provider** (spec FR-OPS-009). Provider routing
is the gateway's job (§13.5), and a request that could name ``gpt-4o`` would make the caller a
routing decision-maker: changing provider would then mean changing every call site, which is the
coupling the gateway exists to remove. It would also make per-organisation metering unreliable,
because usage would be attributable to a model rather than to a caller.

**The request carries the organisation, and carries nothing else about the user.** The gateway
meters, budgets and throttles per organisation (spec FR-OPS-005, FR-OPS-008), which needs an
organisation identifier and needs nothing more — no principal, no roles, no session. A model egress
that knew who the user was would be a model egress that could be asked to behave differently for
some of them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from ragcore.domain.errors import DomainError


class ModelPurpose(Enum):
    """What the call is for. **The routing input the platform is allowed to supply.**

    Two members, because the platform makes two kinds of model call. A third would mean a new
    capability, which is a specification change rather than a new enum member.
    """

    COMPLETION = "completion"
    """Reasoning. The output is a **proposal**, never an authorization."""

    EMBEDDING = "embedding"
    """A vector, for retrieval. Routed through the gateway like everything else — an embedding call
    made directly would be an unmetered model call, and the gateway would be 'single' in name."""


class ModelEgressError(DomainError):
    """The gateway did not produce a usable result.

    A :class:`~ragcore.domain.errors.DomainError` rather than a transport error, so the agent loop
    handles a model failure without importing ``httpx`` — and so the provider's own exception, which
    can carry endpoint and request detail, never reaches a caller or a log line through this path.
    """


class ModelBudgetExceededError(ModelEgressError):
    """The organisation's token budget or rate limit refused this call.

    **A distinct type because it is a distinct outcome.** Where a request is throttled by a budget
    or rate limit the user MUST be told it was limited, and it MUST NOT be presented as a failure of
    their request (spec FR-OPS-006). A caller that could not tell this apart from a provider outage
    would have no way to honour that.
    """


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """One call to the gateway.

    Frozen and slotted: a request mutated between construction and send is a request whose
    organisation attribution no longer matches what was metered.

    Attributes:
        tenant_id: The organisation, for metering, budgets and throttles. From trusted context,
            never from a client, and never from model or retrieved content.
        correlation_id: The journey this call belongs to, so a metered token and a user-visible
            outcome can be joined without a second identifier.
        purpose: Completion or embedding. **Not a model name and not a provider.**
        input_text: The prompt or the text to embed.
    """

    tenant_id: str
    correlation_id: str
    purpose: ModelPurpose
    input_text: str

    def __post_init__(self) -> None:
        """Refuse a request that could not be metered or correlated.

        Raises:
            ValueError: When the organisation or correlation identifier is blank. An unattributable
                model call is an unbudgeted one, and a budget that some calls escape is not a
                budget.
        """
        if not self.tenant_id.strip():
            raise ValueError(
                "a model request carries the organisation it is metered against; it was blank"
            )
        if not self.correlation_id.strip():
            raise ValueError("a model request carries a correlation identifier; it was blank")


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """What the gateway returned.

    Attributes:
        text: The completion, for a completion call. Empty for an embedding.
        embedding: The vector, for an embedding call. Empty for a completion.
        served_from_cache: Whether the gateway answered from its semantic cache. Recorded because a
            cached response MUST be attributable and MUST NOT bypass the checks a fresh response
            passes (spec FR-OPS-010) — the attribution half is this field.
        served_by: Which egress produced it — ``ai-gateway`` or the local development seam. A
            response whose origin cannot be stated is a response nobody can reason about.
    """

    text: str = ""
    embedding: Sequence[float] = ()
    served_from_cache: bool = False
    served_by: str = "ai-gateway"


@runtime_checkable
class ModelEgressPort(Protocol):
    """The seam every model call crosses.

    Implemented by :class:`~ragcore.model.gateway.AiGatewayEgress` in every deployed
    environment and by :class:`~ragcore.model.local.LocalDevelopmentEgress` on a
    developer machine. **Both are gateways in the sense that matters**: neither the agent loop nor
    any other caller can tell them apart, so there is no configuration in which application code
    reaches a provider by a different route.
    """

    async def send(self, request: ModelRequest) -> ModelResponse:
        """Send one call through the gateway.

        Raises:
            ModelBudgetExceededError: When the organisation's budget or rate limit refused it.
            ModelEgressError: When the gateway could not produce a result.
        """
        ...
