"""RFC 9457 problem details. **One error contract, and internal detail never reaches a client.**

Every error this service returns is `application/problem+json` carrying `type`, `title`, `status`,
`detail`, `instance` and `correlationId` (contracts/README.md). The correlation field is the one
addition to RFC 9457 and it is what lets a caller quoting an error be followed across the APIM hop
and both queues.

**Internal exception detail MUST NEVER reach a client** (`BL-18`; cross-stack gap,
``docs/governance/open-items.md`` §5). An
unhandled exception becomes a generic 500 whose `detail` says nothing about the failure; the actual
exception goes to telemetry, correlated by the same identifier. The split matters because this
service holds connector credentials and talks to customer systems — a leaked stack trace here can
disclose an endpoint, a vault reference or another organisation's identifier.

**The shape mirrors RagCore's field for field**, deliberately duplicated rather than shared
(Principle VI). A caller that parses one error contract parses both.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from integrations.api.middleware.correlation import current_correlation_id

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Awaitable, Callable

__all__ = [
    "PROBLEM_MEDIA_TYPE",
    "UNIVERSAL_PROBLEM_STATUSES",
    "ProblemDetails",
    "ProblemJSONResponse",
    "ProblemMiddleware",
    "install_exception_handlers",
    "problem",
    "problem_responses",
]

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE: Final = "application/problem+json"
_PROBLEM_BASE: Final = "https://synthia.synoptek.com/problems/"


class ProblemJSONResponse(JSONResponse):
    """A response at the media type RFC 9457 requires, rather than plain `application/json`."""

    media_type = PROBLEM_MEDIA_TYPE


def problem(
    *,
    status: int,
    title: str,
    detail: str,
    kind: str,
    instance: str = "",
) -> ProblemJSONResponse:
    """Build a problem response.

    Args:
        status: The HTTP status.
        title: A short, stable, human-readable summary. It MUST NOT vary per occurrence.
        detail: What a caller can act on. **Never internal exception text.**
        kind: The problem-type slug, appended to the platform problem namespace.
        instance: The request path, where one applies.

    Returns:
        The response, carrying the current correlation identifier.
    """
    body: dict[str, Any] = {
        "type": f"{_PROBLEM_BASE}{kind}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "correlationId": current_correlation_id(),
    }
    return ProblemJSONResponse(status_code=status, content=body)


class ProblemMiddleware(BaseHTTPMiddleware):
    """Converts an unhandled exception into a problem response that discloses nothing.

    Runs **outermost** (`BL-26`: exception handling first), so it catches
    failures in every middleware beneath it as well as in the endpoint.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Serve the request, converting any escape into a disclosure-free 500.

        Args:
            request: The inbound request.
            call_next: The rest of the pipeline.

        Returns:
            The response, or a generic problem when the pipeline raised.
        """
        try:
            return await call_next(request)
        except Exception:
            # The exception goes to telemetry, correlated. It does NOT go to the client: this
            # service holds connector credentials and talks to customer systems, so a stack trace
            # here can disclose an endpoint, a vault reference or another organisation's
            # identifier. `exc_info` is captured; the response body is deliberately uninformative.
            logger.exception(
                "Unhandled exception serving %s %s",
                request.method,
                request.url.path,
                extra={"correlationId": current_correlation_id()},
            )
            return problem(
                status=500,
                title="Internal Server Error",
                detail="The request could not be completed.",
                kind="internal-error",
                instance=request.url.path,
            )


class ProblemDetails(BaseModel):
    """The RFC 9457 body, declared so it appears in every emitted document.

    **The document has to say what an error looks like, or the contract is only half emitted.**
    This module already returns this shape at runtime; without a model the generator falls back to
    FastAPI's own `HTTPValidationError`, and the published contract then describes an error body
    this service never sends.

    Mirrors RagCore's `ProblemDetails` field for field — duplicated rather than shared
    (Principle VI), because one error contract across the platform is what lets a client parse one
    shape rather than two.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    instance: str
    correlation_id: str = Field(
        alias="correlationId",
        description=(
            "The one addition to RFC 9457. It is what lets a caller quoting an error be followed "
            "across the gateway hop and both queues."
        ),
    )


_TITLES: Final[dict[int, str]] = {
    400: "Invalid request",
    401: "Unauthenticated",
    403: "Not authorized",
    404: "Not found",
    422: "Invalid request",
    500: "Internal error",
    502: "Capability unavailable",
    503: "Capability unavailable",
}
"""The stable ``title`` for each status this service publishes. One title per type URI."""

UNIVERSAL_PROBLEM_STATUSES: Final[tuple[int, ...]] = (401, 403, 404, 422, 500)
"""Declared on every operation, because every operation can produce each of them.

401 and 403 come from the identity middleware before routing; 404 is how an object
belonging to another organisation is reported; 422 is a body that did not match; 500 is the
catch-all handler.
"""


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` entries declaring the error contract for each status.

    Args:
        statuses: The statuses to declare.

    Returns:
        A mapping ready to pass as `responses=` to a router or route decorator.

    Raises:
        ValueError: When a status has no declared title. Rejected rather than published with an
            invented one — a title is part of the contract a client branches on.
    """
    unknown = [s for s in statuses if s not in _TITLES]
    if unknown:
        raise ValueError(f"no declared problem title for status(es) {unknown}")

    return {
        status: {
            "description": _TITLES[status],
            "content": {PROBLEM_MEDIA_TYPE: {"schema": ProblemDetails.model_json_schema()}},
        }
        for status in statuses
    }


def install_exception_handlers(app: FastAPI) -> None:
    """Reshape framework-raised errors into the platform's one error contract.

    **Without this, a 422 is published as `application/json` carrying FastAPI's own
    `HTTPValidationError`** — a second error shape a client would have to parse, which
    `build/scripts/openapi_validate.py` refuses as unpublishable and rightly so.

    Args:
        app: The application.
    """

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: Exception) -> Response:
        """A malformed body or an unknown field. **Never silently ignored.**

        An organisation supplied as `tenantId` lands here, because the request models forbid extra
        fields — refused rather than dropped, so a caller cannot believe it was honoured.
        """
        del exc
        return problem(
            status=422,
            title=_TITLES[422],
            detail="The request did not match the contract for this endpoint.",
            kind="invalid-request",
            instance=request.url.path,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: Exception) -> Response:
        """Framework-raised statuses, reshaped into problem details."""
        status = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
        return problem(
            status=status,
            title=_TITLES.get(status, "Request failed"),
            detail=str(getattr(exc, "detail", "")),
            kind=f"http-{status}",
            instance=request.url.path,
        )
