"""The run host — the one place a compiled graph is invoked, and turned into a stream of events.

The graph is *built* in :mod:`ragcore.graph.builder` and *compiled against the durable
checkpointer* in :mod:`ragcore.graph.checkpointer`. This module is what runs it for one turn and
reports what happened.

**Why it is not in the endpoint.** An endpoint that invoked the graph directly would be an endpoint
holding orchestration policy — which node's output becomes which event, what a suspension reports,
what happens when the run ends without proposing anything. Constitution §FastAPI is explicit that
endpoints contain no business policy, and this is the policy that would otherwise leak into one.

**What this module does not know is SSE.** It yields :class:`TurnEvent`s and the transport renders
them. The dependency direction is ``api -> graph``; importing the streaming encoder here would
reverse it, and would also mean the run loop could only be tested through a web framework.

**The stream carries no authority** (contracts/customer-api.md). Every event is a report. An
``interrupt`` event says a decision is needed; it does not ask for one and cannot receive one.
**The stream ending is not a decision** — a dropped connection, a timeout or a closed laptop leaves
the work exactly where it was, suspended, indefinitely.

**What is deliberately absent from every event.** No treatment, no approval state, no command
content, no parameters, no disclosure of what would run, no retrieved text. A ``step`` is a
machine-readable kind and a short client-safe label. The only thing reconstructible from this
stream is that a turn happened.

**The run context is rebuilt per invocation from trusted sources** and is never checkpointed — see
:mod:`ragcore.graph.context` for why the tenant binding cannot travel in the checkpoint.

**Cancellation-safe.** A client disconnect cancels the task consuming the generator; the
``CancelledError`` is raised at the ``yield`` and propagates. Nothing here catches it, because a
cancelled stream must not be mistaken for a completed one — and there is no cleanup to shield,
since the graph's own state is already durable in the checkpointer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final

from langchain_core.runnables import RunnableConfig

from ragcore.graph.state import AgentState
from ragcore.graph.threads import checkpoint_thread_id

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from langgraph.graph.state import CompiledStateGraph

    from ragcore.graph.context import RunContext

__all__ = [
    "STEP_LABELS",
    "RunHost",
    "TurnEvent",
    "TurnEventKind",
    "thread_config",
]

STEP_LABELS: Final[dict[str, str]] = {
    "intake": "Reading your request",
    "converse": "Working on your request",
    "retrieve": "Looking for relevant guidance",
    "ground": "Checking what was found",
    "guardrail": "Checking this is something I can help with",
    "propose": "Deciding what to do",
    "classify": "Checking what this needs",
    "govern": "Applying governance",
    "execute": "Carrying it out",
    "verify": "Confirming the outcome",
    "close": "Finishing up",
}
"""One short, client-safe label per node.

**A closed mapping, not a rendering of the node name.** A node name is an implementation detail and
would leak into a user-visible string the moment somebody renamed one; worse, a future node called
``execute_privileged_script`` would announce itself. A node with no entry emits no step, which is
the safe default: silence discloses nothing.

The labels say what is happening and never what was decided. "Applying governance" is a step;
"approved" would be an outcome, and outcomes belong on records a client reads under its own
identity.
"""


class TurnEventKind(Enum):
    """What one event reports. Mirrors the SSE kinds the transport publishes.

    Deliberately its own enum rather than an import of
    :class:`~ragcore.api.customer.streaming.StreamEventKind`: the graph layer does not depend on
    the transport, and two small enums that ``tests/unit/test_run_host.py`` asserts agree is
    cheaper than a dependency pointing the wrong way.

    There is no ``token`` member, and its absence is honest rather than an omission: the scaffold
    makes no model call, so there is no partial content to send.
    """

    STEP = "step"
    """Progress. A machine-readable node kind and a short client-safe label."""

    INTERRUPT = "interrupt"
    """The run suspended. A kind; it asks for nothing."""

    DONE = "done"
    """The turn completed. **Not** a statement that anything was authorized or executed."""

    ERROR = "error"
    """The turn failed. The transport attaches a correlation identifier; this carries no detail."""


@dataclass(frozen=True, slots=True)
class TurnEvent:
    """One thing worth telling the client about.

    Attributes:
        kind: What this reports.
        name: The node kind, for a ``step``; the interrupt kind, for an ``interrupt``; empty
            otherwise.
        label: The short client-safe label, for a ``step``. Empty otherwise — and never a rendering
            of a node name; see :data:`STEP_LABELS`.
    """

    kind: TurnEventKind
    name: str = ""
    label: str = ""


def thread_config(context: RunContext) -> RunnableConfig:
    """The checkpointer thread for one session, **derived from trusted identity**.

    The thread is the organisation, the requester and the session together — see
    :mod:`ragcore.graph.threads`. Keyed on the session alone, the thread was whatever identifier a
    caller put in the path: another organisation, or another user, naming the same session would
    have resumed this one's conversation and the authority context it was suspended on.
    """
    thread_id = checkpoint_thread_id(
        context.tenant.tenant_id.value, context.requester.value, context.session_id.value
    )
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    return config


@dataclass(frozen=True, slots=True)
class RunHost:
    """Runs one turn of the graph and reports it as a sequence of events.

    Frozen: the compiled graph is bound once, at application startup, against the one durable
    checkpointer. A host whose graph could be swapped mid-process is a host where a suspension
    written by one shape is resumed by another.

    Attributes:
        graph: The compiled graph. Compiled with a checkpointer in every deployed process — an
            in-memory saver would lose every awaiting conversation on the next scale-to-zero,
            silently and without an error anywhere.
    """

    graph: CompiledStateGraph[AgentState, RunContext, AgentState, AgentState]

    async def stream_turn(self, context: RunContext, turn: AgentState) -> AsyncIterator[TurnEvent]:
        """Run one turn, emitting an event per node and exactly one terminal event.

        Args:
            context: The trusted bindings for this invocation — organisation, requester,
                correlation and session. Re-established from validated identity on every call and
                never read back out of the checkpoint.
            turn: The initial state: the conversation turn that started it. The caller builds it;
                a node cannot.

        Yields:
            A ``step`` per node that has a label, an ``interrupt`` where the run suspended, then
            exactly one of ``done`` or ``error``.
        """
        try:
            async for update in self.graph.astream(
                turn, config=thread_config(context), context=context
            ):
                for node, channels in update.items():
                    if node == "__interrupt__":
                        yield TurnEvent(TurnEventKind.INTERRUPT, name=_interrupt_kind(channels))
                        continue

                    label = STEP_LABELS.get(node)
                    if label is not None:
                        yield TurnEvent(TurnEventKind.STEP, name=node, label=label)
        except Exception:
            # Deliberately broad, and deliberately re-raised after the event. The response status
            # is already 200 and the headers are already sent, so there is no status left to fail
            # with — the only honest thing available is an `error` event, which the transport
            # renders with a correlation identifier. The exception is NOT rendered into it: a
            # provider message can carry an endpoint, a header or a token, and this reaches a
            # browser.
            yield TurnEvent(TurnEventKind.ERROR)
            raise

        # `done` even after a suspension. The TURN finished; the work has not, and the interrupt
        # event already said so. Closing silently would leave a client unable to tell "the turn
        # ended" from "the connection dropped", which is the distinction the whole
        # stream-carries-no-authority rule depends on.
        yield TurnEvent(TurnEventKind.DONE)


def _interrupt_kind(payload: object) -> str:
    """The interrupt kind, read from the node's own payload.

    **Only the kind is read.** The payload is built by a node, and rendering a session or work
    identifier from it — rather than from the trusted run context the transport already holds —
    would let a node address a frame at another session. An unreadable payload falls back to
    ``clarification``, the interrupt that asks the end user rather than announcing a pending
    decision: a wrong label on the least consequential interrupt is the safe failure.
    """
    if isinstance(payload, tuple | list) and payload:
        value = getattr(payload[0], "value", None)
        if isinstance(value, dict):
            candidate = value.get("kind")
            if isinstance(candidate, str):
                return candidate
    return "clarification"
