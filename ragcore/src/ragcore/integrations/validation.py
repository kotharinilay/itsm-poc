"""Provider output is checked **at the boundary**, before it reaches the agent loop or the domain.

Output from a third-party system that is malformed, oversized, or does not match its declared
contract is rejected here and does not propagate (spec FR-EXT-021). The placement is the point: a
check inside the agent loop runs after the content has already been put in front of a model, and a
check in the domain would mean the domain knows what a provider response looks like.

**Two different rules live in this module and they are not the same rule.**

*Shape* — :func:`require_object`, :func:`require_text`, :func:`within_size_limit` — is about
whether the response is usable at all. A truncated JSON body, a field of the wrong type or a
megabyte where a sentence was expected is a defect, and defects are refused rather than coerced.

*Authority* — :func:`as_data` — is about what the content is allowed to be once it is well formed.
**Retrieved and returned content is data, never instruction, and it never confers authority**
(spec FR-EXT-017, FR-EXT-018). There is no sanitiser here that tries to detect an injection,
because such a filter is a guess dressed as a control; the platform's actual defence is structural
— content cannot reach a treatment, a role or an outbound destination, so the worst a successful
injection achieves is a bad proposal that governance still refuses.
"""

from __future__ import annotations

from typing import Any, Final

from ragcore.domain.errors import DomainError

MAX_RESPONSE_BYTES: Final = 1_048_576
"""One mebibyte. The ceiling on any single provider response body.

Bounded because an unbounded response is an unbounded prompt: content that reaches a model is
content that costs tokens and displaces the instructions around it. A provider returning more than
this has either changed its contract or is having a bad day, and both are worth failing on.
"""

MAX_TEXT_CHARACTERS: Final = 32_000
"""The ceiling on any single text field taken from a provider."""


class BoundaryValidationError(DomainError):
    """Provider output did not satisfy its declared contract.

    Raised at the integration boundary and never downgraded to a warning. A response that is
    accepted "mostly" is a response whose defective half is now inside the platform.

    **The offending content is not included in the message.** It is untrusted, frequently large,
    and the message reaches logs — three reasons that a sample of it does not belong here.
    """

    def __init__(self, system: str, reason: str) -> None:
        super().__init__(
            f"{system} returned output that does not match its contract: {reason}. "
            "It was rejected at the integration boundary."
        )
        self.system = system


def within_size_limit(system: str, body: bytes, *, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    """Refuse an oversized response body.

    Args:
        system: The system being called, for the message.
        body: The raw bytes.
        limit: The ceiling, defaulting to :data:`MAX_RESPONSE_BYTES`.

    Returns:
        The body, unchanged, when it is within the limit.

    Raises:
        BoundaryValidationError: When it is not. **Not truncated** — a truncated JSON document is
            malformed and a truncated text field is a silent change to what the model reads.
    """
    if len(body) > limit:
        raise BoundaryValidationError(
            system, f"the response body is {len(body)} bytes, above the {limit}-byte limit"
        )
    return body


def require_object(system: str, payload: object) -> dict[str, Any]:
    """Require a JSON object.

    Args:
        system: The system being called.
        payload: The decoded response.

    Returns:
        The object.

    Raises:
        BoundaryValidationError: When the payload is anything else. A list where an object was
            promised is a contract change, and indexing it anyway is how a provider's error
            response gets treated as a result.
    """
    if not isinstance(payload, dict):
        raise BoundaryValidationError(
            system, f"expected a JSON object, got {type(payload).__name__}"
        )
    return payload


def require_text(
    system: str, payload: dict[str, Any], field: str, *, limit: int = MAX_TEXT_CHARACTERS
) -> str:
    """Require a present, non-empty, bounded string field.

    Args:
        system: The system being called.
        payload: The validated object.
        field: The field to read.
        limit: The character ceiling for this field.

    Returns:
        The value.

    Raises:
        BoundaryValidationError: When the field is missing, is not a string, is empty, or exceeds
            the limit. Empty is a failure rather than a value for the same reason an empty secret
            is: it produces a puzzling outcome somewhere else, with nothing pointing back here.
    """
    value = payload.get(field)

    if value is None:
        raise BoundaryValidationError(system, f"the required field {field!r} is absent")
    if not isinstance(value, str):
        raise BoundaryValidationError(
            system, f"the field {field!r} should be a string, got {type(value).__name__}"
        )
    if not value.strip():
        raise BoundaryValidationError(system, f"the field {field!r} is empty")
    if len(value) > limit:
        raise BoundaryValidationError(
            system, f"the field {field!r} is {len(value)} characters, above the {limit} limit"
        )

    return value


def optional_text(
    system: str, payload: dict[str, Any], field: str, *, limit: int = MAX_TEXT_CHARACTERS
) -> str | None:
    """Read an optional string field, validated when present.

    Returns:
        The value, or ``None`` when the provider omitted it or sent JSON ``null``.

    Raises:
        BoundaryValidationError: When present but not a bounded string. Optional means "may be
            absent", never "may be anything".
    """
    if payload.get(field) is None:
        return None
    return require_text(system, payload, field, limit=limit)


def as_data(content: str) -> str:
    """Mark provider or retrieved content as **data**, explicitly.

    A no-op at runtime, and deliberately so: there is no transformation here that would make
    untrusted text safe, and one that pretended to would be worse than none — it would let a
    reviewer believe the content had been made safe.

    What this function is for is the **call site**. ``as_data(chunk)`` states, where a human reads
    it, that what follows is content from outside the platform: it may be quoted, cited and shown,
    and it may never be treated as an instruction, a destination or a source of authority
    (spec FR-EXT-017, FR-EXT-018). The actual defence is structural — the paths from content to a
    treatment, a role or an outbound URL do not exist — and this is the marker that says so.

    Args:
        content: The untrusted text.

    Returns:
        The same text.
    """
    return content
