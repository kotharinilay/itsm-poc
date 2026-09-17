"""RFC 9457 problem details, in the shape the .NET side emits.

One error contract across both deployables (research R-015, contracts/README.md). A client
calls both — they are two backends behind one trust boundary — so an error from RagCore and an
error from the monolith must be the same shape or every client grows two error paths.

``application/problem+json`` with ``type``, ``title``, ``status``, ``detail``, ``instance`` and
``correlationId``. The last is not part of RFC 9457 and is added deliberately: it is what lets a
user quoting an error be followed across an asynchronous, suspendable flow (spec FR-OPS-001).

**What a problem document never contains.** No stack trace, no provider error string, no SQL, no
tenant identifier and no principal identifier. A 404 that exists *because* the resource belongs to
another organisation is indistinguishable from one where nothing exists, which is the point:
existence is itself tenant-scoped information (contracts/README.md).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import Message

from ragcore.api.schemas import ProblemDetails
from ragcore.domain.errors import (
    AuthorizationError,
    AuthorizationExpiredError,
    DomainError,
    TenantNotAdmittedError,
    TreatmentNotInCatalogueError,
    WorkAlreadyClaimedError,
)

_log = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE: Final = "application/problem+json"

PROBLEM_BASE: Final = "https://synthia.synoptek.com/problems"
"""Namespace for ``type`` URIs. Stable identifiers a client may branch on."""

CORRELATION_HEADER: Final = "X-Correlation-Id"


def problem_dict(
    *,
    status: int,
    title: str,
    detail: str,
    instance: str,
    correlation_id: str,
    problem_type: str | None = None,
) -> dict[str, object]:
    """Build one problem document.

    Args:
        status: HTTP status code.
        title: Short, human-readable summary. Stable for a given ``type``.
        detail: What happened, in platform vocabulary. Never a provider or database message.
        instance: The request path.
        correlation_id: The identifier carried on every log, span, trigger and audit record.
        problem_type: The ``type`` URI slug. Derived from the status when omitted.

    Returns:
        The document, ready to serialize.
    """
    slug = problem_type if problem_type is not None else f"http-{status}"
    return {
        "type": f"{PROBLEM_BASE}/{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "correlationId": correlation_id,
    }


def problem_response(
    *,
    status: int,
    title: str,
    detail: str,
    instance: str,
    correlation_id: str,
    problem_type: str | None = None,
) -> list[Message]:
    """Build a problem response as raw ASGI messages.

    For middleware that has no ``Request`` to respond from — the identity middleware refuses
    before FastAPI's routing has run, so it cannot use the exception handlers below.

    Returns:
        The ``http.response.start`` and ``http.response.body`` messages, in order.
    """
    body = json.dumps(
        problem_dict(
            status=status,
            title=title,
            detail=detail,
            instance=instance,
            correlation_id=correlation_id,
            problem_type=problem_type,
        )
    ).encode()
    return [
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", PROBLEM_MEDIA_TYPE.encode()),
                (b"content-length", str(len(body)).encode()),
                (CORRELATION_HEADER.lower().encode(), correlation_id.encode()),
            ],
        },
        {"type": "http.response.body", "body": body},
    ]


# How each domain error surfaces. The mapping is explicit rather than derived from the class
# name, because the status a refusal deserves is a product decision: a tenant that is not
# admitted is a 403, while work that belongs to another organisation is a 404, and no naming
# convention encodes that difference.
_DOMAIN_STATUS: Final[dict[type[DomainError], tuple[int, str, str]]] = {
    TenantNotAdmittedError: (403, "Organisation not admitted", "tenant-not-admitted"),
    AuthorizationError: (403, "Not authorized", "not-authorized"),
    TreatmentNotInCatalogueError: (403, "Operation not permitted", "not-in-catalogue"),
    AuthorizationExpiredError: (410, "Authorization expired", "authorization-expired"),
    WorkAlreadyClaimedError: (409, "Already claimed", "already-claimed"),
}


def _correlation_id(request: Request) -> str:
    value = getattr(request.state, "correlation_id", "")
    return value if isinstance(value, str) else ""


def _response(request: Request, status: int, title: str, detail: str, slug: str) -> JSONResponse:
    correlation_id = _correlation_id(request)
    return JSONResponse(
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers={CORRELATION_HEADER: correlation_id},
        content=problem_dict(
            status=status,
            title=title,
            detail=detail,
            instance=request.url.path,
            correlation_id=correlation_id,
            problem_type=slug,
        ),
    )


def install_problem_handlers(app: FastAPI) -> None:
    """Register the handlers that turn every failure into one shape.

    Args:
        app: The application to install onto.
    """

    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: Exception) -> JSONResponse:
        """Map a domain refusal to its documented status.

        An unmapped ``DomainError`` becomes a 403 rather than a 500: a refusal the mapping has
        not been updated for is still a refusal, and reporting it as a server fault would tell a
        user the platform broke when in fact it declined.
        """
        mapped = _DOMAIN_STATUS.get(type(exc)) if isinstance(exc, DomainError) else None
        status, title, slug = mapped if mapped is not None else (403, "Refused", "refused")
        return _response(request, status, title, str(exc), slug)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: Exception) -> JSONResponse:
        """A malformed body or an unknown filter field. Never silently ignored."""
        del exc
        return _response(
            request,
            422,
            "Invalid request",
            "The request did not match the contract for this endpoint.",
            "invalid-request",
        )

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: Exception) -> JSONResponse:
        """Framework-raised statuses, reshaped into problem details."""
        status = exc.status_code if isinstance(exc, HTTPException) else 500
        detail = str(exc.detail) if isinstance(exc, HTTPException) else ""
        return _response(request, status, "Request failed", detail, f"http-{status}")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        """Anything unanticipated.

        Logged in full with the correlation identifier; reported with none of it. The exception
        text could carry a connection string, a row from another organisation or a provider
        error, and a 500 body is the wrong place to find out.
        """
        _log.exception(
            "unhandled error", extra={"correlation_id": _correlation_id(request)}, exc_info=exc
        )
        return _response(
            request,
            500,
            "Internal error",
            "The request could not be completed. Quote the correlation identifier when reporting.",
            "internal-error",
        )


# ---------------------------------------------------------------------------
# The same contract, declared rather than only returned
# ---------------------------------------------------------------------------


class ProblemJSONResponse(JSONResponse):
    """A response whose media type is the one RFC 9457 requires.

    Used as a route's ``response_class`` where the route's *success* status is itself a problem —
    the 501 placeholders. Without it the generator would document those bodies as
    ``application/json``, and a client branching on the media type would never see them.
    """

    media_type = PROBLEM_MEDIA_TYPE


_TITLES: Final[dict[int, str]] = {
    400: "Invalid request",
    401: "Unauthenticated",
    403: "Not authorized",
    404: "Not found",
    409: "Already claimed",
    410: "Authorization expired",
    422: "Invalid request",
    500: "Internal error",
    501: "Not implemented",
}
"""The stable ``title`` for each status this platform publishes. One title per type URI."""

UNIVERSAL_PROBLEM_STATUSES: Final[tuple[int, ...]] = (401, 403, 404, 422, 500)
"""Declared on every operation, because every operation can produce each of them.

401 and 403 come from the identity middleware before routing; 404 is how a resource belonging to
another organisation is reported; 422 is a body that did not match; 500 is the catch-all handler.
"""


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses`` entries declaring the error contract for each status.

    Args:
        statuses: The statuses to declare. Unrecognised ones are rejected rather than published
            with an invented title — a title is part of the contract a client branches on.

    Returns:
        A mapping ready to pass as ``responses=`` to an ``APIRouter`` or a route decorator.

    Raises:
        ValueError: When a status has no declared title.
    """
    unknown = sorted(status for status in statuses if status not in _TITLES)
    if unknown:
        raise ValueError(f"no declared problem title for {unknown}")

    return {
        status: {"model": ProblemDetails, "description": _TITLES[status]} for status in statuses
    }


def not_implemented(request: Request) -> ProblemDetails:
    """The 501 body a wired-but-inert route returns.

    A scaffold route returns a problem document rather than ``{"detail": ...}`` for the same reason
    it returns 501 rather than 200: the client parses one error contract, and an endpoint that
    invents a second shape for "nothing runs here yet" is a client branch that survives the
    scaffold.
    """
    return ProblemDetails(
        type=f"{PROBLEM_BASE}/not-implemented",
        title=_TITLES[501],
        status=501,
        detail=("No product behaviour exists at this stage. The boundary is wired; nothing runs."),
        instance=request.url.path,
        correlation_id=_correlation_id(request),
    )
