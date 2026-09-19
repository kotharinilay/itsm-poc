"""The correlation rule belongs to the platform: ``build/policy/correlation-id.json``.

Each deployable implements it and each suite asserts the implementation against the shared vectors,
because the rules had drifted: this service accepted any printable string — ``<script>`` came back
in a header and a problem body — while the Integrations Service accepted hex only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ragcore.api.middleware.correlation import (
    CORRELATION_HEADER,
    WELL_FORMED,
    CorrelationIdMiddleware,
    _accepted,
)
from ragcore.domain.identifiers import CORRELATION_ID_MAX_LENGTH

POLICY_PATH: Final = (
    Path(__file__).resolve().parents[3] / "build" / "policy" / "correlation-id.json"
)
POLICY: Final[dict[str, Any]] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


class TestThisServiceImplementsThePlatformRule:
    def test_the_pattern_is_the_policys(self) -> None:
        assert WELL_FORMED.pattern == POLICY["pattern"]
        assert POLICY["maxLength"] == CORRELATION_ID_MAX_LENGTH

    @pytest.mark.parametrize("candidate", POLICY["accept"])
    def test_a_well_formed_identifier_is_kept(self, candidate: str) -> None:
        assert _accepted(candidate) == candidate

    @pytest.mark.parametrize("candidate", POLICY["reject"])
    def test_a_malformed_identifier_is_replaced(self, candidate: str) -> None:
        assert _accepted(candidate) is None

    def test_the_length_limit_is_inclusive(self) -> None:
        limit = POLICY["maxLength"]
        assert _accepted("a" * limit) == "a" * limit
        assert _accepted("a" * (limit + 1)) is None


def _app() -> Starlette:
    """An inner layer that sets the header itself, as the problem handler and SSE stream do."""

    async def endpoint(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok", headers={CORRELATION_HEADER: "set-by-an-inner-layer"})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(CorrelationIdMiddleware)
    return app


class TestTheResponseCarriesExactlyOneIdentifier:
    def test_markup_is_never_echoed(self) -> None:
        response = TestClient(_app()).get("/", headers={CORRELATION_HEADER: "<script>"})

        echoed = response.headers.get_list(CORRELATION_HEADER)
        assert len(echoed) == 1
        assert echoed[0] != "<script>"
        assert WELL_FORMED.fullmatch(echoed[0])

    def test_an_inner_layers_copy_is_replaced_not_joined(self) -> None:
        supplied = "0b8f7c1e-2c7a-4d51-9a55-7d0c6d8e1f00"

        response = TestClient(_app()).get("/", headers={CORRELATION_HEADER: supplied})

        assert response.headers.get_list(CORRELATION_HEADER) == [supplied]
