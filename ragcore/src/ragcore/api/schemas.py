"""Shared request and response schema conventions.

**camelCase both directions, both deployables** (contracts/README.md). A client calls RagCore and
the .NET monolith in the same session, so one casing convention is not a style preference — two
would mean every client carrying two serializers.

**What no request schema on this platform has.** No ``tenantId``, no ``roles``, no ``audience``,
no ``actAs``. Those are derived from trusted identity, and a Pydantic model that declared one
would make it part of the OpenAPI document — advertising a parameter the middleware rejects.
``tests/contracts/test_api_surface.py`` walks every model and asserts none appears.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base for every request and response body crossing the HTTP boundary.

    ``extra="forbid"`` is the load-bearing setting. An unknown field is a **400**, never silently
    dropped: a client sending ``{"verdict": "granted", "treatment": "AUTO"}`` must be told the
    second field is not part of the contract, rather than having it quietly ignored and going on
    believing it did something.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class Acknowledged(ApiModel):
    """The response to a command that was accepted but whose effect happens elsewhere.

    Deliberately carries no outcome. **The approving request returns before execution runs**
    (contracts/triggers.md): a verdict is recorded, a trigger is published, and the execution leg
    picks it up. A response that reported success would be reporting something that has not
    happened yet, and a client showing it would be lying to a user.
    """

    accepted: bool = True
    correlation_id: str


class HealthStatus(ApiModel):
    """Liveness. Carries nothing about an organisation, a session or a decision."""

    status: str = "ok"


class ProblemDetails(ApiModel):
    """The RFC 9457 error body, declared so it appears in every emitted document.

    **The document has to say what an error looks like, or the contract is only half emitted.**
    :mod:`ragcore.api.middleware.problems` already returns this shape at runtime; without a model
    the generator falls back to FastAPI's ``HTTPValidationError``, and the published contract then
    describes an error body the service never sends.

    Mirrors ``Synthia.Contracts.Errors.ProblemContract`` on the .NET side field for field, because a
    client calls both deployables and must parse one error contract, not two.

    ``correlationId`` is the one addition to RFC 9457, and it is what lets a user quoting an error
    be followed across an asynchronous, suspendable flow (spec FR-OPS-001).
    """

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    correlation_id: str
