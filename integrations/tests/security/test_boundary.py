"""Security guards. **Every prohibition is proven unreachable, not merely stated.**

Constitution §Coverage: every protection named as a hard failure must have a test that fails when
the protection is removed. These cover the prohibitions this slice establishes.

The gateway-provenance tests are the ones that matter most. `SC-DEMO-003b` measures the specific
shape a real bypass takes — a request carrying a **well-formed but self-supplied** identity contract
— and the service must refuse it rather than strip the headers and serve it.
"""

from __future__ import annotations

import ast
from pathlib import Path

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
from integrations.observability.telemetry import ConnectorMetrics

pytestmark = pytest.mark.security

_ACCEPTED_HASH = "a" * 64
_SRC = Path(__file__).resolve().parents[2] / "src" / "integrations"


def _client() -> TestClient:
    """A client whose app trusts exactly one certificate hash."""
    container = Container(
        settings=IntegrationsSettings(
            edge_trust=EdgeTrustSettings(
                gateway_certificate_thumbprints=frozenset({_ACCEPTED_HASH})
            ),
            observability=ObservabilitySettings(),
        ),
        readiness=ReadinessRegistry(),
        connector_metrics=ConnectorMetrics(),
    )
    return TestClient(create_app(container), raise_server_exceptions=False)


def test_empty_certificate_allow_list_fails_at_startup() -> None:
    """An empty allow-list stops the process rather than defaulting to permissive.

    This is the asymmetry the check exists for. An unconfigured vault fails loudly at first use; an
    unconfigured allow-list fails **silently by accepting forged identity**, because at request time
    "trust nothing" and "trust everything" look identical when the set is empty.
    """
    with pytest.raises(ValueError, match="thumbprint"):
        EdgeTrustSettings(gateway_certificate_thumbprints=frozenset())


def test_request_without_gateway_provenance_is_refused() -> None:
    """A direct request — not through APIM — fails.

    No pod-to-pod, container-to-container or internal-address route may reach this service.
    """
    response = _client().get("/api/workload/v1/integrations/openapi.json")
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")


def test_self_supplied_identity_contract_is_refused_not_sanitised() -> None:
    """**The shape a real bypass takes.**

    A caller forging the full `X-Idp-*` contract without gateway provenance is refused. Stripping
    the headers and serving the request would return *success* to an attacker and leave the attempt
    indistinguishable from an ordinary unauthenticated call — so the one event worth alerting on
    would become invisible.
    """
    response = _client().get(
        "/api/workload/v1/integrations/openapi.json",
        headers={
            "X-Idp-Tenant-Id": "11111111-1111-1111-1111-111111111111",
            "X-Idp-Principal-Id": "22222222-2222-2222-2222-222222222222",
            "X-Idp-Credential-Class": "app",
            "X-Idp-Client-Surface": "workload",
        },
    )
    assert response.status_code == 403
    body = response.json()
    assert body["type"].endswith("gateway-provenance-required")


def test_delegated_credential_is_refused_on_this_audience() -> None:
    """A human credential cannot reach the workload surface.

    APIM refuses a delegated token before the request arrives; this is the second half of that
    check. It is not redundant: a policy misconfiguration is exactly the failure that would let a
    human's authority arrive wearing a machine's shape — and appear in the audit record as a
    machine.
    """
    response = _client().get(
        "/api/workload/v1/integrations/openapi.json",
        headers={
            "X-Client-Certificate-Sha256": _ACCEPTED_HASH,
            "X-Idp-Tenant-Id": "11111111-1111-1111-1111-111111111111",
            "X-Idp-Principal-Id": "22222222-2222-2222-2222-222222222222",
            "X-Idp-Credential-Class": "delegated",
            "X-Idp-Client-Surface": "customer",
        },
    )
    assert response.status_code == 403


def test_health_endpoints_disclose_nothing() -> None:
    """Probes are exempt from provenance and return an empty body.

    They are unauthenticated by necessity — a platform probe does not traverse APIM — so they must
    disclose no identity, no dependency name and no configuration. A readiness endpoint that named
    the dependency it could not reach would be a reconnaissance surface on a service whose
    dependency list includes a vault.
    """
    client = _client()
    for path in ("/health/live", "/health/ready"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.content == b""


def test_no_token_parsing_library_is_imported() -> None:
    """The service MUST NOT parse an access token.

    Identity is derived exactly once, at APIM (Principle I). A JWT library here is an architectural
    change, not a convenience — it creates a second place identity can be established, and a second
    place it can be established wrongly.
    """
    banned = {"jwt", "jose", "python_jose", "authlib", "msal"}
    offenders: list[str] = []
    for path in _SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}:{a.name}" for a in node.names if a.name.split(".")[0] in banned
                ]
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.split(".")[0] in banned
            ):
                offenders.append(f"{path.name}:{node.module}")

    assert offenders == [], (
        "token-parsing libraries imported: "
        + ", ".join(offenders)
        + ". Identity is derived at APIM."
    )
