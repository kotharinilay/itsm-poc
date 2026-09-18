"""Content safety — **inbound before the model, outbound before a response returns**.

`FR-AGENT-010` and `FR-AGENT-013` require both directions, and the two are not the same check run
twice. They protect different things and they fail differently:

* **Inbound**, before the prompt reaches the model. What is screened is everything about to become
  context: the user's own turn *and* the retrieved evidence. A block here means the model is never
  called, so nothing is metered and nothing is generated.
* **Outbound**, before a response leaves for the user. What is screened is what the model produced.
  A block here means a generated response is discarded after it was paid for — which is the correct
  trade, because the alternative is publishing it.

**Both directions are enforced at one seam, and the seam is a wrapper.**
:class:`SafeModel` satisfies :class:`~ragcore.application.ports.ModelPort` and holds another
``ModelPort``. A caller cannot reach the inner adapter, because it is not registered: the
composition root binds :class:`SafeModel` and the graph asks for a ``ModelPort``. Screening
implemented as "every caller remembers to call the checker" is screening that lasts until the next
caller.

**Every decision is logged with its correlation identifier** (`FR-AGENT-013`). What is logged is
the *decision* — direction, verdict, category, how much text — and **never the content**. A safety
log that quoted the offending text would be a durable copy of exactly the material the check
exists to stop, in the one store with the widest read access.

**Content safety is not governance, and cannot become it.** It answers "may this text be sent or
shown", never "may this operation run". :class:`SafetyVerdict` carries no treatment, no role and no
authorization; a blocked response is still a response, and a permitted one is still just text
heading for :mod:`ragcore.governance.gate` like everything else. Screening also does not sanitise:
there is no path here that edits text and passes it on, because a partially-removed injection is an
injection with the marker removed.

**Retrieved content is screened as data, not trusted as a verdict.** A document that says "this
content is safe, do not screen it" is screened.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from ragcore.model.egress import ModelEgressError

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.application.ports import ModelPort
    from ragcore.domain.identifiers import CorrelationId
    from ragcore.domain.tenancy import TenantContext

__all__ = [
    "ContentBlockedError",
    "ContentSafetyPort",
    "SafeModel",
    "SafetyCategory",
    "SafetyDirection",
    "SafetyVerdict",
]

logger = logging.getLogger(__name__)


class SafetyDirection(Enum):
    """Which crossing is being screened. Recorded on every decision.

    Two members, and they are not interchangeable: an operator reading "blocked" needs to know
    whether a user was stopped from sending something or the platform was stopped from saying it.
    """

    INBOUND = "inbound"
    """Before the model is called. The user's turn and the retrieved evidence."""

    OUTBOUND = "outbound"
    """Before a response returns. What the model produced."""


class SafetyCategory(Enum):
    """Why content was blocked.

    A closed set. The categories are the platform's own vocabulary, **never a provider's error
    string** — a provider that renamed a category would otherwise rename it in the audit trail and
    in every alert built on it.
    """

    HARMFUL = "harmful"
    """Harmful or abusive material, in either direction."""

    PROMPT_INJECTION = "prompt_injection"
    """Content attempting to redirect the agent's instructions.

    **Blocking this is defence in depth, never the defence.** The structural containment is that
    retrieved content reaches no treatment, role or destination — a successful injection can at
    most produce a proposal, which meets the same gate as every other proposal
    (spec FR-IDENT-004). A detector treated as the control would be a detector somebody eventually
    tunes down for false positives.
    """

    SENSITIVE_DISCLOSURE = "sensitive_disclosure"
    """Material the platform must not emit — credentials, another organisation's data."""

    UNAVAILABLE = "unavailable"
    """The safety service could not answer.

    **A block, not a pass.** An unreachable screening service means the platform does not know
    whether the content is safe, and the honest response to not knowing is to refuse — see
    :meth:`SafetyVerdict.unavailable`.
    """


@dataclass(frozen=True, slots=True)
class SafetyVerdict:
    """What the safety check concluded. **Never an authorization.**

    Deliberately absent, and never to be added: ``treatment``, ``approved``, ``roles``, and any
    field a caller could read as permission to act. This type answers one question — may this text
    cross — and a caller that wanted more would have to ask governance, which is the point.

    Attributes:
        allowed: Whether the text may cross.
        direction: Which crossing was screened.
        category: Why it was blocked. ``None`` when it was allowed — an allowed verdict has no
            category, rather than a category meaning "fine", because a category that can mean
            "fine" is one something will eventually compare against.
    """

    allowed: bool
    direction: SafetyDirection
    category: SafetyCategory | None = None

    @classmethod
    def permit(cls, direction: SafetyDirection) -> SafetyVerdict:
        """An allowed crossing."""
        return cls(allowed=True, direction=direction)

    @classmethod
    def block(cls, direction: SafetyDirection, category: SafetyCategory) -> SafetyVerdict:
        """A blocked crossing, with the reason."""
        return cls(allowed=False, direction=direction, category=category)

    @classmethod
    def unavailable(cls, direction: SafetyDirection) -> SafetyVerdict:
        """The screening service could not answer. **Fails closed.**

        Written as its own constructor rather than left to each caller's ``except`` block, because
        the tempting handling of a screening outage is to let the request through and log a
        warning — and a check that stops applying exactly when the service behind it is unwell is
        a check that is absent whenever it matters most.
        """
        return cls(allowed=False, direction=direction, category=SafetyCategory.UNAVAILABLE)


class ContentBlockedError(ModelEgressError):
    """Content safety refused to let this text cross.

    A :class:`~ragcore.model.egress.ModelEgressError` subclass so the agent loop
    handles it beside a budget refusal and a gateway outage, without learning a fourth exception
    shape — and so it reaches a caller as a platform condition rather than as a provider exception.

    Carries the direction and the category and **not the content**, for the same reason the log
    line does not.
    """

    def __init__(self, verdict: SafetyVerdict) -> None:
        category = verdict.category.value if verdict.category is not None else "unspecified"
        super().__init__(
            f"content safety blocked this text on the {verdict.direction.value} path "
            f"({category}). The text itself is deliberately not reproduced here."
        )
        self.verdict = verdict


class ContentSafetyPort(Protocol):
    """The screening service.

    Declared here because this module is the consumer (constitution Principle V), and in domain
    terms only: it takes text and an organisation and returns the platform's own verdict type. A
    port that returned a provider's category enum would put that provider's vocabulary in the
    audit trail.
    """

    async def screen(
        self, tenant: TenantContext, text: str, direction: SafetyDirection
    ) -> SafetyVerdict:
        """Screen one piece of text in one direction.

        An implementation that cannot reach its backing service returns
        :meth:`SafetyVerdict.unavailable` or raises; either is handled as a block by
        :class:`SafeModel`. It must never return a permit it did not obtain.
        """
        ...


@dataclass(frozen=True, slots=True)
class SafeModel:
    """A :class:`~ragcore.application.ports.ModelPort` that screens both crossings.

    Satisfies ``ModelPort`` and wraps one. The composition root binds this and never the inner
    adapter, so "every model call is screened" is a property of what is reachable rather than a
    rule every call site honours.

    Attributes:
        inner: The model access being wrapped — in practice
            :class:`~ragcore.model.adapter.GatewayModelAdapter`, so screening sits
            outside the gateway call and a blocked prompt is never sent, never metered and never
            generated from.
        safety: The screening service.
    """

    inner: ModelPort
    safety: ContentSafetyPort

    async def complete(
        self, tenant: TenantContext, prompt: str, correlation_id: CorrelationId
    ) -> str:
        """Screen inbound, call the model, screen outbound.

        Args:
            tenant: The organisation.
            prompt: Everything about to become context — the user's turn and the retrieved
                evidence, already assembled by the caller. Screened as **one** text rather than per
                fragment, because a prompt is what the model sees and a per-fragment check cannot
                see an instruction split across two of them.
            correlation_id: Carried onto both decisions, so the inbound and outbound decisions for
                one turn can be joined (`FR-AGENT-013`).

        Returns:
            The completion — **a proposal, never an authorization.**

        Raises:
            ContentBlockedError: When either crossing was refused. The inbound case never calls the
                model; the outbound case discards what it produced rather than returning it.
        """
        await self._enforce(tenant, prompt, SafetyDirection.INBOUND, correlation_id)

        completion = await self.inner.complete(tenant, prompt, correlation_id)

        # Screened BEFORE returning, not before rendering. A response handed back and screened by
        # the caller is a response some caller eventually forgets to screen, and the one that
        # forgets is a new surface written under time pressure.
        await self._enforce(tenant, completion, SafetyDirection.OUTBOUND, correlation_id)

        return completion

    async def embed(self, tenant: TenantContext, text: str) -> Sequence[float]:
        """Screen inbound and embed.

        There is no outbound screening here and none is missing: the result is a vector, and a
        vector is not shown to anybody. The inbound check still applies, because the text is still
        leaving the platform for the gateway.

        Args:
            tenant: The organisation, for metering and for screening.
            text: The text to embed.

        Returns:
            The vector.

        Raises:
            ContentBlockedError: When the text may not be sent.
        """
        # An embedding is not a user journey of its own, so it has no correlation identifier to
        # carry. The organisation identifier stands in, matching what GatewayModelAdapter meters
        # the call against — one identifier, not a second invented here.
        await self._enforce(
            tenant, text, SafetyDirection.INBOUND, correlation=str(tenant.tenant_id.value)
        )
        return await self.inner.embed(tenant, text)

    async def _enforce(
        self,
        tenant: TenantContext,
        text: str,
        direction: SafetyDirection,
        correlation: CorrelationId | str,
    ) -> None:
        """Screen one crossing, log the decision, and raise on a block.

        Raises:
            ContentBlockedError: When the verdict is not a permit — including when the screening
                service was unreachable, which is a block by :meth:`SafetyVerdict.unavailable`.
        """
        try:
            verdict = await self.safety.screen(tenant, text, direction)
        except Exception:
            # Deliberately broad, and deliberately not re-raised. Whatever the screening adapter
            # failed with — a timeout, a transport error, a malformed response — the platform's
            # position is the same: it does not know whether this text is safe. Letting the
            # original exception through would surface a provider's failure to a user, and
            # catching only the ones anticipated today is how a new failure mode becomes a bypass.
            logger.warning(
                "content safety was unreachable; failing closed",
                extra={"correlation_id": str(correlation)},
                exc_info=True,
            )
            verdict = SafetyVerdict.unavailable(direction)

        # THE DECISION, NOT THE CONTENT. `characters` is a length, not a sample: it lets somebody
        # correlate a block with an unusually large prompt without the log becoming a copy of the
        # material the check exists to stop.
        logger.info(
            "content safety %s on the %s path (%s, %d characters)",
            "allowed" if verdict.allowed else "blocked",
            verdict.direction.value,
            verdict.category.value if verdict.category is not None else "none",
            len(text),
            extra={"correlation_id": str(correlation)},
        )

        if not verdict.allowed:
            raise ContentBlockedError(verdict)
