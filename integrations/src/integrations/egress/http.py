"""Outbound HTTP. **Every call carries an explicit timeout, and no client is built ad hoc.**

.claude/rules/21-python.md PY-17. The timeout rule is specific to this platform rather than general
hygiene:
an execution runs inside a fifteen-minute authorization window that now spans **two hops** — RagCore
to here, and here to the external system — so one call without a timeout can hold work past its
expiry and turn a slow vendor into an expired approval that requires fresh human authorization.

**Transient and non-transient are distinguished, and only one of them is retried.**

* A **read** may retry with backoff inside the adapter.
* A **side-effecting** call MUST NOT be retried automatically (spec `FR-EXEC-006`,
  `FR-INTEG-027`). A failed authorized action requires fresh human authorization, and a retry loop
  here would spend one authority record more than once. :meth:`ResilientCaller.send` therefore takes
  `retriable` explicitly and has **no default** — a caller must say which kind of call this is,
  because a default would eventually be wrong for the dangerous case.

**One pooled client for the process.** `httpx.AsyncClient` is constructed once and reused: a client
per call exhausts sockets and re-resolves DNS on every request, and the constitution prohibits
one-off unmanaged clients for exactly that reason.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import httpx

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping

__all__ = ["EgressError", "OutboundRequest", "OutboundResponse", "ResilientCaller"]

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS: Final = 30.0
_MAX_ATTEMPTS: Final = 3
_BASE_BACKOFF_SECONDS: Final = 0.5

# 5xx and 429 are transient; 4xx other than 429 are not. Retrying a 400 re-sends a request the far
# side has already told us it will never accept, which is load with no possible outcome.
_TRANSIENT_STATUSES: Final = frozenset({429, 500, 502, 503, 504})


class EgressError(Exception):
    """An outbound call failed in a way the caller must handle.

    Carries no response body. A vendor error body can contain another organisation's data or an
    internal endpoint, and this exception is the thing most likely to be logged or surfaced.
    """


@dataclass(frozen=True, slots=True)
class OutboundRequest:
    """One outbound call.

    Attributes:
        method: The HTTP method.
        url: The absolute destination. **Assembled by the connector registry from durable
            configuration** — never from a parameter, model output or retrieved content.
        headers: Request headers. A credential is attached by the adapter at the point of use and
            is never held on this object beyond the call.
        json_body: The request body, or ``None``.
        timeout_seconds: The explicit timeout. Defaulted, but never absent.
    """

    method: str
    url: str
    headers: Mapping[str, str]
    json_body: Mapping[str, object] | None = None
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class OutboundResponse:
    """What came back.

    Attributes:
        status_code: The HTTP status.
        payload: The decoded body, or an empty mapping. **Data** — contract-checked by the caller
            before it goes anywhere near a decision.
    """

    status_code: int
    payload: Mapping[str, object]

    @property
    def succeeded(self) -> bool:
        """Whether the far side reported success."""
        return 200 <= self.status_code < 300


class ResilientCaller:
    """The one outbound HTTP path."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        """Bind to a pooled client.

        Args:
            client: The process-wide client. Constructed by the composition root, not here.
        """
        self._client = client

    @staticmethod
    def build_client() -> httpx.AsyncClient:
        """Construct the process-wide client.

        Returns:
            A client with a default timeout, so even a request that somehow omitted one cannot
            hang forever. Belt and braces: :class:`OutboundRequest` always carries one.
        """
        return httpx.AsyncClient(
            timeout=httpx.Timeout(_DEFAULT_TIMEOUT_SECONDS),
            follow_redirects=False,
        )

    async def send(self, request: OutboundRequest, *, retriable: bool) -> OutboundResponse:
        """Send one request.

        Args:
            request: What to send, including its explicit timeout.
            retriable: Whether this call may be retried. **Keyword-only and without a default**, so
                a caller must state which kind of call this is. A side-effecting call passes
                ``False``: a failed authorized action requires fresh human authorization, never an
                automatic retry.

        Returns:
            The response.

        Raises:
            EgressError: When the call could not be completed. The underlying exception is logged,
                not surfaced — a vendor error can carry another organisation's data.
        """
        attempts = _MAX_ATTEMPTS if retriable else 1
        last_status: int | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.request(
                    request.method,
                    request.url,
                    headers=dict(request.headers),
                    json=request.json_body,
                    timeout=request.timeout_seconds,
                )
            except httpx.HTTPError as error:
                if not retriable or attempt == attempts:
                    logger.warning("Outbound call failed", exc_info=True)
                    raise EgressError("the outbound call could not be completed") from error
                await self._backoff(attempt)
                continue

            if retriable and response.status_code in _TRANSIENT_STATUSES and attempt < attempts:
                last_status = response.status_code
                await self._backoff(attempt)
                continue

            return OutboundResponse(
                status_code=response.status_code,
                payload=self._decode(response),
            )

        # The last transient status is reported, because "did not succeed after 3 attempts" sends an
        # operator looking without saying where: a 429 means back off, a 503 means the far side is
        # down, and they call for different actions.
        raise EgressError(
            f"the outbound call did not succeed after {attempts} attempts"
            + (f" (last status {last_status})" if last_status is not None else "")
        )

    @staticmethod
    async def _backoff(attempt: int) -> None:
        """Wait before retrying.

        Exponential **with jitter**. Without jitter, every replica that failed on the same vendor
        blip retries in the same millisecond, which is a self-inflicted thundering herd against a
        system that is already struggling.

        Args:
            attempt: The attempt just completed, one-based.
        """
        delay = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
        await asyncio.sleep(delay + random.uniform(0, delay / 2))  # noqa: S311 — jitter, not crypto

    @staticmethod
    def _decode(response: httpx.Response) -> Mapping[str, object]:
        """Decode a JSON body, tolerating one that is absent or malformed.

        Args:
            response: The response.

        Returns:
            The decoded mapping, or an empty one. A malformed body is **not** an exception here:
            the status code is still meaningful, and the boundary validator is what decides whether
            a payload is acceptable. Raising here would conflate "the far side answered oddly" with
            "the call failed".
        """
        try:
            decoded = response.json()
        except ValueError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
