"""The authority boundary, stated as a total function over every source the platform reads.

**MODEL MAY PROPOSE. MODEL MAY NOT AUTHORIZE.**

Prose cannot be tested. This module turns the rule into two closed enumerations and one total
function over their union, so ``tests/governance/test_authority_boundary.py`` can assert the
answer for every source that exists — including any added later, because a new member of either
enum that the function does not handle fails the exhaustiveness test rather than silently
defaulting.

The distinction being drawn is **not** trustworthiness. The operation catalogue and a staff
verdict are authority-bearing; retrieved content and model output are not. That is a statement
about *where a decision may come from*, not about how reliable a source is. A perfectly accurate
model is still not an authorization, and a compromised catalogue is still where treatment comes
from — which is why the catalogue is protected by schema constraints and separated database
principals rather than by being doubted at the call site.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class UntrustedContent(Enum):
    """Content classes that MUST NEVER confer authority of any kind (spec FR-IDENT-003, -004).

    Enumerated as a type so the prohibition can be asserted against a list rather than argued
    from prose. Every member is content the platform reads, uses and cites — and never obeys.

    A successful prompt injection in any of these can, at most, produce a bad **proposal**.
    The gate that follows does not read them.
    """

    MODEL_OUTPUT = "model_output"
    """Anything the model generated, including tool-call arguments it chose."""

    RETRIEVED_CONTENT = "retrieved_content"
    """Chunks from the derived index. Grounding evidence, never instruction."""

    VENDOR_RESPONSE = "vendor_response"
    """Output fetched from an external or MCP system. Data, never instruction."""

    CHAT_TEXT = "chat_text"
    """Anything a human typed into the conversation, including 'yes, go ahead'."""

    REALTIME_MESSAGE = "realtime_message"
    """Anything arriving on the notification channel. A leaf, never a link."""

    TRIGGER_MESSAGE = "trigger_message"
    """A Service Bus trigger. Causes work to happen; carries no authority to do it."""


class AuthoritySource(Enum):
    """The only sources from which authority may be read.

    Every member is either a durable platform record or an authenticated human decision that
    arrived on a RagCore API (ADR-0002). Nothing here is content, and nothing here is anything a
    client sent as a field.
    """

    GATEWAY_DERIVED_IDENTITY = "gateway_derived_identity"
    """The closed header contract, derived once at APIM.

    Establishes *who is acting*, never *what may be done*.
    """

    TENANT_REGISTRY = "tenant_registry"
    """Registry state. The other half of tenant admission, and the only half that is stored."""

    OPERATION_CATALOGUE = "operation_catalogue"
    """The canonical catalogue. The sole origin of an execution treatment."""

    DURABLE_WORK_RECORD = "durable_work_record"
    """The work item. Every trigger is untrusted; this is what the consumer reads instead."""

    AUTHENTICATED_STAFF_VERDICT = "authenticated_staff_verdict"
    """A verdict recorded through ``POST /api/staff/v1/approvals/{id}/verdict``."""

    AUTHENTICATED_END_USER_CONSENT = "authenticated_end_user_consent"
    """A consent recorded through ``POST /api/customer/v1/work/{id}/consent``."""


AUTHORITY_SOURCES: Final[frozenset[AuthoritySource]] = frozenset(AuthoritySource)
"""Closed set. Adding a member is an architectural change, not an implementation detail."""

NON_AUTHORITY_SOURCES: Final[frozenset[UntrustedContent]] = frozenset(UntrustedContent)
"""Closed set. Every member is read, used and cited — and never obeyed."""


def may_grant_authority(source: AuthoritySource | UntrustedContent) -> bool:
    """Whether a decision may be read from ``source``.

    Total over the union of both enumerations, with no ``else`` branch and no default: a source
    that is neither is a :class:`TypeError`, not a ``False`` that quietly absorbs a new content
    class as merely unauthorized.

    Args:
        source: The origin of a claim the caller is considering acting on.

    Returns:
        ``True`` only for an :class:`AuthoritySource`.

    Raises:
        TypeError: When ``source`` belongs to neither enumeration.
    """
    if isinstance(source, AuthoritySource):
        return True
    if isinstance(source, UntrustedContent):
        return False
    raise TypeError(
        f"{source!r} is neither an AuthoritySource nor an UntrustedContent. Every source the "
        "platform reads must be classified before anything acts on it."
    )


class AuthorityAssertionError(Exception):
    """Raised when code attempted to read authority from a source that cannot grant it.

    Not a :class:`~ragcore.domain.errors.DomainError`: this is a defect in the platform, not a
    condition a user produced, and it MUST NOT be mapped to a problem-details response and shown
    to somebody as though they had done something wrong.
    """


def require_authority_source(source: AuthoritySource | UntrustedContent) -> AuthoritySource:
    """Narrow ``source`` to an authority-bearing one, or refuse.

    The call site for code that is about to act on a decision and wants the boundary asserted at
    the point of use rather than reasoned about in review.

    Args:
        source: The origin of the decision.

    Returns:
        ``source``, narrowed to :class:`AuthoritySource`.

    Raises:
        AuthorityAssertionError: When the source cannot grant authority.
        TypeError: When ``source`` belongs to neither enumeration.
    """
    if isinstance(source, AuthoritySource):
        return source
    if isinstance(source, UntrustedContent):
        raise AuthorityAssertionError(
            f"{source} cannot grant authority. Retrieved content, fetched or vendor content, "
            "model output and chat text are data — a decision read from any of them is not a "
            "decision (A3 §6.3, spec FR-IDENT-003, FR-IDENT-004)."
        )
    raise TypeError(f"{source!r} is neither an AuthoritySource nor an UntrustedContent.")
