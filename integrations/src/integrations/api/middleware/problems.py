"""RFC 9457 problem details. **One error contract, and internal detail never reaches a client.**

Every error this service returns is `application/problem+json` carrying `type`, `title`, `status`,
`detail`, `instance` and `correlationId` (contracts/README.md). The correlation field is the one
addition to RFC 9457 and it is what lets a caller quoting an error be followed across the APIM hop
and both queues.

**Internal exception detail MUST NEVER reach a client** (constitution §Validation and errors). An
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

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from integrations.api.middleware.correlation import current_correlation_id

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

__all__ = ["PROBLEM_MEDIA_TYPE", "ProblemJSONResponse", "ProblemMiddleware", "problem"]

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

    Runs **outermost** (constitution §Middleware order: exception handling first), so it catches
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
