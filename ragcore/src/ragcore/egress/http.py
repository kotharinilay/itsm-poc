"""Outbound HTTP. **Pooled clients, one resilience policy, and a timeout on every call.**

No adapter in this package constructs an ``httpx.AsyncClient`` of its own. They take one from
:class:`HttpClientFactory`, which owns the lifetime and the pool — the Python equivalent of the
``IHttpClientFactory`` rule the .NET stack follows (research R-020). A client constructed per call
leaks sockets and pins DNS to whatever it resolved at construction; a client constructed per module
does the same, more slowly, and is harder to see.

**The timeout rule is specific to this platform, not general hygiene.** RagCore calls MCP servers,
the system of record, Graph and the AI Gateway inside a fifteen-minute execution window. One call
without a timeout can hold work past its expiry, which turns a slow dependency into an expired
approval — a governance outcome produced by a transport defect. :class:`OutboundRequest` therefore
has no default timeout and no ``None``: the value is constructed with the request or there is no
request.

**Transient and non-transient failure are different types, not a status code the caller inspects.**
:class:`TransientIntegrationError` may be retried at the transport level; anything else may not.
The distinction matters more here than in most systems because of the rule it must not be confused
with: transport-level retry of a *read* is fine, while a failed side-effecting operation does not
re-fire and requires fresh human authorization (ADR-0002). This module retries transport, never
operations, and the two live on opposite sides of the execution gate.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Self

import httpx

from ragcore.domain.errors import DomainError

_log: Final = logging.getLogger(__name__)

MAX_TIMEOUT_SECONDS: Final = 120.0
"""The longest any single outbound call may wait.

Bounded above rather than left to each caller. The execution window is fifteen minutes and a call
that could occupy a meaningful fraction of it is a call that should have failed and been retried.
"""


class IntegrationError(DomainError):
    """An outbound call did not produce a usable result.

    Derives from :class:`~ragcore.domain.errors.DomainError` so that a caller handling platform
    failure does not also have to know ``httpx``. **The provider's exception is never chained into
    the message** — it can carry request URLs, headers and response bodies, and this message reaches
    logs.
    """

    def __init__(self, system: str, reason: str) -> None:
        super().__init__(f"the call to {system} did not succeed: {reason}")
        self.system = system


class TransientIntegrationError(IntegrationError):
    """The call failed in a way that may succeed on retry — a timeout, a 5xx, a 429.

    **Retrying a read is fine; retrying an operation is not.** This type says the *transport*
    failed, and says nothing about whether the effect happened. An adapter performing a
    side-effecting call reports this outward rather than re-firing (ADR-0002).
    """


class PermanentIntegrationError(IntegrationError):
    """The call failed in a way that will fail again — a 4xx that is not 429, a contract breach.

    Retrying is not merely useless here but harmful: it turns one clear failure into a burst of
    identical ones and, against a rate-limited provider, into an outage that looks like the
    provider's fault.
    """


@dataclass(frozen=True, slots=True)
class OutboundRequest:
    """One outbound call, with its timeout stated.

    Frozen and slotted, and ``timeout_seconds`` has **no default**. That is the whole design: a
    default timeout is a timeout nobody chose, and the one call site that needed a different value
    is the one that will not have set it.
    """

    method: str
    url: str
    timeout_seconds: float
    headers: dict[str, str] | None = None
    json_body: object | None = None

    def __post_init__(self) -> None:
        """Refuse a call that could outlive the execution window.

        Raises:
            ValueError: When the timeout is absent, non-positive or above
                :data:`MAX_TIMEOUT_SECONDS`, or when the URL is not https. Both are refused at
                construction rather than at send, so the failure names the call site.
        """
        if self.timeout_seconds <= 0 or self.timeout_seconds > MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"an outbound call needs an explicit timeout in (0, {MAX_TIMEOUT_SECONDS}] "
                f"seconds, got {self.timeout_seconds}. A call without a bounded timeout can hold "
                "work past its fifteen-minute expiry."
            )
        if not self.url.startswith("https://"):
            raise ValueError(
                f"outbound calls are https-only, got {self.url!r}. Every one of them carries an "
                "Entra token or organisation-scoped data."
            )


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How a transient failure is retried. **Transport only.**

    Small and bounded on purpose. Generous retry against a struggling dependency is how one
    degraded provider becomes a self-inflicted outage, and every attempt spends part of the
    execution window that the approval it serves is counting down.
    """

    max_attempts: int = 3
    backoff_seconds: float = 0.5

    def __post_init__(self) -> None:
        """Reject a policy that would retry indefinitely.

        Raises:
            ValueError: When the attempt count is below one or above five.
        """
        if not 1 <= self.max_attempts <= 5:
            raise ValueError(f"max_attempts must be between 1 and 5, got {self.max_attempts}")

    def delay_before(self, attempt: int) -> float:
        """The wait before ``attempt``, exponential from the base backoff."""
        return self.backoff_seconds * float(2 ** (attempt - 1))


def classify(system: str, response: httpx.Response) -> IntegrationError | None:
    """Turn a response into the error it represents, or ``None`` when it succeeded.

    **One classification for every adapter.** Written once here rather than per adapter, because
    "which statuses are worth retrying" answered differently in six places is six different
    behaviours under the same outage, and only one of them was ever tested.

    Args:
        system: The system being called, for the message.
        response: What came back.

    Returns:
        The error, or ``None`` for a 2xx.
    """
    status = response.status_code

    if status < 400:
        return None

    # 408 request timeout, 429 too many requests, and every 5xx. A 429 is transient by definition —
    # the provider is telling us when to come back — and treating it as permanent would surface a
    # throttle to the user as a failure of their request, which FR-OPS-006 prohibits.
    if status in (408, 429) or status >= 500:
        return TransientIntegrationError(system, f"HTTP {status}")

    return PermanentIntegrationError(system, f"HTTP {status}")


class HttpClientFactory:
    """The pooled clients this process holds, one per named integration.

    Named rather than shared so that a slow system of record cannot exhaust the pool the AI Gateway
    is using. Each name gets its own client with its own connection pool, which is what makes the
    blast radius of one degraded dependency the calls to *that* dependency.

    The factory owns every client's lifetime and is closed by the application lifespan. An adapter
    never closes one, because an adapter does not know whether another holds it.
    """

    def __init__(
        self,
        *,
        max_connections: int = 20,
        max_keepalive: int = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Construct the factory.

        Args:
            max_connections: The per-integration connection ceiling.
            max_keepalive: How many of those are kept alive between calls.
            transport: A substitute transport. **The seam an integration test uses**, and the reason
                it is a constructor argument rather than a patch: a test that monkey-patches
                ``httpx`` exercises a different code path from the one that ships, and the real
                Azure resources these adapters call are not available in CI. With a fake transport
                the adapter, the resilience policy, the timeout rule and the boundary validation are
                all the production ones — only the far side is substituted.
        """
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._transport = transport
        self._limits = httpx.Limits(
            max_connections=max_connections, max_keepalive_connections=max_keepalive
        )

    def client_for(self, system: str) -> httpx.AsyncClient:
        """Return the pooled client for one system, constructing it on first use.

        Args:
            system: The integration's name — ``ai-gateway``, ``servicenow``, ``graph``.

        Returns:
            The client. Its default timeout is :data:`MAX_TIMEOUT_SECONDS` and is never the one
            actually used: :class:`OutboundRequest` requires an explicit value and
            :meth:`ResilientHttpCaller.send` passes it per call. The client-level value is the
            backstop for a code path that somehow reached the client directly — it makes the worst
            case a bounded wait rather than an unbounded one.
        """
        existing = self._clients.get(system)
        if existing is not None:
            return existing

        created = httpx.AsyncClient(
            limits=self._limits, timeout=MAX_TIMEOUT_SECONDS, transport=self._transport
        )
        self._clients[system] = created
        return created

    async def aclose(self) -> None:
        """Close every pooled client. Called once, from the lifespan that owns this factory."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    async def __aenter__(self) -> Self:
        """Enter, so a worker without a FastAPI lifespan still cannot forget to close."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close on exit, whether or not the body raised."""
        del exc_type, exc, traceback
        await self.aclose()


class ResilientHttpCaller:
    """Sends an :class:`OutboundRequest` under one shared resilience policy.

    Every adapter in this package calls through here. That is what makes "a consistent resilience
    policy distinguishing transient from non-transient failure" a property of the code rather than
    a paragraph each adapter author was expected to have read.
    """

    def __init__(
        self,
        factory: HttpClientFactory,
        *,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._factory = factory
        self._retry = retry if retry is not None else RetryPolicy()

    async def send(self, system: str, request: OutboundRequest) -> httpx.Response:
        """Send one request, retrying only transient transport failure.

        Args:
            system: The integration's name. Selects the pool and names the error.
            request: The call, with its timeout already stated.

        Returns:
            The successful response.

        Raises:
            TransientIntegrationError: When every attempt failed transiently. The caller decides
                what that means — for a read, try later; for an operation, **do not re-fire**.
            PermanentIntegrationError: On the first non-transient failure. Not retried.
        """
        client = self._factory.client_for(system)
        last: IntegrationError | None = None

        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                response = await client.request(
                    request.method,
                    request.url,
                    headers=request.headers,
                    json=request.json_body,
                    timeout=request.timeout_seconds,
                )
            except httpx.TimeoutException as error:
                last = TransientIntegrationError(system, "the call timed out")
                _log.warning(
                    "Outbound call timed out. system=%s attempt=%d/%d",
                    system,
                    attempt,
                    self._retry.max_attempts,
                    exc_info=error,
                )
            except httpx.HTTPError as error:
                # A transport error — connection refused, DNS, a reset. Transient by nature: the
                # request may never have reached the far side.
                last = TransientIntegrationError(system, "the transport failed")
                _log.warning(
                    "Outbound transport failure. system=%s attempt=%d/%d",
                    system,
                    attempt,
                    self._retry.max_attempts,
                    exc_info=error,
                )
            else:
                failure = classify(system, response)
                if failure is None:
                    return response
                if isinstance(failure, PermanentIntegrationError):
                    raise failure
                last = failure

            if attempt < self._retry.max_attempts:
                await asyncio.sleep(self._retry.delay_before(attempt))

        raise last if last is not None else TransientIntegrationError(system, "no attempt was made")
