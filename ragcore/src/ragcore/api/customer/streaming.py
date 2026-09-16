"""The SSE streaming envelope.

Five event kinds — ``token``, ``step``, ``interrupt``, ``done``, ``error`` — and one rule that
outranks all of them:

**The stream carries no authority** (contracts/customer-api.md).

An ``interrupt`` event tells a client that a decision is needed. It does not ask for one and
cannot receive one: the decision is made by calling the consent or answer endpoint, authenticated,
where it is recorded durably. **The stream ending is not a decision.** A dropped connection, a
timeout or a closed laptop leaves the work exactly where it was — suspended, indefinitely — which
is why the three ``awaiting_*`` states have no expiry.

That is also why an ``interrupt`` event carries identifiers and a machine-readable ``kind`` and
nothing else. No approval state, no target, no command content, no disclosure of what would run.
A client fetches the disclosure from an authenticated API, where the caller is known.

**Accessibility reaches into this contract** (contracts/customer-api.md). ``token`` events carry
*incremental* text, never the accumulated message, so assistive technology can announce what
arrived without re-reading what it already announced. And every ``interrupt`` carries ``kind`` so
a client can convey state by more than colour.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from enum import Enum
from typing import Final

SSE_MEDIA_TYPE: Final = "text/event-stream"

SSE_HEADERS: Final[dict[str, str]] = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
"""Headers every stream response carries.

``X-Accel-Buffering: no`` is not incidental — a buffering reverse proxy holds tokens until the
response completes, which turns a progressive response into a slow one and defeats the purpose.
"""


class StreamEventKind(Enum):
    """The closed set of SSE event kinds. Adding one is a contract change."""

    TOKEN = "token"  # noqa: S105 — an SSE event name, not a credential
    """Partial content. **Incremental**, never the accumulated message so far."""

    STEP = "step"
    """Progress in the step trail. Identifiers and a label; never command content."""

    INTERRUPT = "interrupt"
    """Work suspended. Carries ``kind`` and identifiers only, and asks for nothing."""

    DONE = "done"
    """The turn completed. **Not** a statement that anything was authorized or executed."""

    ERROR = "error"
    """The turn failed. Carries a correlation identifier, never a stack trace."""


def encode_event(kind: StreamEventKind, data: Mapping[str, object]) -> str:
    """Encode one SSE frame.

    Args:
        kind: The event kind.
        data: The payload. Serialized as compact JSON on a single ``data:`` line, because a
            multi-line payload would need per-line prefixing and a reader that got it wrong would
            silently truncate.

    Returns:
        The wire-format frame, terminated by the blank line SSE requires.
    """
    return f"event: {kind.value}\ndata: {json.dumps(dict(data), separators=(',', ':'))}\n\n"


def token(text: str) -> str:
    """A partial-content frame carrying only what is new."""
    return encode_event(StreamEventKind.TOKEN, {"text": text})


def step(step_id: str, label: str) -> str:
    """A progress frame for the step trail."""
    return encode_event(StreamEventKind.STEP, {"stepId": step_id, "label": label})


def interrupt(kind: str, session_id: str, work_item_id: str | None, correlation_id: str) -> str:
    """An interrupt frame: identifiers and a kind, and nothing to act on.

    Args:
        kind: ``clarification``, ``consent`` or ``approval``. Machine-readable so a client can
            convey state by more than colour.
        session_id: The session that suspended.
        work_item_id: The work, where one exists.
        correlation_id: For following this across the asynchronous flow that follows.

    Returns:
        The frame. Note what is absent: no approval state, no target, no commands, no treatment.
    """
    return encode_event(
        StreamEventKind.INTERRUPT,
        {
            "kind": kind,
            "sessionId": session_id,
            "workItemId": work_item_id,
            "correlationId": correlation_id,
        },
    )


def done(session_id: str) -> str:
    """A completion frame.

    Says the *turn* finished. It does not say anything was authorized, executed or verified —
    those are separate facts on separate records, and conflating them here is how a client ends
    up telling a user their request was actioned when it is waiting for approval.
    """
    return encode_event(StreamEventKind.DONE, {"sessionId": session_id})


def error(correlation_id: str) -> str:
    """A failure frame carrying a correlation identifier and nothing else."""
    return encode_event(
        StreamEventKind.ERROR,
        {
            "correlationId": correlation_id,
            "detail": "The turn could not be completed. Quote the correlation identifier.",
        },
    )


async def empty_stream(session_id: str) -> AsyncIterator[str]:
    """The scaffold's stream: open it, close it honestly, emit no content.

    No model is called at this stage (Stage 6 non-goals), so there are no tokens to send. It
    still emits ``done`` rather than closing silently, because a client distinguishing "the turn
    finished" from "the connection dropped" is exactly what the stream-carries-no-authority rule
    depends on.

    **Cancellation-safe.** A client disconnect cancels the task consuming this generator; the
    ``CancelledError`` is raised at the ``yield`` and propagates. Nothing here catches it, and
    there is no cleanup to shield because the scaffold's stream holds no resource.
    """
    yield done(session_id)
