"""RagCore authenticates to the Integrations Service as itself, through APIM.

APIM validates an Entra token and the workload application role on
``/api/workload/v1/integrations``. The client used to send a correlation identifier and nothing
else, so every call it made would have been refused at the gateway with a 401 — and no test
noticed, because no test exercised the client at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from ragcore.config.settings import IntegrationsServiceSettings
from ragcore.domain.identifiers import CorrelationId, IdempotencyKey
from ragcore.egress.http import OutboundRequest
from ragcore.platform_clients.integrations import IntegrationsClient, IntegrationsClientSettings

EDGE = "https://edge.example"
SCOPE = "api://synthia-workload/.default"
CORRELATION = CorrelationId("0b8f7c1e-2c7a-4d51-9a55-7d0c6d8e1f00")


@dataclass
class _Token:
    token: str


@dataclass
class FakeCredential:
    """An ``AsyncTokenCredential`` recording the scopes it was asked for."""

    scopes: list[str] = field(default_factory=list)

    async def get_token(self, scope: str) -> _Token:
        self.scopes.append(scope)
        return _Token("fake-workload-token")


@dataclass
class RecordingCaller:
    """The shared resilient caller, reduced to recording what would have been sent."""

    body: dict[str, Any]
    requests: list[OutboundRequest] = field(default_factory=list)

    async def send(self, system: str, request: OutboundRequest) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.body)


def _client(caller: RecordingCaller, credential: FakeCredential) -> IntegrationsClient:
    return IntegrationsClient(
        IntegrationsClientSettings(gateway_base_url=EDGE, entra_scope=SCOPE),
        caller,  # type: ignore[arg-type]
        credential,
    )


class TestEveryCallCarriesRagCoresOwnWorkloadToken:
    async def test_the_catalogue_read_is_authenticated(self) -> None:
        caller, credential = RecordingCaller(body={"items": []}), FakeCredential()

        await _client(caller, credential).read_catalogue(uuid4(), CORRELATION)

        (request,) = caller.requests
        assert request.headers is not None
        assert request.headers["Authorization"] == "Bearer fake-workload-token"
        assert request.headers["X-Correlation-Id"] == str(CORRELATION)
        assert credential.scopes == [SCOPE]

    async def test_the_case_operation_is_authenticated(self) -> None:
        caller = RecordingCaller(body={"succeeded": True, "externalReference": "CS001"})
        credential = FakeCredential()

        await _client(caller, credential).create_case(
            uuid4(), "synthia.reference.case", 1, {}, IdempotencyKey("k"), CORRELATION
        )

        (request,) = caller.requests
        assert request.headers is not None
        assert request.headers["Authorization"] == "Bearer fake-workload-token"
        assert credential.scopes == [SCOPE]

    async def test_no_organisation_travels_on_the_call(self) -> None:
        """App-only: the far side recovers the organisation from the object named."""
        caller = RecordingCaller(body={"succeeded": True})

        await _client(caller, FakeCredential()).create_case(
            uuid4(), "synthia.reference.case", 1, {}, IdempotencyKey("k"), CORRELATION
        )

        (request,) = caller.requests
        assert request.headers is not None
        assert not any(name.lower().startswith("x-idp-") for name in request.headers)
        assert isinstance(request.json_body, dict)
        assert "tenantId" not in request.json_body


class TestARouteThatCannotAuthenticateIsRefusedAtStartup:
    def test_the_client_refuses_an_empty_scope(self) -> None:
        with pytest.raises(ValueError, match="token scope"):
            IntegrationsClientSettings(gateway_base_url=EDGE, entra_scope=" ")

    def test_the_settings_refuse_an_address_without_a_scope(self) -> None:
        with pytest.raises(ValidationError, match="ENTRA_SCOPE"):
            IntegrationsServiceSettings(gateway_base_url=EDGE)

    def test_no_address_needs_no_scope(self) -> None:
        assert IntegrationsServiceSettings().is_configured is False
