"""The workload API boundary. **Positive and negative, at the HTTP edge.**

The negatives here are the ones that matter most: an organisation supplied as a parameter, a
credential or endpoint leaking into a response, and a treatment field a caller could read and act
on. Each is a prohibition the platform states, so each gets a test that would fail if the
prohibition were removed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from integrations.api.health import ReadinessRegistry
from integrations.config.composition import Container
from integrations.config.settings import (
    EdgeTrustSettings,
    IntegrationsSettings,
    ObservabilitySettings,
)
from integrations.domain.catalogue import (
    AccessDecision,
    AccessRefusal,
    Capability,
    CapabilityIdentity,
)
from integrations.observability.telemetry import ConnectorMetrics

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = pytest.mark.security

_HASH = "b" * 64
_SESSION = UUID("22222222-2222-2222-2222-222222222222")
_TENANT = UUID("33333333-3333-3333-3333-333333333333")

_GATEWAY_HEADERS = {
    "X-Forwarded-Client-Cert": f"Hash={_HASH};Subject=CN=apim",
    "X-Idp-Tenant-Id": "44444444-4444-4444-4444-444444444444",
    "X-Idp-Principal-Id": "55555555-5555-5555-5555-555555555555",
    "X-Idp-Credential-Class": "app",
    "X-Idp-Client-Surface": "workload",
}


class _Catalogue:
    async def capabilities_for(self, tenant_id: UUID) -> Sequence[Capability]:
        del tenant_id
        return [
            Capability(
                identity=CapabilityIdentity("reference.inert_read", 1),
                kind="read",
                entitled=True,
                available=True,
                is_reference_fixture=True,
            ),
            Capability(
                identity=CapabilityIdentity("reference.inert_action", 1),
                kind="action",
                entitled=False,
                available=True,
                is_reference_fixture=True,
            ),
        ]

    async def is_entitled(self, tenant_id: UUID, catalogue_id: str) -> bool:
        del tenant_id, catalogue_id
        return True

    async def registered_version(self, catalogue_id: str) -> int | None:
        del catalogue_id
        return 1


class _Tenants:
    def __init__(self, *, known: bool = True) -> None:
        self._known = known

    async def tenant_for_session(self, session_id: UUID) -> UUID | None:
        del session_id
        return _TENANT if self._known else None

    async def tenant_for_work_item(self, work_item_id: UUID) -> UUID | None:
        del work_item_id
        return _TENANT if self._known else None


class _RefusingPolicy:
    async def evaluate(self, tenant_id: UUID, identity: CapabilityIdentity) -> AccessDecision:
        del tenant_id, identity
        return AccessDecision.refuse(AccessRefusal.NOT_ENTITLED)


def _client(*, known_session: bool = True) -> TestClient:
    container = Container(
        settings=IntegrationsSettings(
            edge_trust=EdgeTrustSettings(gateway_certificate_thumbprints=frozenset({_HASH})),
            observability=ObservabilitySettings(),
        ),
        readiness=ReadinessRegistry(),
        connector_metrics=ConnectorMetrics(),
        catalogue=_Catalogue(),  # type: ignore[arg-type]
        tenants=_Tenants(known=known_session),  # type: ignore[arg-type]
        access_policy=_RefusingPolicy(),  # type: ignore[arg-type]
        servicenow=None,
    )
    return TestClient(create_app(container), raise_server_exceptions=False)


# --------------------------------------------------------------------------- positive


def test_catalogue_read_through_the_gateway_succeeds() -> None:
    """**Positive.** A gateway-stamped, app-only call with an opaque session identifier works."""
    response = _client().get(
        "/api/workload/v1/integrations/catalogue",
        params={"sessionId": str(_SESSION)},
        headers=_GATEWAY_HEADERS,
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["catalogueId"] == "reference.inert_read"


def test_unentitled_capabilities_are_listed_rather_than_omitted() -> None:
    """A caller can tell *not entitled* from *does not exist*.

    Omitting unentitled entries would make the two identical, and they need different operator
    actions — entitle the organisation, versus register the capability.
    """
    items = (
        _client()
        .get(
            "/api/workload/v1/integrations/catalogue",
            params={"sessionId": str(_SESSION)},
            headers=_GATEWAY_HEADERS,
        )
        .json()["items"]
    )

    assert [i["entitled"] for i in items] == [True, False]


def test_reference_fixtures_are_visibly_labelled() -> None:
    """Constitution Principle IX: a fixture is never presentable as product capability."""
    items = (
        _client()
        .get(
            "/api/workload/v1/integrations/catalogue",
            params={"sessionId": str(_SESSION)},
            headers=_GATEWAY_HEADERS,
        )
        .json()["items"]
    )

    assert all(i["isReferenceFixture"] for i in items)


# --------------------------------------------------------------------------- negative


def test_the_catalogue_response_carries_no_treatment_roles_or_endpoint() -> None:
    """**The most important negative here.**

    Treatment is deterministic governance's decision in RagCore (FR-INTEG-008). A catalogue
    response carrying it would invite a caller to read it and decide — and an endpoint would be an
    egress hint from a service whose whole job is to be the only egress.
    """
    body = json.dumps(
        _client()
        .get(
            "/api/workload/v1/integrations/catalogue",
            params={"sessionId": str(_SESSION)},
            headers=_GATEWAY_HEADERS,
        )
        .json()
    ).lower()

    for forbidden in ("treatment", "acceptedroles", "risktier", "endpoint", "url", "credential"):
        assert forbidden not in body, f"the catalogue response disclosed {forbidden!r}"


def test_an_organisation_supplied_as_a_parameter_is_rejected() -> None:
    """**No endpoint accepts an organisation and trusts it** (contracts README rule 1).

    The models forbid unknown fields, so `tenantId` is refused rather than ignored. Ignoring it
    would let a caller believe it had been honoured.
    """
    response = _client().post(
        "/api/workload/v1/integrations/case-operations",
        json={
            "sessionId": str(_SESSION),
            "tenantId": str(uuid4()),
            "catalogueId": "reference.inert_action",
            "catalogueVersion": 1,
            "idempotencyKey": "derived-key-0001",
            "parameters": {},
        },
        headers=_GATEWAY_HEADERS,
    )

    assert response.status_code == 422


def test_supplying_both_identifiers_is_refused_rather_than_resolved() -> None:
    """Two ideas about which organisation this is gets an error, not a precedence rule.

    Silently preferring one would resolve that disagreement invisibly.
    """
    response = _client().get(
        "/api/workload/v1/integrations/catalogue",
        params={"sessionId": str(_SESSION), "workItemId": str(uuid4())},
        headers=_GATEWAY_HEADERS,
    )

    assert response.status_code == 400


def test_supplying_neither_identifier_is_refused() -> None:
    """Without an identifier there is no durable object to recover an organisation from."""
    response = _client().get("/api/workload/v1/integrations/catalogue", headers=_GATEWAY_HEADERS)

    assert response.status_code == 400


def test_an_unknown_session_is_404_not_403() -> None:
    """Existence is itself organisation-scoped information.

    Answering 403 for "exists but not yours" and 404 for "does not exist" would let a caller map
    another organisation's identifiers by the difference between the two.
    """
    response = _client(known_session=False).get(
        "/api/workload/v1/integrations/catalogue",
        params={"sessionId": str(_SESSION)},
        headers=_GATEWAY_HEADERS,
    )

    assert response.status_code == 404


def test_a_policy_refusal_names_what_an_operator_must_fix() -> None:
    """A refusal is actionable, and it is not a 500.

    The policy here always refuses on entitlement, and the problem type says so — an operator is
    told to entitle the organisation rather than to go looking for a fault.
    """
    response = _client().post(
        "/api/workload/v1/integrations/case-operations",
        json={
            "sessionId": str(_SESSION),
            "catalogueId": "reference.inert_action",
            "catalogueVersion": 1,
            "idempotencyKey": "derived-key-0001",
            "parameters": {},
        },
        headers=_GATEWAY_HEADERS,
    )

    assert response.status_code == 403
    assert response.json()["type"].endswith("not-entitled")


def test_health_is_absent_from_the_published_contract() -> None:
    """Probes are platform infrastructure, not an API operation.

    Publishing them would describe an unauthenticated surface in a document handed to API
    consumers.
    """
    document = create_app(
        Container(
            settings=IntegrationsSettings(
                edge_trust=EdgeTrustSettings(gateway_certificate_thumbprints=frozenset({_HASH})),
                observability=ObservabilitySettings(),
            ),
            readiness=ReadinessRegistry(),
            connector_metrics=ConnectorMetrics(),
            catalogue=_Catalogue(),  # type: ignore[arg-type]
            tenants=_Tenants(),  # type: ignore[arg-type]
            access_policy=_RefusingPolicy(),  # type: ignore[arg-type]
            servicenow=None,
        )
    ).openapi()

    assert not [path for path in document["paths"] if path.startswith("/health")]
