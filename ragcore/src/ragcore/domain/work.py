"""Work item and session state models.

Enumerated in the specification (FR-EXEC-010, FR-SESS-015) rather than invented here.
"""

from __future__ import annotations

from enum import Enum


class WorkItemState(Enum):
    """The lifecycle of the durable authority record (spec FR-EXEC-010)."""

    OPEN = "open"
    AWAITING_DECISION = "awaiting_decision"
    AUTHORIZED = "authorized"
    CLAIMED = "claimed"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


class ApprovalState(Enum):
    """What a human decided (spec FR-EXEC-010).

    Independent of :class:`WorkItemState`: approval state records the decision, work state
    records what happened to the work. An ``APPROVED`` item that never executed must stay
    distinguishable from one that did.
    """

    NONE = "none"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalVerdict(Enum):
    """What a human decided on an approval request (``data-model.md``, ``approval.verdict``).

    **Exactly two members, and that is load-bearing.** This is deliberately NOT
    :class:`ApprovalState`, which is the work item's field and also carries ``pending`` and
    ``expired``. Typing a verdict as that enum would let ``record_verdict(EXPIRED)`` type-check —
    a system-synthesized verdict, which §17.7 and FR-INTR-008 prohibit outright:

        "No timeout, no auto-reject, no system-synthesized verdict."

    Expiry is a work-item transition performed by the expiry sweeper. It is never a recorded human
    decision, and ``approved_by`` always means a human approved (§17.8).

    There is no ``REJECT_AND_TAKE_OVER`` member either. §17.6 lists it as a staff *action*, but it
    is a rejection plus a session transition to ``staff_controlled`` — two things, recorded
    separately. A third verdict value would make the takeover invisible to anything reading the
    verdict alone.
    """

    APPROVED = "approved"
    """The operation proceeds as proposed. ``expires_at`` is set. No modification is possible."""

    REJECTED = "rejected"
    """The operation does not execute. The session escalates."""


class ConsentVerdict(Enum):
    """An end user's decision on an operation affecting their own account or device.

    Two members, mirroring ``data-model.md`` ``consent.verdict`` and the two consent trigger kinds.
    A boolean would collapse this to ``True``/``False`` at every call site, which the constitution
    prohibits as "a boolean parameter flag that hides behaviour" (Principle VI).
    """

    GRANTED = "granted"
    REFUSED = "refused"


class OperationStatus(Enum):
    """The lifecycle of one proposed or executed operation.

    Mirrors ``data-model.md`` ``operation.status``.

    Distinct from :class:`WorkItemState`: a work item is the durable authority record, an operation
    is a single action within it.

    ``GATED`` and ``REFUSED`` are why this type exists rather than being folded into the work
    item. ``GATED`` records that deterministic governance evaluated this operation at all, and
    ``REFUSED`` is how a ``NOT_ALLOWED`` outcome is recorded — a denial audited as durably as a
    permission (FR-AUDIT-003).
    """

    PROPOSED = "proposed"
    """The agent proposed it. A proposal authorizes nothing."""

    GATED = "gated"
    """The control gate evaluated it. Treatment came from the catalogue, never from the model."""

    AUTHORIZED = "authorized"
    """Cleared to execute, within its validity window."""

    EXECUTED = "executed"
    """Execution completed. See the verification outcome for what the platform actually knows."""

    FAILED = "failed"
    """Execution failed. Does not re-fire; requires fresh human authorization (FR-EXEC-006)."""

    REFUSED = "refused"
    """Refused at the gate. Never surfaced to a human as an approvable proposal."""


class SessionState(Enum):
    """The nine session states (spec FR-SESS-015).

    The three ``AWAITING_*`` states persist indefinitely; losing the realtime connection
    changes nothing.
    """

    CONVERSATIONAL = "conversational"
    RESOLVING = "resolving"
    AWAITING_USER = "awaiting_user"
    AWAITING_CONSENT = "awaiting_consent"
    AWAITING_APPROVAL = "awaiting_approval"
    STAFF_CONTROLLED = "staff_controlled"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED_DECLINED = "closed_declined"

    @property
    def is_terminal(self) -> bool:
        """Whether this state starts the content-retention clock (spec FR-SESS-020)."""
        return self in _TERMINAL_SESSION_STATES

    @property
    def is_awaiting(self) -> bool:
        """Whether the session is suspended on a human."""
        return self in _AWAITING_SESSION_STATES


_TERMINAL_SESSION_STATES = frozenset(
    {SessionState.RESOLVED, SessionState.ESCALATED, SessionState.CLOSED_DECLINED}
)
_AWAITING_SESSION_STATES = frozenset(
    {
        SessionState.AWAITING_USER,
        SessionState.AWAITING_CONSENT,
        SessionState.AWAITING_APPROVAL,
    }
)


class InterruptKind(Enum):
    """The three interruption types (spec FR-INTR-001)."""

    CLARIFICATION = "clarification"
    CONSENT = "consent"
    APPROVAL = "approval"


class SenderKind(Enum):
    """Who authored a message (``data-model.md`` §Message).

    Three members, not two. ``STAFF`` exists because a staff member may speak into a session they
    have taken over — and its presence in the conversation **never confers requester authority**
    (spec FR-SURF-009). A boolean ``is_agent`` would have made the third case unrepresentable and
    the rule unstateable.
    """

    END_USER = "end_user"
    """The end user who owns the session."""

    AGENT = "agent"
    """The platform. Carries no ``sender_oid``, because no principal authored it."""

    STAFF = "staff"
    """A staff member, valid only while the session is ``staff_controlled``."""


class FeedbackSignal(Enum):
    """A per-message thumbs signal (spec FR-SESS-009).

    **Never an input to a decision.** Governance, retrieval and execution MUST NOT read it
    (spec FR-SESS-011a, ``data-model.md`` §Feedback). It is a quality signal, and the reason it
    lives here rather than beside the treatment enums is to keep that separation legible.
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"
