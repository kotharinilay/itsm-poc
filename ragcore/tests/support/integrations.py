"""Fakes for the Stage 9 integration boundaries.

**These are fakes, not mocks**, on the same terms as :mod:`tests.support.fakes`: each one honours
the contract of the thing it stands in for, so a test that passes against them is testing behaviour
rather than an interaction transcript.

**Substituted at the transport, not at the adapter.** :func:`transport_returning` builds an
``httpx`` transport, which means the adapter under test is the production adapter, running the
production resilience policy, the production timeout rule and the production boundary validation.
Only the far side is fake. A test that substituted the adapter itself would assert that a fake
behaves like a fake.

That matters here more than in most suites: **the real Azure resources are not available in CI**.
There is no AI Gateway, no AI Search index and no ServiceNow instance in a pull-request build, so
the choice is between fakes at the transport and no adapter coverage at all. Fakes at the transport
leave everything above the socket exercised.

**No credential appears in this module.** :class:`FakeCredential` returns a token-shaped string
that authenticates nothing. The constitution's rule is that no credential appears in source, in
tests, or in committed local configuration; a fake that carried a real-looking secret would be
indistinguishable from a leak to every scanner that looks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class _FakeToken:
    """What an Azure credential's ``get_token`` returns."""

    token: str
    expires_on: int = 0


class FakeCredential:
    """A credential that mints a token authenticating nothing.

    Stands in for the shared ``DefaultAzureCredential`` so that the token-acquisition path in each
    adapter is exercised without an Azure sign-in — CI has no managed identity, and a test that
    skipped the token step would leave the one line that constructs the ``Authorization`` header
    untested.
    """

    def __init__(self) -> None:
        self.requested_scopes: list[str] = []

    async def get_token(self, *scopes: str, **kwargs: Any) -> _FakeToken:
        """Record the scope and return a placeholder token.

        The scopes are recorded because *which* scope an adapter asks for is itself a control: a
        broader one than the resource needs would be a quiet privilege escalation, and the
        assertion that it asked for the narrow one belongs in a test.
        """
        del kwargs
        self.requested_scopes.extend(scopes)
        return _FakeToken(token="placeholder-token")  # noqa: S106 — authenticates nothing


# `FakeSecretResolver` AND `FakeCredentialReferenceStore` STOOD HERE AND ARE GONE (T296).
#
# They existed to test per-organisation connector credential resolution, which this deployable no
# longer performs. Their equivalents live beside the code that does, in the Integrations Service.
#
# **A dead fake is not harmless.** A fixture modelling a removed capability is an invitation to
# rebuild it — the next author finds a ready-made store for connector credentials and reasonably
# concludes that resolving one here is a supported thing to do.


@dataclass
class RecordedRequest:
    """One request the fake transport saw.

    Kept so a test can assert on what actually went on the wire — the tenant filter that was sent,
    the idempotency key that was carried, the absence of an ``api-key`` header.
    """

    method: str
    url: str
    headers: dict[str, str]
    body: Any


@dataclass
class TransportRecorder:
    """The requests a fake transport received, in order."""

    requests: list[RecordedRequest] = field(default_factory=list)

    @property
    def last(self) -> RecordedRequest:
        """The most recent request. Raises ``IndexError`` when nothing was sent, which is the
        correct failure for a test asserting on a call that never happened."""
        return self.requests[-1]

    def header(self, name: str) -> str | None:
        """One header from the last request, case-insensitively."""
        lowered = {key.lower(): value for key, value in self.last.headers.items()}
        return lowered.get(name.lower())


def transport_returning(
    handler: Callable[[RecordedRequest], httpx.Response],
) -> tuple[httpx.AsyncBaseTransport, TransportRecorder]:
    """Build a fake transport driven by ``handler``, plus the recorder of what it saw.

    Args:
        handler: Decides the response for each request. A function rather than a fixed response so
            a test can vary by URL — which is how the retry, the throttle and the 404 paths are
            exercised without a real dependency.

    Returns:
        The transport to hand to :class:`~ragcore.egress.http.HttpClientFactory`, and the
        recorder.
    """
    recorder = TransportRecorder()

    def respond(request: httpx.Request) -> httpx.Response:
        raw = request.content
        recorded = RecordedRequest(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            body=json.loads(raw) if raw else None,
        )
        recorder.requests.append(recorded)
        return handler(recorded)

    return httpx.MockTransport(respond), recorder


def json_response(payload: Any, status: int = 200) -> httpx.Response:
    """A JSON response, for a handler that does not care about the request."""
    return httpx.Response(status_code=status, json=payload)


class FakeModelEgress:
    """A gateway seam that records what crossed it.

    Satisfies :class:`~ragcore.integrations.model.egress.ModelEgressPort`. Used to assert what the
    *adapter* sends — that the organisation is the one from trusted context, that the purpose is
    the right one, and that no model name was invented along the way.
    """

    def __init__(self, *, text: str = "a proposal", embedding: tuple[float, ...] = (0.1, 0.2)):
        from ragcore.integrations.model.egress import ModelRequest

        self.sent: list[ModelRequest] = []
        self._text = text
        self._embedding = embedding

    async def send(self, request: Any) -> Any:
        """Record the request and answer it."""
        from ragcore.integrations.model.egress import ModelPurpose, ModelResponse

        self.sent.append(request)

        if request.purpose is ModelPurpose.COMPLETION:
            return ModelResponse(text=self._text)
        return ModelResponse(embedding=list(self._embedding))
