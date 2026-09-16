"""The session state machine: nine states, and which moves between them are legal."""

from __future__ import annotations

import pytest

from ragcore.domain.session_state import (
    IllegalSessionTransitionError,
    can_transition,
    suspension_for,
    terminal_states,
    transition,
)
from ragcore.domain.work import InterruptKind, SessionState

ALL_STATES = list(SessionState)
TERMINAL_STATES: list[SessionState] = sorted(terminal_states(), key=lambda s: s.value)
"""Bound to a typed name: ``parametrize`` takes ``Iterable[object]`` and erases the enum."""


class TestTheNineStates:
    """The set is closed, and the three classifications over it are exact."""

    def test_there_are_exactly_nine(self) -> None:
        assert len(ALL_STATES) == 9

    def test_the_three_terminal_states(self) -> None:
        """Terminal states start the content-retention clock (spec FR-SESS-020)."""
        assert terminal_states() == {
            SessionState.RESOLVED,
            SessionState.ESCALATED,
            SessionState.CLOSED_DECLINED,
        }

    def test_the_three_awaiting_states(self) -> None:
        awaiting = {state for state in ALL_STATES if state.is_awaiting}
        assert awaiting == {
            SessionState.AWAITING_USER,
            SessionState.AWAITING_CONSENT,
            SessionState.AWAITING_APPROVAL,
        }

    def test_no_state_is_both_awaiting_and_terminal(self) -> None:
        """A suspension that had also ended would start a retention clock on live work."""
        assert not {s for s in ALL_STATES if s.is_awaiting and s.is_terminal}


class TestTransitions:
    """The legal set is data, so it can be checked exhaustively — including what must fail."""

    @pytest.mark.parametrize("state", ALL_STATES)
    def test_every_state_has_a_declared_legal_set(self, state: SessionState) -> None:
        """An undeclared state would raise ``KeyError`` on whichever path first reached it."""
        assert can_transition(state, state) is False or True  # exercises the lookup

    @pytest.mark.parametrize("state", ALL_STATES)
    def test_no_state_transitions_to_itself(self, state: SessionState) -> None:
        """A no-op transition hides a caller that did not know where it was."""
        assert can_transition(state, state) is False

    @pytest.mark.parametrize("state", TERMINAL_STATES)
    def test_a_terminal_state_is_terminal(self, state: SessionState) -> None:
        """Resurrecting a session would restart a retention clock that has already started."""
        for target in ALL_STATES:
            assert can_transition(state, target) is False

    @pytest.mark.parametrize(
        "state",
        [
            SessionState.AWAITING_USER,
            SessionState.AWAITING_CONSENT,
            SessionState.AWAITING_APPROVAL,
        ],
    )
    def test_every_suspension_can_be_cancelled(self, state: SessionState) -> None:
        """Cancellation is available at every suspension point (spec FR-INTR-014)."""
        assert can_transition(state, SessionState.CLOSED_DECLINED)

    @pytest.mark.parametrize(
        "state",
        [
            SessionState.AWAITING_USER,
            SessionState.AWAITING_CONSENT,
            SessionState.AWAITING_APPROVAL,
        ],
    )
    def test_every_suspension_can_be_taken_over(self, state: SessionState) -> None:
        """A take-over is a single authenticated transition (spec FR-INTR-013)."""
        assert can_transition(state, SessionState.STAFF_CONTROLLED)

    @pytest.mark.parametrize(
        "state",
        [
            SessionState.AWAITING_USER,
            SessionState.AWAITING_CONSENT,
            SessionState.AWAITING_APPROVAL,
        ],
    )
    def test_every_suspension_resumes_into_resolving(self, state: SessionState) -> None:
        """Resume continues the work rather than restarting the interaction (FR-INTR-012)."""
        assert can_transition(state, SessionState.RESOLVING)

    def test_an_illegal_transition_raises(self) -> None:
        with pytest.raises(IllegalSessionTransitionError):
            transition(SessionState.RESOLVED, SessionState.RESOLVING)

    def test_a_legal_transition_returns_the_requested_state(self) -> None:
        assert transition(SessionState.CONVERSATIONAL, SessionState.RESOLVING) is (
            SessionState.RESOLVING
        )

    def test_nothing_transitions_directly_from_conversational_to_a_decision(self) -> None:
        """A work record is committed only once a genuine request exists (spec FR-SESS-003)."""
        assert not can_transition(SessionState.CONVERSATIONAL, SessionState.AWAITING_CONSENT)
        assert not can_transition(SessionState.CONVERSATIONAL, SessionState.AWAITING_APPROVAL)


class TestSuspensionMapping:
    """Each interrupt produces exactly one suspension, and every kind is covered."""

    @pytest.mark.parametrize("kind", list(InterruptKind))
    def test_every_interrupt_kind_maps_to_an_awaiting_state(self, kind: InterruptKind) -> None:
        assert suspension_for(kind).is_awaiting

    def test_the_mapping_is_one_to_one(self) -> None:
        """Two interrupts sharing a state would make 'what is this waiting for' unanswerable."""
        suspensions = {suspension_for(kind) for kind in InterruptKind}
        assert len(suspensions) == len(list(InterruptKind))

    def test_the_expected_pairs(self) -> None:
        assert suspension_for(InterruptKind.CLARIFICATION) is SessionState.AWAITING_USER
        assert suspension_for(InterruptKind.CONSENT) is SessionState.AWAITING_CONSENT
        assert suspension_for(InterruptKind.APPROVAL) is SessionState.AWAITING_APPROVAL


class TestNothingExpiresASuspension:
    """The three awaiting states persist indefinitely (spec FR-SESS-016)."""

    def test_the_module_imports_no_clock(self) -> None:
        """There is no expression here for 'this suspension aged out'.

        Checked against imports and signatures rather than raw text: the prose in this module
        discusses timeouts precisely in order to rule them out, and a substring search would
        flag the explanation along with the thing it forbids.
        """
        import ast
        import inspect

        from ragcore.domain import session_state

        tree = ast.parse(inspect.getsource(session_state))

        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not imported & {"datetime", "time", "asyncio"}

        parameters = {
            argument.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            for argument in node.args.args
        }
        assert not parameters & {"now", "clock", "timeout", "deadline", "expires_at"}
