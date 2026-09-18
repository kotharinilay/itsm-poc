"""Result normalization. **Provider output is data, and it is checked before it travels.**

Spec `FR-EXT-017`, `FR-EXT-021`, `FR-INTEG-023`. Output returned by a third-party system MUST be
treated as data: it MUST NOT become an instruction, a destination, an identity, an organisation or a
source of authority. Output that is malformed, oversized or off-contract is **rejected at the
boundary** rather than passed inward.

**Why rejection rather than best-effort parsing.** A vendor that returns something unexpected has
either changed its contract or been compromised, and both cases want the same answer: stop, record,
escalate. Salvaging what parses turns the second case into a quiet success — the platform proceeds
on an attacker's payload because most of the fields still looked right.

**What is deliberately dropped, not carried:**

* any field naming a URL, host or endpoint — a destination comes from the connector registry and
  from nowhere else (`FR-EXT-018`);
* any field that looks like a credential — a vendor echoing one back must not put it in a durable
  execution record;
* any key the contract does not name.

Dropping rather than rejecting on the last one is a deliberate asymmetry: a vendor **adding** a
field is ordinary API evolution, while a vendor **omitting** a required one or exceeding the size
bound is not.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping

__all__ = [
    "BoundaryValidationError",
    "NormalizedProfile",
    "NormalizedResult",
    "normalize_case_result",
    "normalize_directory_profile",
    "normalize_tool_result",
]

# Sized to hold a case record with generous room, and small enough that a runaway vendor response
# cannot become a multi-megabyte row in an append-only execution record.
_MAX_PAYLOAD_BYTES: Final = 64 * 1024

# Keys the case contract names. Anything else is dropped.
_CASE_FIELDS: Final = frozenset({"number", "sys_id", "state", "short_description", "opened_at"})

_EXTERNAL_REFERENCE_KEYS: Final = ("number", "sys_id")

# Directory field bounds. Graph's own limits, restated here because a boundary that trusted the far
# side to enforce its documented maximums would be trusting the thing it exists to check.
_DISPLAY_NAME_LIMIT: Final = 256
_MAIL_LIMIT: Final = 320

# Field names that plausibly carry a credential or a destination. Matched on the KEY, because the
# value's shape is not reliably distinguishable and a value-based scan would drop legitimate text.
_FORBIDDEN_KEY = re.compile(
    r"(password|secret|token|credential|api[_-]?key|authorization|endpoint|url|uri|host)",
    re.IGNORECASE,
)


class BoundaryValidationError(Exception):
    """Provider output did not satisfy its contract.

    Carries **no payload fragment**. This exception is the thing most likely to be logged, and the
    output that triggered it is exactly the output not to be trusted in a log line.
    """


@dataclass(frozen=True, slots=True)
class NormalizedResult:
    """Provider output, reduced to what the contract names.

    Attributes:
        external_reference: The far side's own identifier, where it returned one.
        payload: The contract-named fields, with forbidden keys removed.
    """

    external_reference: str | None
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class NormalizedProfile:
    """Directory facts in platform terms. **Deliberately two fields.**

    Attributes:
        display_name: The principal's name, for presentation only.
        mail: The primary address, where the directory publishes one.
    """

    display_name: str
    mail: str | None


def normalize_case_result(raw: Mapping[str, object]) -> NormalizedResult:
    """Validate and reduce a case response.

    Args:
        raw: The decoded provider body.

    Returns:
        The normalized result.

    Raises:
        BoundaryValidationError: When the body exceeds the size bound or carries no usable external
            reference. **Both are refusals rather than warnings**: an oversized body is either a
            contract change or an attack, and a case operation that returned no identifier gives the
            platform nothing to reconcile against later.
    """
    # Size is measured on the re-serialised body rather than on the transport length, because the
    # bound that matters is what would be stored, not what was received.
    encoded = json.dumps(raw, default=str)
    if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise BoundaryValidationError(
            f"provider response exceeds the {_MAX_PAYLOAD_BYTES} byte boundary limit"
        )

    payload = {
        key: value
        for key, value in raw.items()
        if key in _CASE_FIELDS and not _FORBIDDEN_KEY.search(key)
    }

    external_reference: str | None = None
    for key in _EXTERNAL_REFERENCE_KEYS:
        candidate = payload.get(key)
        if isinstance(candidate, str) and candidate.strip():
            external_reference = candidate.strip()
            break

    if external_reference is None:
        raise BoundaryValidationError(
            "provider response carried no case identifier. The platform would have nothing to "
            "reconcile the record against, and an unreconcilable write is worse than a failed one."
        )

    return NormalizedResult(external_reference=external_reference, payload=payload)


def normalize_tool_result(raw: Mapping[str, object]) -> NormalizedResult:
    """Validate and reduce a generic tool response — MCP or native connector.

    **Looser than the case contract on shape, identical on safety.** A case record has a known set
    of fields; an arbitrary capability does not, and inventing one would reject every legitimate
    connector that did not happen to match it. So the field allow-list is dropped here and the two
    rules that carry the security weight are kept:

    * the **size bound**, because an oversized body is either a contract change or an attack, and
      either way it must not become a multi-megabyte row in an append-only record;
    * the **forbidden-key filter**, because a credential or an endpoint echoed back by a provider
      must not be carried inward — a destination comes from the registry, and a secret comes from
      the vault.

    **An external reference is optional here**, unlike a case. Many capabilities legitimately return
    no identifier — a read, a check, a no-op — and demanding one would fail them at the boundary for
    behaving correctly.

    Args:
        raw: The decoded provider body.

    Returns:
        The normalized result.

    Raises:
        BoundaryValidationError: When the body exceeds the size bound.
    """
    encoded = json.dumps(raw, default=str)
    if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise BoundaryValidationError(
            f"provider response exceeds the {_MAX_PAYLOAD_BYTES} byte boundary limit"
        )

    payload = {key: value for key, value in raw.items() if not _FORBIDDEN_KEY.search(key)}

    external_reference: str | None = None
    for key in _EXTERNAL_REFERENCE_KEYS:
        candidate = payload.get(key)
        if isinstance(candidate, str) and candidate.strip():
            external_reference = candidate.strip()
            break

    return NormalizedResult(external_reference=external_reference, payload=payload)


def normalize_directory_profile(raw: Mapping[str, object]) -> NormalizedProfile:
    """Validate and reduce a directory response.

    **The narrowest contract in this module, and deliberately so.** The platform's identity is
    derived once at the gateway (constitution Principle I), so what a directory adds is presentation
    detail — not identity, not roles, not group membership. A profile carrying any of those would be
    a second source of authorization beside the closed header contract, which is why there is no
    field here to put one in.

    **Graph's vocabulary stops at this function.** ``userPrincipalName``, ``@odata.context`` and
    ``id`` are read here and nowhere else; what leaves is stated in platform terms.

    Args:
        raw: The decoded provider body.

    Returns:
        The normalized profile.

    Raises:
        BoundaryValidationError: When the body exceeds the size bound, or carries no usable display
            name. A profile with nothing to display is an absence dressed as a presence, and the
            caller that received it would render an empty string as though the directory had
            answered.
    """
    encoded = json.dumps(raw, default=str)
    if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise BoundaryValidationError(
            f"provider response exceeds the {_MAX_PAYLOAD_BYTES} byte boundary limit"
        )

    display_name = _bounded_text(raw.get("displayName"), limit=_DISPLAY_NAME_LIMIT)
    if display_name is None:
        raise BoundaryValidationError(
            "directory response carried no display name. An empty profile would render as though "
            "the directory had answered, which is not the same fact as an unknown principal."
        )

    return NormalizedProfile(
        display_name=display_name,
        mail=_bounded_text(raw.get("mail"), limit=_MAIL_LIMIT),
    )


def _bounded_text(value: object, *, limit: int) -> str | None:
    """One bounded string field, or ``None``.

    **Truncation is not an option here.** A silently shortened value is a value the platform now
    holds a wrong version of, and the wrongness is invisible; refusing is what makes a contract
    change show up as a failure rather than as subtly corrupted data.

    Args:
        value: The raw field.
        limit: The inclusive maximum length.

    Returns:
        The stripped text, or ``None`` when absent, blank or not a string.

    Raises:
        BoundaryValidationError: When the text exceeds the bound.
    """
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if not candidate:
        return None

    if len(candidate) > limit:
        raise BoundaryValidationError(
            f"a directory field exceeds its {limit} character bound at the boundary"
        )

    return candidate
