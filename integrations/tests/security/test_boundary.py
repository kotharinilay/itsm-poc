"""Security guards. **Every prohibition is proven unreachable, not merely stated.**

.claude/rules/40-testing.md §40.10: every protection named as a hard failure must have a test that
fails when
the protection is removed. These cover the prohibitions this slice establishes.

**The gateway-provenance tests are gone, and their absence is the finding.** They asserted that a
request arriving without proof of having come through APIM was refused, which is what `SC-DEMO-003b`
measured. That mechanism is deferred — see
`docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md` — and nothing replaced it,
so the assertion stopped being true. It was deleted rather than reworded into something that still
passes. What remains below is the identity boundary, which is a narrower control and is tested as
such.
"""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from integrations.api.health import ReadinessRegistry
from integrations.config.composition import Container
from integrations.config.settings import (
    IntegrationsSettings,
    ObservabilitySettings,
)
from integrations.observability.telemetry import ConnectorMetrics

pytestmark = pytest.mark.security

_SRC = Path(__file__).resolve().parents[2] / "src" / "integrations"


class _UnreachableCatalogue:
    """Every method raises.

    These tests are about the **identity boundary**, which runs before any endpoint.
    A catalogue that raised if reached proves the refusal happened at the boundary rather than
    somewhere deeper — a benign stub would let a routing change pass these tests silently.
    """

    def __getattr__(self, name: str) -> object:
        raise AssertionError(
            f"{name} was reached. These tests assert the request is refused before any endpoint "
            "runs, so reaching the catalogue means the boundary did not hold."
        )


def _client() -> TestClient:
    """A client arriving as any caller now does: with nothing proving where it came from."""
    container = Container(
        settings=IntegrationsSettings(observability=ObservabilitySettings()),
        readiness=ReadinessRegistry(),
        connector_metrics=ConnectorMetrics(),
        catalogue=_UnreachableCatalogue(),  # type: ignore[arg-type]
        tenants=_UnreachableCatalogue(),  # type: ignore[arg-type]
        access_policy=_UnreachableCatalogue(),  # type: ignore[arg-type]
        servicenow=None,
    )
    return TestClient(create_app(container), raise_server_exceptions=False)


def test_a_request_carrying_no_identity_is_refused() -> None:
    """No contract, no service. The narrowest thing still true here.

    **This is deliberately weaker than the test it replaces**, and the difference is the whole
    point of ADR 0008. That test asserted a *well-formed but self-supplied* `X-Idp-*` contract was
    refused — the shape a real bypass takes, which `SC-DEMO-003b` measured. It was refused on
    gateway provenance, and gateway provenance is deferred with nothing in its place.

    So this service can no longer tell a self-supplied contract from an APIM-stamped one: **a
    complete forgery sent from inside the environment is honoured.** What remains is that a caller
    supplying no identity at all gets nothing, which is asserted below and is not a substitute.
    """
    response = _client().get("/api/workload/v1/integrations/openapi.json")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_delegated_credential_is_refused_on_this_audience() -> None:
    """A human credential cannot reach the workload surface.

    APIM refuses a delegated token before the request arrives; this is the second half of that
    check. It is not redundant: a policy misconfiguration is exactly the failure that would let a
    human's authority arrive wearing a machine's shape — and appear in the audit record as a
    machine.

    **This test now exercises the credential-class check for the first time.** It previously sent a
    stale, unread header name in place of gateway provenance, so the request was refused before the
    credential class was ever inspected and the assertion passed for the wrong reason. With
    provenance deferred (ADR 0008), the refusal below is the one the test claims to be about.
    """
    response = _client().get(
        "/api/workload/v1/integrations/openapi.json",
        headers={
            "X-Idp-Tenant-Id": "11111111-1111-1111-1111-111111111111",
            "X-Idp-Principal-Id": "22222222-2222-2222-2222-222222222222",
            "X-Idp-Credential-Class": "delegated",
            "X-Idp-Client-Surface": "customer",
        },
    )
    assert response.status_code == 403


@pytest.mark.parametrize("name", ["tenantId", "tenant_id", "X-Tenant-Id", "roles", "organisation"])
def test_a_client_supplied_authority_parameter_is_refused_not_ignored(name: str) -> None:
    """Refused with 400, as RagCore and the monolith refuse it.

    It used to be silently ignored: the organisation here comes from durable state, so the value was
    never honoured — but a boundary that quietly tolerates the attempt is one where nobody can tell
    an attempt was made, and the three deployables answered the same request three different ways.
    """
    response = _client().get(
        f"/api/workload/v1/integrations/catalogue?sessionId={uuid4()}&{name}=anything",
        headers={
            "X-Idp-Tenant-Id": "11111111-1111-1111-1111-111111111111",
            "X-Idp-Principal-Id": "22222222-2222-2222-2222-222222222222",
            "X-Idp-Credential-Class": "app",
            "X-Idp-Client-Surface": "workload",
        },
    )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "anything" not in response.text


def test_health_endpoints_disclose_nothing() -> None:
    """Probes are anonymous by necessity and return an empty body.

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
