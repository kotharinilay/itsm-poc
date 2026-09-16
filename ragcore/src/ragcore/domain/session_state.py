"""The session state machine (T076).

``SessionState`` in :mod:`ragcore.domain.work` names the nine states. This module says which
moves between them are legal, and it is the only place that knowledge lives.

**Why a table rather than ``if`` statements at each call site.** A transition rule spread across
the code base is a rule that holds until somebody adds a branch. Here the legal set is data, an
illegal move raises, and ``test_session_state.py`` can enumerate every pair — including the ones
that must fail.

Two properties the specification cares about are structural here rather than remembered:

* **The three ``awaiting_*`` states persist indefinitely** (spec FR-SESS-016). Nothing in this
  module takes a clock, a timeout or a deadline, so there is no expression for "this suspension
  aged out". Losing the realtime connection cannot change a session's state because the
  realtime channel never reaches this module.
* **A terminal state is terminal.** No transition leaves one. Retention is measured from the
  moment a session reaches one (spec FR-SESS-020), and a resurrected session would restart a
  clock that has already started.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from ragcore.domain.errors import DomainError
from ragcore.domain.work import InterruptKind, SessionState


class IllegalSessionTransitionError(DomainError):
    """A move the state machine does not permit.

    Raised rather than returned, because there is no sensible way for a caller to carry on: the
    session is not in the state the caller believed it was in, and guessing which one it *is*
    would be inventing state.
    """

    def __init__(self, current: SessionState, requested: SessionState) -> None:
        super().__init__(f"{current.value} -> {requested.value} is not a legal session transition")
        self.current = current
        self.requested = requested


_LEGAL: Final[Mapping[SessionState, frozenset[SessionState]]] = {
    SessionState.CONVERSATIONAL: frozenset(
        {
            SessionState.RESOLVING,
            SessionState.AWAITING_USER,
            SessionState.STAFF_CONTROLLED,
            SessionState.RESOLVED,
            SessionState.ESCALATED,
            SessionState.CLOSED_DECLINED,
        }
    ),
    SessionState.RESOLVING: frozenset(
        {
            SessionState.CONVERSATIONAL,
            SessionState.AWAITING_USER,
            SessionState.AWAITING_CONSENT,
            SessionState.AWAITING_APPROVAL,
            SessionState.STAFF_CONTROLLED,
            SessionState.RESOLVED,
            SessionState.ESCALATED,
            SessionState.CLOSED_DECLINED,
        }
    ),
    # Every awaiting state can be cancelled (spec FR-INTR-014) and taken over (FR-INTR-013),
    # and resumes into RESOLVING when its decision arrives (FR-INTR-011).
    SessionState.AWAITING_USER: frozenset(
        {
            SessionState.RESOLVING,
            SessionState.STAFF_CONTROLLED,
            SessionState.ESCALATED,
            SessionState.CLOSED_DECLINED,
        }
    ),
    SessionState.AWAITING_CONSENT: frozenset(
        {
            SessionState.RESOLVING,
            SessionState.STAFF_CONTROLLED,
            SessionState.ESCALATED,
            SessionState.CLOSED_DECLINED,
        }
    ),
    SessionState.AWAITING_APPROVAL: frozenset(
        {
            SessionState.RESOLVING,
            SessionState.STAFF_CONTROLLED,
            SessionState.ESCALATED,
            SessionState.CLOSED_DECLINED,
        }
    ),
    SessionState.STAFF_CONTROLLED: frozenset(
        {
            SessionState.RESOLVED,
            SessionState.ESCALATED,
            SessionState.CLOSED_DECLINED,
        }
    ),
    SessionState.RESOLVED: frozenset(),
    SessionState.ESCALATED: frozenset(),
    SessionState.CLOSED_DECLINED: frozenset(),
}
"""Legal moves, keyed by the state being left. An absent target is illegal, not undefined."""


_SUSPENSION_FOR: Final[Mapping[InterruptKind, SessionState]] = {
    InterruptKind.CLARIFICATION: SessionState.AWAITING_USER,
    InterruptKind.CONSENT: SessionState.AWAITING_CONSENT,
    InterruptKind.APPROVAL: SessionState.AWAITING_APPROVAL,
}
"""Which suspension each interrupt produces. One-to-one and total over ``InterruptKind``."""


def can_transition(current: SessionState, requested: SessionState) -> bool:
    """Whether ``requested`` is reachable from ``current``.

    Args:
        current: The state the session is in.
        requested: The state being asked for.

    Returns:
        ``True`` when the move is legal. A move from a state to itself is **not** legal: a
        no-op transition hides a caller that did not know where it was.
    """
    return requested in _LEGAL[current]


def transition(current: SessionState, requested: SessionState) -> SessionState:
    """Apply a transition, or refuse it.

    Args:
        current: The state the session is in.
        requested: The state being asked for.

    Returns:
        ``requested``, once it is established to be legal.

    Raises:
        IllegalSessionTransitionError: When the move is not in the legal set.
    """
    if not can_transition(current, requested):
        raise IllegalSessionTransitionError(current, requested)
    return requested


def suspension_for(kind: InterruptKind) -> SessionState:
    """The state a session enters when it suspends on ``kind``.

    Args:
        kind: Which of the three interruptions fired.

    Returns:
        The matching ``awaiting_*`` state.
    """
    return _SUSPENSION_FOR[kind]


def terminal_states() -> frozenset[SessionState]:
    """The states that start the content-retention clock (spec FR-SESS-020)."""
    return frozenset(state for state in SessionState if state.is_terminal)
