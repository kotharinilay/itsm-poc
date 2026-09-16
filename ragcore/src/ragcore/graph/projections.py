"""Enum-to-channel conversion: the one place a domain value becomes a state literal.

:mod:`ragcore.graph.state` is deliberately free of domain imports — it describes what a
checkpoint holds, in terms a checkpoint can hold. The nodes work in domain types. Something has
to convert, and doing it inline would mean ``outcome.treatment.value`` typed as ``str`` flowing
into a ``Literal`` field behind a type-checker suppression at every call site.

So it happens here, once, through total mappings. Each mapping is exhaustive over its enum, and
``tests/unit/test_graph_state.py`` asserts that — so adding an enum member without adding it here
fails a test rather than raising a :class:`KeyError` on the one path that reaches the new case.
"""

from __future__ import annotations

from typing import Final

from ragcore.domain.governance import ExecutionTreatment, VerificationOutcome
from ragcore.domain.work import InterruptKind, SessionState
from ragcore.governance.gate import GateDisposition
from ragcore.graph.state import (
    DispositionValue,
    InterruptValue,
    SessionStateValue,
    TreatmentValue,
    VerificationValue,
)

TREATMENT_VALUES: Final[dict[ExecutionTreatment, TreatmentValue]] = {
    ExecutionTreatment.AUTO: "AUTO",
    ExecutionTreatment.END_USER_APPROVAL: "END_USER_APPROVAL",
    ExecutionTreatment.STAFF_APPROVAL: "STAFF_APPROVAL",
    ExecutionTreatment.NOT_ALLOWED: "NOT_ALLOWED",
}

DISPOSITION_VALUES: Final[dict[GateDisposition, DispositionValue]] = {
    GateDisposition.PROCEED: "proceed",
    GateDisposition.SUSPEND_FOR_CONSENT: "suspend_for_consent",
    GateDisposition.SUSPEND_FOR_APPROVAL: "suspend_for_approval",
    GateDisposition.REFUSE: "refuse",
}

INTERRUPT_VALUES: Final[dict[InterruptKind, InterruptValue]] = {
    InterruptKind.CLARIFICATION: "clarification",
    InterruptKind.CONSENT: "consent",
    InterruptKind.APPROVAL: "approval",
}

SESSION_STATE_VALUES: Final[dict[SessionState, SessionStateValue]] = {
    SessionState.CONVERSATIONAL: "conversational",
    SessionState.RESOLVING: "resolving",
    SessionState.AWAITING_USER: "awaiting_user",
    SessionState.AWAITING_CONSENT: "awaiting_consent",
    SessionState.AWAITING_APPROVAL: "awaiting_approval",
    SessionState.STAFF_CONTROLLED: "staff_controlled",
    SessionState.RESOLVED: "resolved",
    SessionState.ESCALATED: "escalated",
    SessionState.CLOSED_DECLINED: "closed_declined",
}

VERIFICATION_VALUES: Final[dict[VerificationOutcome, VerificationValue]] = {
    VerificationOutcome.SERVER_CONFIRMED: "server_confirmed",
    VerificationOutcome.CLIENT_ATTESTED: "client_attested",
    VerificationOutcome.CONTRADICTED: "contradicted",
}


def treatment_value(treatment: ExecutionTreatment) -> TreatmentValue:
    """Project a treatment onto its channel literal."""
    return TREATMENT_VALUES[treatment]


def disposition_value(disposition: GateDisposition) -> DispositionValue:
    """Project a gate disposition onto its channel literal."""
    return DISPOSITION_VALUES[disposition]


def interrupt_value(kind: InterruptKind) -> InterruptValue:
    """Project an interrupt kind onto its channel literal."""
    return INTERRUPT_VALUES[kind]


def session_state_value(state: SessionState) -> SessionStateValue:
    """Project a session state onto its channel literal."""
    return SESSION_STATE_VALUES[state]


def verification_value(outcome: VerificationOutcome) -> VerificationValue:
    """Project a verification outcome onto its channel literal."""
    return VERIFICATION_VALUES[outcome]
